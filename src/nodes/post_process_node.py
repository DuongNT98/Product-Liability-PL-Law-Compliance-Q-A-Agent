"""AgentCore Platform v1.0 - MFG-C2-066 ResponseValidateNode (outer post_process slot).

Attaches the non-suppressible 弁護士 referral notice (legal-liability
control - S-3), enforces the S-5 recall-burst rate limit, and emits the
S-4 audit event for the PL compliance query. Own-dict field re-check only
(S-3 self-consistency rule - [[s3-hook-cross-state-recheck-fragile]]).
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json
from src.services.service import REFERRAL_NOTICE, RecallBurstRateLimiter, has_incident_specific_quantification


class ResponseValidateNode(FunctionNode):
    """Enforce the recall-burst rate limit; attach the non-suppressible 弁護士 referral notice."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self, rate_limiter: RecallBurstRateLimiter | None = None) -> None:
        super().__init__()
        self._rate_limiter = rate_limiter or RecallBurstRateLimiter()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        caller_key = state.get("caller_id") or state.get("session_id") or "anonymous"
        if not self._rate_limiter.allow(caller_key):
            emit_trace_event("response_validate_rate_limited", {"reason": "recall_burst_rate_limit"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: S-5 recall-burst rate limit exceeded for caller"],
            }

        law_citation = state.get("law_citation", "")
        required_action_steps = from_json(state.get("required_action_steps", ""), [])
        eu_pld_crossref = state.get("eu_pld_crossref")

        action_text = "\n".join(required_action_steps) if required_action_steps else ""
        liability_framing_note = (
            "This guidance is generic compliance information, not an individualized liability determination."
        )
        formatted_output_parts = [action_text]
        if law_citation:
            formatted_output_parts.append(f"Citation: {law_citation}")
        formatted_output_parts.append(liability_framing_note)
        formatted_output_parts.append(REFERRAL_NOTICE)
        formatted_output = "\n\n".join(p for p in formatted_output_parts if p)

        emit_trace_event(
            "pl_compliance_query_answered",
            {
                "defect_type": state.get("defect_type", ""),
                "kb_sub_index": state.get("kb_sub_index", ""),
                "has_eu_pld_crossref": bool(eu_pld_crossref),
            },
            state,
        )

        return {
            "formatted_output": formatted_output,
            "liability_framing_note": liability_framing_note,
            "legal_advisor_referral_notice": REFERRAL_NOTICE,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Non-suppressible re-check on the output dict's own fields.

        The 弁護士 referral notice must be present in every answer, and the
        answer must never quantify liability for a specific incident.
        """
        formatted_output = state.get("formatted_output", "") or ""

        if REFERRAL_NOTICE not in formatted_output:
            emit_trace_event("response_validate_s3_recheck_blocked", {"reason": "referral_notice_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "ResponseValidateNode: S-3 re-check blocked an answer missing the non-suppressible 弁護士 referral notice"
                ],
            }

        if has_incident_specific_quantification(formatted_output):
            emit_trace_event("response_validate_s3_recheck_blocked", {"reason": "incident_quantification"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "ResponseValidateNode: S-3 re-check blocked an answer quantifying liability for a specific incident"
                ],
            }

        return state
