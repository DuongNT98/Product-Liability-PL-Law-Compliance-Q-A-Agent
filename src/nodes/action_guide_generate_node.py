"""AgentCore Platform v1.0 - MFG-C2-066 ActionGuideGenerateNode (inner subgraph).

LLM-optional recall/notification action-guide synthesis + 製造物責任法
citation; generic-only framing (no incident-specific liability
quantification). Runs last in the inner subgraph - pl_reg_passages already
in state from PLRegKBRetrieveNode within the same invocation.

LLM wiring (Azure OpenAI, graceful degrade): the `llm` constructor param is a
test-double seam only - production wiring never passes one. On each
invocation the node instead attempts to build a fresh AzureOpenAIClient from
the caller's bound secrets (never cached on self - node instances are reused
across callers via the registry's LRU cache). Any failure to build or call
the LLM (missing secret, malformed endpoint, API error, empty/unusable
response) degrades to the deterministic action guide - an LLM outage is not
a pipeline failure. See docs/02_design.md "LLM degrade policy".
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.services.llm.azure_openai_client import AzureOpenAIClient
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import (
    ActionGuideLLMError,
    generate_action_guide,
    has_incident_specific_quantification,
)


class ActionGuideGenerateNode(FunctionNode):
    """Generate recall/notification action steps + 製造物責任法 citation (generic-only)."""

    # S-1: inner subgraph node - trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._llm = llm

    def _resolve_llm(self, state: dict[str, Any]) -> Any:
        """Constructor-injected llm wins (test-double seam). Otherwise build a
        fresh AzureOpenAIClient per invocation from the caller's bound secrets;
        any failure (no secret provider bound, secret missing, malformed
        endpoint, ...) returns None so the caller degrades to the deterministic
        path rather than raising."""
        if self._llm is not None:
            return self._llm
        try:
            ctx = InvocationContext.from_state(state)
            return AzureOpenAIClient(
                {
                    "api_key": ctx.secrets.require("AZURE_OPENAI_API_KEY"),
                    "azure_endpoint": ctx.secrets.require("AZURE_OPENAI_ENDPOINT"),
                    "azure_deployment": ctx.secrets.require("AZURE_OPENAI_DEPLOYMENT"),
                }
            )
        except Exception:
            return None

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        defect_type = state.get("defect_type", "")
        passages = from_json(state.get("pl_reg_passages", ""), [])

        if not defect_type:
            emit_trace_event("action_guide_generate_rejected", {"reason": "defect_type_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ActionGuideGenerateNode: defect_type missing - DefectTypeClassifyNode must run first"],
            }

        llm = self._resolve_llm(state)
        try:
            law_citation, required_action_steps = generate_action_guide(defect_type, passages, llm=llm)
        except ActionGuideLLMError as exc:
            # Graceful-degrade contract: an LLM outage or unusable response is not
            # a pipeline failure - fall back to the deterministic action guide
            # instead of failing the request.
            emit_trace_event("action_guide_llm_degraded", {"reason": str(exc)}, state)
            law_citation, required_action_steps = generate_action_guide(defect_type, passages, llm=None)

        # S-3: generic-only framing - never quantify liability for a specific incident.
        joined_steps = "\n".join(required_action_steps)
        if has_incident_specific_quantification(joined_steps):
            emit_trace_event("action_guide_generate_rejected", {"reason": "incident_quantification"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "ActionGuideGenerateNode: generated guidance quantified liability for a specific incident - rejected"
                ],
            }

        emit_trace_event(
            "action_guide_generated",
            {"defect_type": defect_type, "step_count": len(required_action_steps)},
            state,
        )

        return {
            "law_citation": law_citation,
            "required_action_steps": to_json(required_action_steps),
            "status": AgentStatus.SUCCESS.value,
        }
