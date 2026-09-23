"""AgentCore Platform v1.0 - MFG-C2-066 QueryNormalizeNode (outer pre_process).

Sanitizes the incoming query, enum-validates any caller-supplied defect_type
hint (rejects free-form defect text that may carry confidential
product/incident data), classifies intent type, and serializes a combined
{query, defect_type_hint, jurisdiction} envelope as validated_input for the
GraphNode boundary (see [[graphnode-extract-input-multi-field-envelope]]).
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import to_json

_VALID_DEFECT_TYPES = ("design", "manufacturing", "instruction", "ambiguous")
_VALID_JURISDICTIONS = ("jp", "jp_eu_cross")


class QueryNormalizeNode(FunctionNode):
    """Sanitize the query; enum-validate defect_type; classify intent."""

    # S-1: outer boundary node - matches agent.yaml required_trust_level.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        user_input = state.get("user_input", "")

        if not user_input or not user_input.strip():
            emit_trace_event("query_normalize_rejected", {"reason": "empty_user_input"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["QueryNormalizeNode: user_input is empty or missing"],
            }

        defect_type_hint = state.get("defect_type_hint", "") or ""
        if defect_type_hint and defect_type_hint not in _VALID_DEFECT_TYPES:
            emit_trace_event("query_normalize_rejected", {"reason": "invalid_defect_type_hint_enum"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [
                    "QueryNormalizeNode: defect_type_hint must be a valid enum value "
                    f"({_VALID_DEFECT_TYPES}) - free-form defect descriptions are rejected "
                    "(may carry confidential product/incident data)"
                ],
            }

        jurisdiction = state.get("jurisdiction", "jp") or "jp"
        if jurisdiction not in _VALID_JURISDICTIONS:
            jurisdiction = "jp"

        intent_type = "recall_procedure" if "recall" in user_input.lower() else "pl_compliance"

        emit_trace_event(
            "query_normalized",
            {"intent_type": intent_type, "jurisdiction": jurisdiction, "has_defect_type_hint": bool(defect_type_hint)},
            state,
        )

        return {
            "intent_type": intent_type,
            "jurisdiction": jurisdiction,
            "validated_input": to_json(
                {"query": user_input.strip(), "defect_type_hint": defect_type_hint, "jurisdiction": jurisdiction}
            ),
            "status": AgentStatus.SUCCESS.value,
        }
