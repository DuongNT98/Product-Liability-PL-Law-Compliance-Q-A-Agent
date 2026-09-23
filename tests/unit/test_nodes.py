# MFG-C2-066 - Unit tests: per-node success + error/edge paths.

from framework.schemas.agent_status import AgentStatus

from src.nodes.action_guide_generate_node import ActionGuideGenerateNode
from src.nodes.defect_type_classify_node import DefectTypeClassifyNode
from src.nodes.pl_reg_kb_retrieve_node import PLRegKBRetrieveNode
from src.nodes.post_process_node import ResponseValidateNode
from src.nodes.pre_process_node import QueryNormalizeNode
from src.schemas.state import from_json, to_json

KB = [
    {
        "sub_index": "japan_pl_law.design_defect",
        "ref_id": "PL-ART-3",
        "law_citation": "製造物責任法第3条",
        "action_step": "Notify METI of the design defect within statutory window.",
    }
]


class TestQueryNormalizeNode:
    def test_success_pl_compliance(self):
        state = {"user_input": "What are our PL compliance obligations for a design defect?"}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["intent_type"] == "pl_compliance"

    def test_success_recall_intent(self):
        state = {"user_input": "What is the recall procedure for this product?"}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["intent_type"] == "recall_procedure"

    def test_empty_input_error(self):
        assert QueryNormalizeNode().execute({"user_input": ""})["status"] == AgentStatus.ERROR

    def test_invalid_defect_type_hint_rejected(self):
        state = {"user_input": "question", "defect_type_hint": "the airbag exploded on 2026-01-01 in unit #4521"}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.ERROR

    def test_valid_defect_type_hint_accepted(self):
        state = {"user_input": "question", "defect_type_hint": "design"}
        r = QueryNormalizeNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        envelope = from_json(r["validated_input"], {})
        assert envelope["defect_type_hint"] == "design"


class TestDefectTypeClassifyNode:
    def test_success_design_defect(self):
        envelope = {"query": "This has a design flaw", "defect_type_hint": ""}
        state = {"user_input": to_json(envelope)}
        r = DefectTypeClassifyNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["defect_type"] == "design"
        assert r["kb_sub_index"] == "japan_pl_law.design_defect"

    def test_success_ambiguous_defaults(self):
        envelope = {"query": "generic compliance question", "defect_type_hint": ""}
        state = {"user_input": to_json(envelope)}
        r = DefectTypeClassifyNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["defect_type"] == "ambiguous"

    def test_missing_query_error(self):
        assert DefectTypeClassifyNode().execute({"user_input": ""})["status"] == AgentStatus.ERROR


class TestPLRegKBRetrieveNode:
    def test_success_retrieves_passages(self):
        envelope = {"query": "design defect question", "jurisdiction": "jp"}
        state = {"user_input": to_json(envelope), "kb_sub_index": "japan_pl_law.design_defect"}
        r = PLRegKBRetrieveNode(kb=KB).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert len(from_json(r["pl_reg_passages"], [])) == 1

    def test_missing_kb_sub_index_error(self):
        state = {"user_input": to_json({"query": "q", "jurisdiction": "jp"})}
        assert PLRegKBRetrieveNode(kb=KB).execute(state)["status"] == AgentStatus.ERROR


class _FakeLLM:
    """Test-double for Azure OpenAI wiring - never a real network call."""

    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise_exc = raise_exc
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._response


class TestActionGuideGenerateNode:
    def test_success_generates_citation(self):
        # Real production shape: no constructor override, no InvocationContext
        # bound secrets - _resolve_llm swallows the resulting error and returns
        # None, so this exercises the deterministic fallback.
        state = {"defect_type": "design", "pl_reg_passages": to_json(KB)}
        r = ActionGuideGenerateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["law_citation"] == "製造物責任法第3条"

    def test_missing_defect_type_error(self):
        assert ActionGuideGenerateNode().execute({"pl_reg_passages": to_json([])})["status"] == AgentStatus.ERROR

    def test_missing_defect_type_never_calls_llm(self):
        llm = _FakeLLM(raise_exc=AssertionError("must not be called with no defect_type"))
        r = ActionGuideGenerateNode(llm=llm).execute({"pl_reg_passages": to_json([])})
        assert r["status"] == AgentStatus.ERROR
        assert llm.calls == 0

    def test_llm_override_generates_from_response(self):
        llm = _FakeLLM(response={"content": "Notify METI within 10 business days per 製造物責任法."})
        state = {"defect_type": "design", "pl_reg_passages": to_json(KB)}
        r = ActionGuideGenerateNode(llm=llm).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert llm.calls == 1
        assert "Notify METI" in from_json(r["required_action_steps"], [])[0]

    def test_llm_prose_response_accepted_as_is(self):
        llm = _FakeLLM(response={"content": "```\nStep 1: notify authorities.\n```"})
        state = {"defect_type": "manufacturing", "pl_reg_passages": to_json(KB)}
        r = ActionGuideGenerateNode(llm=llm).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert llm.calls == 1

    def test_llm_empty_response_degrades_to_deterministic(self):
        llm = _FakeLLM(response={"content": ""})
        state = {"defect_type": "design", "pl_reg_passages": to_json(KB)}
        r = ActionGuideGenerateNode(llm=llm).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["law_citation"] == "製造物責任法第3条"

    def test_llm_raises_degrades_to_deterministic(self):
        llm = _FakeLLM(raise_exc=RuntimeError("Azure OpenAI timeout"))
        state = {"defect_type": "design", "pl_reg_passages": to_json(KB)}
        r = ActionGuideGenerateNode(llm=llm).execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["law_citation"] == "製造物責任法第3条"


class TestResponseValidateNode:
    def test_success_includes_referral_notice(self):
        state = {
            "law_citation": "製造物責任法第3条",
            "required_action_steps": to_json(["[PL-ART-3] Notify METI within statutory window."]),
        }
        r = ResponseValidateNode().execute(state)
        assert r["status"] == AgentStatus.SUCCESS
        assert r["legal_advisor_referral_notice"] in r["formatted_output"]

    def test_extra_gate_blocks_missing_referral_notice(self):
        bad_state = {"formatted_output": "some answer without the notice"}
        out = ResponseValidateNode()._extra_security_gate_output(bad_state)
        assert out["status"] == AgentStatus.ERROR

    def test_extra_gate_blocks_incident_quantification(self):
        from src.services.service import REFERRAL_NOTICE

        bad_state = {"formatted_output": f"your liability is significant.\n\n{REFERRAL_NOTICE}"}
        out = ResponseValidateNode()._extra_security_gate_output(bad_state)
        assert out["status"] == AgentStatus.ERROR

    def test_extra_gate_passthrough_valid_answer(self):
        from src.services.service import REFERRAL_NOTICE

        good_state = {"formatted_output": f"[PL-ART-3] Notify METI.\n\n{REFERRAL_NOTICE}"}
        assert ResponseValidateNode()._extra_security_gate_output(good_state) is good_state
