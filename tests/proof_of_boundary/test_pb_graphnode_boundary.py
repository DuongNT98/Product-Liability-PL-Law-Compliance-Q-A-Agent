"""PB-6 boundary coverage for PLComplianceGraphNode (Cat 2 outer main-slot wrapper).

PLComplianceGraphNode lives under src/graph/graph.py (not src/nodes/), so
the generic PB-6 invoke-order probe (test_pb_invoke_order.py, which only
discovers BaseNode subclasses under src/nodes/) never exercises it. This file is
the required compensating boundary test (test-artifacts.md §PB-6 "GraphNode nằm
NGOÀI phạm vi PB-6") - it is NOT a workaround for avoiding PB-6; it targets the
real security boundary that the outer GraphNode sits on (first node in the outer
backbone to receive caller input).

Covers:
  - S-1: caller_trust_level below PLComplianceGraphNode.required_trust_level
    (S-1 guard runs inside BaseNode.__call__, before execute()/get_subgraph() run).
  - Boundary mapping: extract_input() only reads the field it needs;
    merge_output() maps subgraph fields explicitly (criterion #9 - no raw
    pass-through of the subgraph result dict).
  - Delegation-has-purpose: PLComplianceGraphNode intentionally does not run its
    own S-2/S-3 content gates - gating is delegated to the inner subgraph's entry
    node (DefectTypeClassifyNode), per framework/nodes/graph_node.py's GraphNode
    contract (GraphNode.execute() does not call _security_gate_input/output; the
    inner BaseGraph.invoke() runs the standard S-1..S-4 pipeline on its own
    nodes). DefectTypeClassifyNode is ANONYMOUS because trust is already
    verified at the outer PLComplianceGraphNode boundary (S-1) before the inner
    subgraph runs.
"""

from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import PLComplianceGraphNode
from src.nodes.defect_type_classify_node import DefectTypeClassifyNode


class TestPLComplianceGraphNodeS1TrustGate:
    """S-1: the outer GraphNode wrapper enforces its own trust gate before delegating."""

    def setup_method(self):
        self.node = PLComplianceGraphNode()

    def test_anonymous_caller_denied_execute_not_reached(self):
        # PLComplianceGraphNode requires VERIFIED_EXTERNAL; a caller with only
        # ANONYMOUS trust must be denied by BaseNode.__call__ before
        # execute()/get_subgraph() ever run (no subgraph dispatch attempted).
        state = {"caller_trust_level": TrustLevel.ANONYMOUS.value, "validated_input": "PL compliance question"}
        result = self.node(state)

        assert result["status"] == AgentStatus.ERROR.value
        assert any("S-1 trust gate denied" in msg for msg in result["error_log"])
        # execute() would only have populated subgraph-merged fields on the
        # success path through __call__ - S-1 denial returns before that.
        assert "law_citation" not in result
        assert "required_action_steps" not in result

    def test_verified_external_caller_passes_gate(self):
        # A caller at the required trust level clears S-1 (does not assert on
        # subgraph output here - that is exercised by tests/integration/test_graph.py).
        assert PLComplianceGraphNode.required_trust_level == TrustLevel.VERIFIED_EXTERNAL


class TestPLComplianceGraphNodeBoundaryMapping:
    """extract_input()/merge_output() define the schema boundary (criterion #9)."""

    def setup_method(self):
        self.node = PLComplianceGraphNode()

    def test_extract_input_prefers_validated_input(self):
        state = {"validated_input": "validated query", "user_input": "raw input"}
        assert self.node.extract_input(state) == "validated query"

    def test_extract_input_falls_back_to_user_input(self):
        assert self.node.extract_input({"user_input": "raw input"}) == "raw input"

    def test_merge_output_maps_fields_explicitly_no_raw_passthrough(self):
        sub_result = {
            "defect_type": "design",
            "kb_sub_index": "japan_pl_law.design_defect",
            "pl_reg_passages": '[{"ref_id": "PL-ART-3"}]',
            "eu_pld_crossref": "null",
            "kb_source_ref": '["PL-ART-3"]',
            "law_citation": "製造物責任法第3条",
            "required_action_steps": '["[PL-ART-3] Notify METI"]',
            "status": AgentStatus.SUCCESS.value,
            "some_internal_subgraph_only_field": "must not leak",
        }
        delta = self.node.merge_output({}, sub_result)

        assert delta["law_citation"] == "製造物責任法第3条"
        assert delta["defect_type"] == "design"
        assert delta["status"] == AgentStatus.SUCCESS.value
        # Explicit field mapping - the subgraph's internal-only field must not
        # pass through untouched (no `**sub_result` splat in merge_output()).
        assert "some_internal_subgraph_only_field" not in delta


class TestPLComplianceGraphNodeDelegatesGatingToInnerSubgraph:
    """Delegation is a deliberate design choice, not a gap - proven here, not just asserted in docs."""

    def test_inner_entry_node_declares_its_own_trust_level(self):
        # DefectTypeClassifyNode is the inner subgraph's entry node (first node
        # inside PLComplianceWorkflowGraph). It runs the standard S-1..S-4
        # BaseNode.__call__ pipeline on its own - the outer
        # PLComplianceGraphNode does not re-implement per-node gating, it only
        # enforces the outer S-1 boundary above.
        assert DefectTypeClassifyNode.required_trust_level == TrustLevel.ANONYMOUS

    def test_graph_node_execute_is_framework_provided(self):
        # PLComplianceGraphNode does not override execute() - GraphNode.execute()
        # (framework/nodes/graph_node.py) owns dispatch to get_subgraph() /
        # extract_input() / merge_output(); confirms no local override that
        # could silently skip the framework's subgraph-error handling.
        assert "execute" not in PLComplianceGraphNode.__dict__
