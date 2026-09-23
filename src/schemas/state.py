"""AgentCore Platform v1.0 - MFG-C2-066 state schema.

Product Liability & PL Law Compliance Q&A Agent. Flat TypedDict extension
of AgentState (ADR-005). Structured payloads (dict/list) are JSON-string-
encoded before being stored in state fields (compound values are never
stored as raw dict/list per ADR-005).
"""

import json
from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class State(AgentState):
    """Agent state for MFG-C2-066.

    defect_type_hint: caller-supplied raw defect type hint (enum-validated
      by QueryNormalizeNode before use; free-form defect text is rejected).
    jurisdiction: optional caller-supplied jurisdiction ("jp" | "jp_eu_cross").
    intent_type: normalized query intent ("pl_compliance" | "recall_procedure"
      | "liability_framing").
    defect_type: classified defect type ("design" | "manufacturing" |
      "instruction" | "ambiguous").
    kb_sub_index: legal-standard KB sub-index the defect type routed to.
    pl_reg_passages: JSON list[dict] of retrieved 製造物責任法/METI/消費者庁 passages.
    law_citation: 製造物責任法 article citation for the answer.
    required_action_steps: JSON list[str] of recall/notification action steps.
    eu_pld_crossref: JSON dict|None - EU PLD 2024 cross-reference when requested.
    liability_framing_note: generic-only liability framing note (never an
      individualized liability determination).
    legal_advisor_referral_notice: non-suppressible 弁護士 referral notice.
    kb_source_ref: JSON list[str] of cited KB source ref_ids.
    """

    # AgentState is a TypedDict at runtime, but mypy can't see that without SDK
    # stubs (framework/ ships no py.typed marker), so it rejects NotRequired[...]
    # as used outside a TypedDict definition. Scoped ignore per field - a
    # stub-visibility limitation, not a code error; each field really is
    # optional/JSON-safe at runtime.
    defect_type_hint: NotRequired[str]  # type: ignore[valid-type]
    jurisdiction: NotRequired[str]  # type: ignore[valid-type]
    intent_type: NotRequired[str]  # type: ignore[valid-type]
    defect_type: NotRequired[str]  # type: ignore[valid-type]
    kb_sub_index: NotRequired[str]  # type: ignore[valid-type]
    pl_reg_passages: NotRequired[str]  # type: ignore[valid-type]
    law_citation: NotRequired[str]  # type: ignore[valid-type]
    required_action_steps: NotRequired[str]  # type: ignore[valid-type]
    eu_pld_crossref: NotRequired[str]  # type: ignore[valid-type]
    liability_framing_note: NotRequired[str]  # type: ignore[valid-type]
    legal_advisor_referral_notice: NotRequired[str]  # type: ignore[valid-type]
    kb_source_ref: NotRequired[str]  # type: ignore[valid-type]
