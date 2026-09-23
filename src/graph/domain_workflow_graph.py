"""AgentCore Platform v1.0 - MFG-C2-066 inner domain workflow graph.

Cat 2 inner graph: defect-type classification -> PL-reg KB retrieval ->
action-guide generation. Instantiated by PLComplianceGraphNode.get_subgraph()
in graph.py.

Pipeline (linear, fail-fast on ERROR):
    START -> defect_type_classify -> pl_reg_kb_retrieve -> action_guide_generate -> END
"""

from typing import Any

from langgraph.graph import END, START

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus

from src.nodes.action_guide_generate_node import ActionGuideGenerateNode
from src.nodes.defect_type_classify_node import DefectTypeClassifyNode
from src.nodes.pl_reg_kb_retrieve_node import PLRegKBRetrieveNode
from src.schemas.state import State


class PLComplianceWorkflowGraph(BaseGraph):
    """Inner graph for the MFG-C2-066 PL-law compliance Q&A workflow."""

    @property
    def name(self) -> str:
        return "mfg-pl-compliance-workflow"

    @property
    def state_schema(self) -> type:
        return State

    def _validate_config(self) -> None:
        # No mandatory config: kb/llm are optional.
        pass

    def register_nodes(self) -> None:
        # No super() - BaseGraph.register_nodes() is abstract.
        kb = self.config.get("kb")
        llm = self.config.get("llm")

        self._nodes["defect_type_classify"] = DefectTypeClassifyNode(llm=llm)
        self._nodes["pl_reg_kb_retrieve"] = PLRegKBRetrieveNode(kb=kb)
        self._nodes["action_guide_generate"] = ActionGuideGenerateNode(llm=llm)

    def add_edges(self) -> None:
        self._sg.add_edge(START, "defect_type_classify")
        self._sg.add_conditional_edges(
            "defect_type_classify",
            lambda s: END if self._is_error(s) else "pl_reg_kb_retrieve",
            {"pl_reg_kb_retrieve": "pl_reg_kb_retrieve", END: END},
        )
        self._sg.add_conditional_edges(
            "pl_reg_kb_retrieve",
            lambda s: END if self._is_error(s) else "action_guide_generate",
            {"action_guide_generate": "action_guide_generate", END: END},
        )
        self._sg.add_edge("action_guide_generate", END)

    @staticmethod
    def _is_error(state: AgentState) -> bool:
        return state.get("status") in (AgentStatus.ERROR.value, AgentStatus.ERROR.value)

    def route(self, state: AgentState) -> str:
        return END if self._is_error(state) else "action_guide_generate"

    def get_output(self, state: AgentState) -> dict[str, Any]:
        return {
            "defect_type": state.get("defect_type"),
            "kb_sub_index": state.get("kb_sub_index"),
            "pl_reg_passages": state.get("pl_reg_passages"),
            "eu_pld_crossref": state.get("eu_pld_crossref"),
            "kb_source_ref": state.get("kb_source_ref"),
            "law_citation": state.get("law_citation"),
            "required_action_steps": state.get("required_action_steps"),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
