#!/usr/bin/env python3
"""Natural-language intake helper for orchestrator queue.

Goal (MVP):
- Accept one natural-language request
- Produce 1..N queue rows (optionally parallel-friendly)
- Keep output deterministic and operator-auditable
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from automation.orchestrator.orch import KST, QueueFile, QueueRow

BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
SPLIT_RE = re.compile(r"\s*(?:,|;|/|→|->|그리고|및|그리고는)\s*")
ORCH_ID_RE = re.compile(r"^ORCH-(\d+)$")


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def _normalize_fragments(parts: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        c = _clean(BULLET_PREFIX_RE.sub("", p))
        if len(c) < 2:
            continue
        out.append(c)
    # dedupe while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        key = x.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(x)
    return uniq


def propose_tasks(request: str, parallel: int) -> list[str]:
    raw = request.strip()
    if not raw:
        raise ValueError("request is empty")

    # 1) line-based bullets first
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    line_frags = _normalize_fragments(lines)
    if len(line_frags) >= 2:
        return line_frags[: max(1, parallel)]

    # 2) delimiter-based split
    split_frags = _normalize_fragments(SPLIT_RE.split(raw))
    if len(split_frags) >= 2:
        return split_frags[: max(1, parallel)]

    # 3) fallback phased plan (deterministic)
    base = _clean(raw)
    phased = [
        f"요구사항 정리/설계: {base}",
        f"구현/수정: {base}",
        f"검증/문서화: {base}",
    ]
    return phased[: max(1, parallel)]


def _next_orch_id(rows: list[QueueRow]) -> str:
    max_num = 0
    for r in rows:
        m = ORCH_ID_RE.match(r.id)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"ORCH-{max_num + 1:03d}"


def _default_success_criteria(task: str) -> str:
    short = task if len(task) <= 28 else f"{task[:28]}..."
    return f"{short} 수행 완료 + 변경사항/검증결과 notes 기록"


def cmd_plan(args: argparse.Namespace) -> int:
    tasks = propose_tasks(args.request, args.parallel)
    print(f"request: {args.request.strip()}")
    print(f"parallel: {args.parallel}")
    for i, t in enumerate(tasks, start=1):
        print(f"{i}. {t}")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    qf = QueueFile(Path(args.queue))
    tasks = propose_tasks(args.request, args.parallel)

    now_tag = datetime.now(KST).strftime("%Y%m%d-%H%M")
    ids: list[str] = []

    for task in tasks:
        row_id = _next_orch_id(qf.rows)
        ids.append(row_id)
        qf.rows.append(
            QueueRow(
                id=row_id,
                status="PENDING",
                priority=args.priority,
                task=task,
                success_criteria=args.success_criteria or _default_success_criteria(task),
                owner_session="-",
                started_at_kst="-",
                due_at_kst=args.due_at_kst or "-",
                notes=f"nl_intake:{now_tag}",
            )
        )

    qf.save()

    print(f"created={len(ids)} ids={','.join(ids)}")
    for i, (row_id, task) in enumerate(zip(ids, tasks), start=1):
        print(f"{i}. {row_id} | {task}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Natural-language intake for orchestrator queue")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")

    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--request", required=True, help="Natural-language request")
    common.add_argument("--parallel", type=int, default=3, help="Max number of task rows to generate")

    plan = sub.add_parser("plan", parents=[common], help="Preview decomposition only")
    plan.set_defaults(func=cmd_plan)

    submit = sub.add_parser("submit", parents=[common], help="Write decomposed tasks to queue")
    submit.add_argument("--priority", choices=["P0", "P1", "P2"], default="P1")
    submit.add_argument("--due-at-kst")
    submit.add_argument("--success-criteria", help="Apply same success criteria to all generated tasks")
    submit.set_defaults(func=cmd_submit)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.parallel < 1:
        raise ValueError("--parallel must be >= 1")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
