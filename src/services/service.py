"""AgentCore Platform v1.0 - MFG-C2-066 domain services.

Deterministic defect-type classification, 製造物責任法/METI/消費者庁 KB
sub-index retrieval (Tool layer, no LLM) + LLM-optional action-guide
synthesis (deterministic fallback per an established fleet precedent). A
recall-burst rate limiter (S-5) and the non-suppressible 弁護士 referral
notice (S-3 legal-liability control) live here as pure deterministic
helpers. The generic-only check ensures the action guide never quantifies
liability for a specific incident (no fabricated case-specific advice).
"""

from __future__ import annotations

import re
import time
from typing import Any

REFERRAL_NOTICE = (
    "本回答は一般的な製造物責任法コンプライアンス情報であり、個別事案の法的助言ではありません。"
    "個別の責任判断・エクスポージャー評価は弁護士にご相談ください。 / "
    "This is general Product Liability Act compliance information, not legal advice for a specific "
    "incident. Consult a licensed attorney for any individualized liability determination or exposure "
    "assessment."
)

_DEFECT_TYPES = ("design", "manufacturing", "instruction", "ambiguous")

# Keyword heuristics for deterministic defect-type classification (Tool layer).
_DESIGN_KEYWORDS = ("design flaw", "設計", "design defect")
_MANUFACTURING_KEYWORDS = ("manufacturing", "製造", "assembly", "production defect")
_INSTRUCTION_KEYWORDS = ("warning", "instruction", "指示", "警告", "label")

# Case-specific liability quantification is out of scope (forced to 弁護士 referral).
_INCIDENT_QUANTIFICATION_PATTERN = re.compile(
    r"\b(your (liability|exposure) is|estimated damages of|you (are|will be) liable for)\b",
    re.IGNORECASE,
)


def classify_defect_type(query: str, hint: str | None = None) -> str:
    """Deterministic defect-type classification (Tool layer, no LLM)."""
    if hint in _DEFECT_TYPES and hint != "ambiguous":
        return hint
    lower_query = query.lower()
    if any(kw in lower_query for kw in _DESIGN_KEYWORDS):
        return "design"
    if any(kw in lower_query for kw in _MANUFACTURING_KEYWORDS):
        return "manufacturing"
    if any(kw in lower_query for kw in _INSTRUCTION_KEYWORDS):
        return "instruction"
    return "ambiguous"


def kb_sub_index_for(defect_type: str) -> str:
    """Map a classified defect type to its legal-standard KB sub-index."""
    return {
        "design": "japan_pl_law.design_defect",
        "manufacturing": "japan_pl_law.manufacturing_defect",
        "instruction": "japan_pl_law.instruction_warning_defect",
    }.get(defect_type, "japan_pl_law.general")


def retrieve_pl_reg_passages(
    kb_sub_index: str,
    jurisdiction: str,
    kb: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic KB lookup for 製造物責任法/METI/消費者庁 (+ optional EU PLD) passages."""
    kb = kb or []
    matches = [entry for entry in kb if entry.get("sub_index") == kb_sub_index]
    if jurisdiction == "jp_eu_cross":
        matches += [entry for entry in kb if entry.get("sub_index") == "eu_pld_2024"]
    return matches


def eu_pld_crossref(jurisdiction: str, kb: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Optional EU PLD 2024 cross-reference (export-market add-on, off unless requested)."""
    if jurisdiction != "jp_eu_cross":
        return None
    kb = kb or []
    eu_entries = [entry for entry in kb if entry.get("sub_index") == "eu_pld_2024"]
    if not eu_entries:
        return None
    return {"ref_ids": [e.get("ref_id") for e in eu_entries]}


class ActionGuideLLMError(Exception):
    """An LLM was configured for action-guide synthesis but the call failed,
    or returned an empty/unrecognized response shape.

    This function's own contract keeps raising (never silently degrades on
    its own): a caller that wants strict configured-LLM semantics gets them.
    ActionGuideGenerateNode (the real caller) instead catches this and
    re-calls with llm=None, treating an LLM outage as a graceful degrade
    rather than a pipeline failure - see the node's own docstring."""


def _extract_llm_text(raw: Any) -> str:
    """Normalize a BaseLLM.complete() response. Canonical shape is a dict
    ({"content": str, "tool_calls": list, "model": str, "usage": {...}});
    a bare string is also accepted for backward-compat test fakes."""
    if isinstance(raw, dict):
        content = raw.get("content", "")
        return content if isinstance(content, str) else ""
    if isinstance(raw, str):
        return raw
    return ""


def generate_action_guide(
    defect_type: str,
    passages: list[dict[str, Any]],
    llm: Any | None = None,
) -> tuple[str, list[str]]:
    """Synthesize the 製造物責任法-cited action guide.

    Returns (law_citation, required_action_steps). Deterministic fallback
    when llm is None; when llm is given, raises ActionGuideLLMError on
    failure/empty response instead of silently degrading here - the caller
    decides whether that should fail the request or be treated as a
    graceful degrade (see ActionGuideGenerateNode).

    Raises:
        ActionGuideLLMError: llm is configured but complete() raised, or
            returned an empty/unrecognized response.
    """
    if llm is not None and hasattr(llm, "complete"):
        prompt = (
            "Generate generic (non-incident-specific) recall/notification action steps and a "
            f"製造物責任法 citation for defect_type={defect_type}, grounded ONLY in {passages}."
        )
        try:
            raw = llm.complete([{"role": "user", "content": prompt}])
        except Exception as exc:  # noqa: BLE001 - narrow re-raise as a typed error
            raise ActionGuideLLMError(f"LLM complete() failed: {exc}") from exc

        text = _extract_llm_text(raw).strip()
        if not text:
            raise ActionGuideLLMError("LLM complete() returned an empty/unrecognized response")

        citation = passages[0].get("law_citation", "製造物責任法") if passages else "製造物責任法"
        return citation, [text]

    # llm is None - deterministic-core mode (no LLM configured); fallback is SUCCESS.
    if not passages:
        return "", ["該当する法的基準が見つかりませんでした。弁護士にご相談ください。"]

    citation = passages[0].get("law_citation", "製造物責任法")
    steps = [f"[{p.get('ref_id', 'unknown')}] {p.get('action_step', p.get('summary', ''))}" for p in passages]
    return citation, steps


def has_incident_specific_quantification(text: str) -> bool:
    """Non-suppressible re-check: the action guide must never quantify liability
    for a specific incident (generic-only framing, S-3 legal-liability control)."""
    return bool(_INCIDENT_QUANTIFICATION_PATTERN.search(text or ""))


class RecallBurstRateLimiter:
    """Deterministic in-memory recall-burst rate limiter (S-5).

    An immutable dependency reference injected into the node constructor
    (like an LLM client or vector store) - its internal counter mutation is
    the limiter's own state, not node-instance mutable state.
    """

    def __init__(self, max_requests: int = 20, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < self._window_seconds]
        if len(hits) >= self._max_requests:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
