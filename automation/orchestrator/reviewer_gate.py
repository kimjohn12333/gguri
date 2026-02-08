from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

PASS = "PASS"
RETRY = "RETRY"
BLOCK = "BLOCK"

_FAILURE_MARKERS = (
    " fail ",
    " failed",
    " error",
    " exception",
    " incomplete",
    " not done",
    " todo",
    " missing",
)
_BLOCK_MARKERS = (
    " blocker",
    " blocked",
    " cannot proceed",
    " escalation",
)
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "have",
    "has",
    "been",
    "were",
    "was",
    "will",
    "shall",
    "must",
    "should",
    "able",
    "ensure",
    "verify",
    "check",
    "tests",
    "test",
}


@dataclass(frozen=True)
class CriteriaItem:
    raw: str
    keywords: tuple[str, ...]


def _normalize(text: str) -> str:
    return " " + re.sub(r"\s+", " ", text.lower()).strip() + " "


def _split_criteria(success_criteria: str) -> list[str]:
    text = success_criteria.strip()
    if not text:
        return []
    lines = [l.strip(" -\t") for l in text.splitlines() if l.strip()]
    chunks: list[str] = []
    for line in lines:
        parts = [p.strip() for p in re.split(r"[;•]+", line) if p.strip()]
        chunks.extend(parts)
    return chunks


def _keywords(item: str) -> tuple[str, ...]:
    words = re.findall(r"[a-zA-Z0-9_\-/]{3,}", item.lower())
    picked = [w for w in words if w not in _STOPWORDS and len(w) >= 4]
    # deterministic, stable order, de-duped
    seen: set[str] = set()
    out: list[str] = []
    for w in picked:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return tuple(out[:6])


def _build_items(success_criteria: str) -> list[CriteriaItem]:
    return [CriteriaItem(raw=i, keywords=_keywords(i)) for i in _split_criteria(success_criteria)]


def _is_item_covered(item: CriteriaItem, normalized_report: str) -> bool:
    phrase = _normalize(item.raw)
    if phrase.strip() and phrase in normalized_report:
        return True
    return any(f" {kw} " in normalized_report for kw in item.keywords)


def _find_markers(normalized_report: str, markers: Iterable[str]) -> list[str]:
    found: list[str] = []
    for marker in markers:
        if marker in normalized_report:
            found.append(marker.strip())
    return found


def evaluate_result(
    success_criteria: str,
    report_text: str,
    *,
    attempt_count: int = 0,
    max_retries: int = 3,
) -> dict:
    """Deterministic gate evaluator.

    Returns dict with keys:
    - verdict: PASS|RETRY|BLOCK
    - reasons: list[str]
    - missing_checks: list[str]
    - covered_checks: int
    - total_checks: int
    """

    normalized_report = _normalize(report_text)
    items = _build_items(success_criteria)
    covered = [item for item in items if _is_item_covered(item, normalized_report)]
    missing = [item.raw for item in items if item not in covered]

    failure_markers = _find_markers(normalized_report, _FAILURE_MARKERS)
    block_markers = _find_markers(normalized_report, _BLOCK_MARKERS)

    reasons: list[str] = []
    if block_markers:
        reasons.append(f"explicit_block_marker:{','.join(block_markers)}")
        verdict = BLOCK
    elif not missing and not failure_markers:
        reasons.append("all_success_criteria_covered")
        verdict = PASS
    else:
        if missing:
            reasons.append(f"missing_checks:{len(missing)}")
        if failure_markers:
            reasons.append(f"failure_markers:{','.join(failure_markers)}")
        verdict = RETRY

    if verdict == RETRY and attempt_count >= max_retries:
        verdict = BLOCK
        reasons.append(f"retry_limit_reached:{attempt_count}/{max_retries}")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "missing_checks": missing,
        "covered_checks": len(covered),
        "total_checks": len(items),
    }
