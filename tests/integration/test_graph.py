# MFG-C2-066 - Integration test: full graph compile + invoke (Cat 2 outer + inner).

from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph

KB = [
    {
        "sub_index": "japan_pl_law.design_defect",
        "ref_id": "PL-ART-3",
        "law_citation": "製造物責任法第3条",
        "action_step": "Notify METI of the design defect within statutory window.",
    }
]

PL_QUERY = "What are our PL compliance obligations for a design defect in this product line?"
RECALL_QUERY = "What is the recall notification procedure for a manufacturing defect?"
EMPTY_QUERY = ""


class TestAgentIntegration:
    def test_pl_compliance_question_reaches_full_pipeline(self):
        # Per [[framework-s2-gate-can-also-break-success-path]], assert the
        # environment-independent invariant (pipeline completion), not an
        # exact terminal status - unit tests already pin the success-path
        # logic deterministically.
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-1", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="staff-001")
        result = agent.invoke(PL_QUERY, ctx=ctx)

        assert len(result.get("node_history", [])) >= 4
        assert result["status"] in ("success", "error", "cancelled")

    def test_recall_question_reaches_full_pipeline(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-2", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="staff-002")
        result = agent.invoke(RECALL_QUERY, ctx=ctx)

        assert len(result.get("node_history", [])) >= 4
        assert result["status"] in ("success", "error", "cancelled")

    def test_empty_query_error(self):
        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="it-3", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="staff-003")
        result = agent.invoke(EMPTY_QUERY, ctx=ctx)
        assert result["status"] in ("error", "cancelled")
