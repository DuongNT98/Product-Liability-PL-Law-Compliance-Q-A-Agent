# MFG-C2-066 - Framework compliance tests TC-01..TC-08.
# Reference shape: an established fleet template's tests/unit/test_framework_compliance.py,
# adapted to this template's real architecture (Cat 2: outer pre/post + GraphNode-wrapped inner nodes).

import os
import re

from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.nodes import action_guide_generate_node, defect_type_classify_node, pl_reg_kb_retrieve_node, post_process_node, pre_process_node
from src.schemas.state import State, to_json

_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
TRUST = TrustLevel.VERIFIED_EXTERNAL.value

KB = [
    {
        "sub_index": "japan_pl_law.design_defect",
        "ref_id": "PL-ART-3",
        "law_citation": "製造物責任法第3条",
        "action_step": "Notify METI of the design defect within statutory window.",
    }
]


def _src_files():
    for root, _d, files in os.walk(_SRC):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# TC-01 - State is a flat TypedDict extending AgentState, added fields are primitives/JSON-str.
class TestTC01StateContract:
    def test_state_is_typeddict_extending_agent_state(self):
        assert hasattr(State, "__annotations__")
        assert "user_input" in State.__annotations__
        assert set(AgentState.__annotations__).issubset(set(State.__annotations__))

    def test_added_fields_are_primitives_or_json_str(self):
        added = [k for k in State.__annotations__ if k not in AgentState.__annotations__]
        assert added, "State must declare agent-specific fields"
        allowed = {"str", "int", "bool", "float"}
        for name in added:
            ann = State.__annotations__[name]
            ann_str = str(ann)
            # NotRequired[str] wraps the primitive - accept either bare name or NotRequired[...] form.
            assert any(a in ann_str for a in allowed), f"{name}: {ann_str} - compound fields must be JSON-string-encoded"


# TC-02 - Empty/missing input yields a fail-closed ERROR outcome, no raise.
class TestTC02Validation:
    def test_empty_input_no_raise(self):
        node = pre_process_node.QueryNormalizeNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]

    def test_missing_query_envelope_no_raise(self):
        node = defect_type_classify_node.DefectTypeClassifyNode()
        out = node.execute({"user_input": ""})
        assert out["status"] == AgentStatus.ERROR
        assert out["error_log"]


# TC-03 - No JWT / API keys / secrets in src/; no direct os.environ reads.
class TestTC03NoCredentials:
    def test_no_credential_literals(self):
        pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []

    def test_no_os_environ_secret_reads(self):
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                content = f.read()
                if "os.environ" in content and "server.py" not in fp:
                    offenders.append(fp)
        assert offenders == []


# TC-04 - InvocationContext is never stored in State after invoke.
class TestTC04ContextIsolation:
    def test_no_invocationcontext_in_state_after_invoke(self):
        from src.graph.graph import Graph

        agent = Graph(config={"max_retry": 1, "kb": KB})
        agent.compile()
        ctx = InvocationContext(session_id="tc04", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="staff-tc04")
        result = agent.invoke("What are our PL compliance obligations for a design defect?", ctx=ctx)
        for v in result.values():
            assert not isinstance(v, InvocationContext)

    def test_from_state_available(self):
        assert hasattr(InvocationContext, "from_state")


# TC-05 - Domain events: the S-4 side-effect node emits >=1 domain event;
# no node under src/nodes/ ever re-emits a framework backbone lifecycle event.
class TestTC05Audit:
    def test_response_validate_emits_domain_event(self, monkeypatch):
        events = []
        monkeypatch.setattr(post_process_node, "emit_trace_event", lambda e, p, s: events.append(e))
        state = {
            "law_citation": "製造物責任法第3条",
            "required_action_steps": to_json(["[PL-ART-3] Notify METI within statutory window."]),
        }
        out = post_process_node.ResponseValidateNode().execute(state)
        assert out["status"] == AgentStatus.SUCCESS
        assert len(events) >= 1
        assert "pl_compliance_query_answered" in events
        assert not ({"node_start", "node_complete", "node_error", "node_skip"} & set(events))

    def test_source_has_no_backbone_events(self):
        pat = re.compile(r'emit_trace_event\(\s*["\'](node_start|node_complete|node_error|node_skip)["\']')
        offenders = []
        for fp in _src_files():
            with open(fp, encoding="utf-8") as f:
                if pat.search(f.read()):
                    offenders.append(fp)
        assert offenders == []


# TC-06 / TC-07 - see tests/unit/test_framework_compliance_tc06_tc07.py (exact-name
# split file required by gate-scaffold-integrity REQUIRED_STG_COMPLETE).


# TC-08 - required_trust_level enforced: insufficient trust -> ERROR state, no raise.
class TestTC08TrustGate:
    def test_declared_trust_levels_valid(self):
        for cls in (
            pre_process_node.QueryNormalizeNode,
            defect_type_classify_node.DefectTypeClassifyNode,
            pl_reg_kb_retrieve_node.PLRegKBRetrieveNode,
            action_guide_generate_node.ActionGuideGenerateNode,
            post_process_node.ResponseValidateNode,
        ):
            assert cls.required_trust_level in (TrustLevel.ANONYMOUS, TrustLevel.VERIFIED_EXTERNAL, TrustLevel.INTERNAL)

    def test_insufficient_trust_returns_error(self):
        node = pre_process_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TrustLevel.ANONYMOUS.value, "user_input": "PL compliance question"})
        assert str(out.get("status")).lower().endswith("error")

    def test_sufficient_trust_succeeds(self):
        node = pre_process_node.QueryNormalizeNode()
        out = node({"caller_trust_level": TRUST, "user_input": "PL compliance question"})
        assert out["status"] == AgentStatus.SUCCESS
