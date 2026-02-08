#!/usr/bin/env python3
"""Dispatcher execution entrypoint.

MVP behavior:
- Pick one eligible PENDING item
- Mark as IN_PROGRESS with owner_session
- Print picked id (or NOOP)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator import db_store
from automation.orchestrator.orch import PRIORITY_ORDER, QueueFile, now_kst_str


def _pick_md(queue_path: Path, owner_session: str) -> str | None:
    qf = QueueFile(queue_path)
    pending = [r for r in qf.rows if r.status == "PENDING"]
    if not pending:
        return None

    pending.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    row = pending[0]
    row.status = "IN_PROGRESS"
    row.owner_session = owner_session
    row.started_at_kst = now_kst_str()
    qf.save()
    return row.id


def _pick_db(db_path: Path, owner_session: str) -> str | None:
    row = db_store.pick_next(db_path, owner_session=owner_session)
    if not row:
        return None
    return str(row["id"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Orchestrator dispatcher entrypoint")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")
    p.add_argument("--db", help="SQLite queue path (preferred when set)")
    p.add_argument("--owner-session", default="dispatcher")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    picked = _pick_db(Path(args.db), args.owner_session) if args.db else _pick_md(Path(args.queue), args.owner_session)

    if not picked:
        print("NOOP")
        return 0

    print(picked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
