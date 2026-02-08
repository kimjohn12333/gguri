#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator import db_store
from automation.orchestrator import token_guardrails as tg


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Enforce token/cost guardrails for a queue item")
    p.add_argument("--id", required=True, help="queue item id")
    p.add_argument("--report", required=True, help="path to compact report text file")
    p.add_argument("--current-tokens", required=True, type=int, help="current conversation token estimate")
    p.add_argument("--db", default="automation/orchestrator/db/queue.db", help="sqlite db path")
    p.add_argument("--soft", type=int, default=2000)
    p.add_argument("--hard", type=int, default=3500)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    report_text = Path(args.report).read_text(encoding="utf-8")
    validation = tg.validate_compact_report(report_text)
    state = tg.check_budget(args.current_tokens, soft=args.soft, hard=args.hard)
    action = tg.decide_action(state, validation["violations"])

    db_store.append_guardrail_event(
        args.db,
        args.id,
        state=state,
        action=action,
        current_tokens=args.current_tokens,
        estimated_tokens=validation["estimated_tokens"],
        violations=validation["violations"],
    )

    if action == tg.ACTION_BLOCK:
        reason = f"Guardrail BLOCK: state={state}; violations={len(validation['violations'])}"
        db_store.mark_blocked(args.db, args.id, reason)

    print(f"item={args.id} state={state} action={action} violations={len(validation['violations'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
