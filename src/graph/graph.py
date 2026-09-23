"""AgentCore Platform v1.0 - MFG-C2-066 outer graph (Cat 2).

Cat 2: outer AgentBaseGraph with the fixed 5-node backbone. Domain
complexity is encapsulated in PLComplianceGraphNode (the `main` slot),
which wraps the inner PLComplianceWorkflowGraph. Do NOT override
add_edges().

Backbone: initialize -> pre_process(QueryNormalizeNode) ->
          main(GraphNode) -> post_process(ResponseValidateNode) -> finalize

PLComplianceGraphNode lives here (not under src/nodes/) - the PB-6
invoke-order test only discovers BaseNode subclasses under src/nodes/,
and a GraphNode's __call__ intentionally skips the standard S-2/S-4/S-3
lifecycle (gating is delegated to the inner subgraph). This outer
boundary is still exercised directly - see
tests/proof_of_boundary/test_pb_graphnode_boundary.py.
"""

from typing import Any, ClassVar, cast

from framework.graph.agent_base_graph import AgentBaseGraph
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.nodes.post_process_node import ResponseValidateNode
from src.nodes.pre_process_node import QueryNormalizeNode
from src.schemas.state import State


class PLComplianceGraphNode(GraphNode):
    """Wraps the inner defect-classify/KB-retrieve/action-guide workflow (Cat 2 composition)."""

    # S-1: outer main-slot wrapper - first node in the outer backbone receiving
    # caller input directly (matches agent.yaml required_trust_level + sibling
    # outer QueryNormalizeNode/ResponseValidateNode).
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL
    # "propagate": re-raise inner errors as SubgraphError (fail fast - default).
    error_strategy: ClassVar[str] = "propagate"
    # No HITL in this template.
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, kb: list[dict[str, Any]] | None = None, llm: Any = None) -> None:
        super().__init__()
        self._kb = kb or []
        self._llm = llm

    def get_subgraph(self) -> Any:
        from src.graph.domain_workflow_graph import PLComplianceWorkflowGraph

        sg = PLComplianceWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        emit_trace_event(
            "pl_compliance_workflow_dispatched", {"correlation_id": state.get("correlation_id", "")}, state
        )
        return cast(str, state.get("validated_input", state.get("user_input", "")))

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        emit_trace_event(
            "pl_compliance_workflow_completed",
            {"correlation_id": state.get("correlation_id", ""), "status": str(sub_result.get("status"))},
            state,
        )
        return {
            "defect_type": sub_result.get("defect_type"),
            "kb_sub_index": sub_result.get("kb_sub_index"),
            "pl_reg_passages": sub_result.get("pl_reg_passages"),
            "eu_pld_crossref": sub_result.get("eu_pld_crossref"),
            "kb_source_ref": sub_result.get("kb_source_ref"),
            "law_citation": sub_result.get("law_citation"),
            "required_action_steps": sub_result.get("required_action_steps"),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        return {"kb": self._kb, "llm": self._llm}


class MFGPLComplianceAgent(AgentBaseGraph):
    """MFG-C2-066 - Product Liability & PL Law Compliance Q&A Agent (Cat 2)."""

    @property
    def name(self) -> str:
        return "mfg-c2-066"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # injects initialize + finalize

        kb = self.config.get("kb")
        llm = self.config.get("llm")

        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = PLComplianceGraphNode(kb=kb, llm=llm)
        self._nodes["post_process"] = ResponseValidateNode()

    # add_edges() is NOT overridden - backbone wiring belongs to the framework.


# Alias for agent.yaml module:"src.graph" resolution (AgentRegistry / api/server.py).
Graph = MFGPLComplianceAgent
