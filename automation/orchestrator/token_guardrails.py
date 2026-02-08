from __future__ import annotations

import math
from typing import Any


STATE_OK = "OK"
STATE_SOFT_EXCEEDED = "SOFT_EXCEEDED"
STATE_HARD_EXCEEDED = "HARD_EXCEEDED"

ACTION_ALLOW = "ALLOW"
ACTION_SUMMARIZE = "SUMMARIZE"
ACTION_BLOCK = "BLOCK"

_REQUIRED_SECTIONS = ["Status:", "Files:", "Diff-Summary:", "Validation:", "Risks:", "Next:"]


def estimate_report_size(text: str) -> int:
    """Estimate token count using a simple deterministic heuristic.

    Heuristic: ceil(char_count / 4), commonly used as rough upper estimate for mixed text.
    """
    if not text:
        return 0
    return int(math.ceil(len(text) / 4.0))


def _violation(code: str, message: str, severity: str = "medium") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def validate_compact_report(text: str) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    estimated_tokens = estimate_report_size(text)

    lines = text.splitlines()
    non_empty = [ln.strip() for ln in lines if ln.strip()]

    if not non_empty:
        violations.append(_violation("EMPTY", "report is empty", "high"))
    else:
        first = non_empty[0]
        if not (first.startswith("[REPORT ") and first.endswith("]")):
            violations.append(_violation("MISSING_REPORT_HEADER", "first line must be [REPORT <task-id>]", "high"))

    # Strong anti-paste guardrails
    if "```" in text:
        violations.append(_violation("CODE_FENCE_FORBIDDEN", "full code/log paste is forbidden in compact report", "high"))
    if len(text) > 8000:
        violations.append(_violation("REPORT_TOO_LONG", "report text too long for compact policy", "high"))

    section_indices: dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        for sec in _REQUIRED_SECTIONS:
            if stripped.startswith(sec) and sec not in section_indices:
                section_indices[sec] = idx

    for sec in _REQUIRED_SECTIONS:
        if sec not in section_indices:
            violations.append(_violation("MISSING_SECTION", f"missing required section: {sec}", "high"))

    # Section order check only when present.
    last = -1
    for sec in _REQUIRED_SECTIONS:
        if sec in section_indices:
            cur = section_indices[sec]
            if cur < last:
                violations.append(_violation("SECTION_ORDER", f"section out of order: {sec}", "medium"))
            last = cur

    bullet_count = sum(1 for ln in lines if ln.lstrip().startswith("- "))
    if bullet_count > 10:
        violations.append(_violation("TOO_MANY_BULLETS", "bullet count exceeds policy recommendation (10)", "medium"))

    def _section_has_bullet(section: str) -> bool:
        if section not in section_indices:
            return False
        start = section_indices[section] + 1
        end = len(lines)
        for sec in _REQUIRED_SECTIONS:
            if sec in section_indices and section_indices[sec] > section_indices[section]:
                end = min(end, section_indices[sec])
        return any(lines[i].lstrip().startswith("- ") for i in range(start, end))

    if "Files:" in section_indices and not _section_has_bullet("Files:"):
        violations.append(_violation("FILES_EMPTY", "Files section must contain at least one bullet path", "high"))
    if "Diff-Summary:" in section_indices and not _section_has_bullet("Diff-Summary:"):
        violations.append(_violation("DIFF_SUMMARY_EMPTY", "Diff-Summary section must contain at least one bullet", "high"))

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "estimated_tokens": estimated_tokens,
    }


def check_budget(current_tokens: int, soft: int = 2000, hard: int = 3500) -> str:
    if current_tokens > hard:
        return STATE_HARD_EXCEEDED
    if current_tokens > soft:
        return STATE_SOFT_EXCEEDED
    return STATE_OK


def decide_action(state: str, violations: list[dict[str, str]]) -> str:
    has_severe = any(v.get("severity") == "high" for v in violations)
    if state == STATE_HARD_EXCEEDED or has_severe:
        return ACTION_BLOCK
    if state == STATE_SOFT_EXCEEDED or violations:
        return ACTION_SUMMARIZE
    return ACTION_ALLOW
