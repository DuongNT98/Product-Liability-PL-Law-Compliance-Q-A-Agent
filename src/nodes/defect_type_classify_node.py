"""AgentCore Platform v1.0 - MFG-C2-066 DefectTypeClassifyNode (inner subgraph).

Classifies the defect type (design/manufacturing/instruction/ambiguous) and
routes to the corresponding legal-standard KB sub-index - the legal
standard applied differs by defect type. Runs first in the inner subgraph.
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json
from src.services.service import classify_defect_type, kb_sub_index_for


class DefectTypeClassifyNode(FunctionNode):
    """Classify defect type -> route to the correct legal-standard KB sub-index."""

    # S-1: inner subgraph node - trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        envelope = from_json(state.get("user_input"), {})
        query = envelope.get("query", "")
        defect_type_hint = envelope.get("defect_type_hint", "")

        if not query:
            emit_trace_event("defect_type_classify_rejected", {"reason": "query_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DefectTypeClassifyNode: query missing from envelope"],
            }

        defect_type = classify_defect_type(query, hint=defect_type_hint or None)
        kb_sub_index = kb_sub_index_for(defect_type)

        emit_trace_event("defect_type_classified", {"defect_type": defect_type, "kb_sub_index": kb_sub_index}, state)

        return {
            "defect_type": defect_type,
            "kb_sub_index": kb_sub_index,
            "status": AgentStatus.SUCCESS.value,
        }
