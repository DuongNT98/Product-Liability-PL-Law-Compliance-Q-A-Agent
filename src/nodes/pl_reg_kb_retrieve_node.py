"""AgentCore Platform v1.0 - MFG-C2-066 PLRegKBRetrieveNode (inner subgraph).

VectorRAG-pattern retrieval from 製造物責任法 + METI 製品安全ガイド + 消費者庁
recall guidelines (+ optional EU PLD 2024 cross-reference), namespace
japan_pl_law. Runs after DefectTypeClassifyNode within the same inner
subgraph invocation (defect_type/kb_sub_index already in state).
"""

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.schemas.state import from_json, to_json
from src.services.service import eu_pld_crossref, retrieve_pl_reg_passages


class PLRegKBRetrieveNode(FunctionNode):
    """Retrieve 製造物責任法/METI/消費者庁 (+ opt EU PLD 2024) passages, namespace japan_pl_law."""

    # S-1: inner subgraph node - trust authenticated at outer backbone.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, kb: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._kb = kb or []

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        envelope = from_json(state.get("user_input"), {})
        jurisdiction = envelope.get("jurisdiction", "jp")
        kb_sub_index = state.get("kb_sub_index", "")

        if not kb_sub_index:
            emit_trace_event("pl_reg_kb_retrieve_rejected", {"reason": "kb_sub_index_missing"}, state)
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["PLRegKBRetrieveNode: kb_sub_index missing - DefectTypeClassifyNode must run first"],
            }

        passages = retrieve_pl_reg_passages(kb_sub_index, jurisdiction, kb=self._kb)
        crossref = eu_pld_crossref(jurisdiction, kb=self._kb)

        emit_trace_event(
            "pl_reg_kb_retrieved",
            {"kb_sub_index": kb_sub_index, "passage_count": len(passages), "has_eu_pld_crossref": bool(crossref)},
            state,
        )

        return {
            "pl_reg_passages": to_json(passages),
            "eu_pld_crossref": to_json(crossref),
            "kb_source_ref": to_json([p.get("ref_id") for p in passages]),
            "status": AgentStatus.SUCCESS.value,
        }
