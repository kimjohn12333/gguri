#!/usr/bin/env python3
"""Watchdog execution entrypoint.

MVP behavior:
- DB mode: use retry_eligible_items for FAILED / stale IN_PROGRESS
- Markdown mode: reset stale IN_PROGRESS to PENDING by age
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automation.orchestrator import config, db_store
from automation.orchestrator.orch import QueueFile
from automation.orchestrator.ops import _append_note

KST = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))


def _parse_kst(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s or s == "-":
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=KST)
    except ValueError:
        return None


def _run_md(queue_path: Path, stale_minutes: int) -> list[str]:
    qf = QueueFile(queue_path)
    now = datetime.now(KST)
    stale_cutoff = now - timedelta(minutes=stale_minutes)

    reset_ids: list[str] = []
    for row in qf.rows:
        if row.status != "IN_PROGRESS":
            continue
        started = _parse_kst(row.started_at_kst)
        if started is None or started > stale_cutoff:
            continue

        row.status = "PENDING"
        row.owner_session = "-"
        row.started_at_kst = "-"
        row.notes = _append_note(row.notes, "[watchdog] stale reset")
        reset_ids.append(row.id)

    if reset_ids:
        qf.save()
    return reset_ids


def _run_db(db_path: Path) -> list[str]:
    return db_store.retry_eligible_items(db_path)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Orchestrator watchdog entrypoint")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")
    p.add_argument("--db", help="SQLite queue path (preferred when set)")
    p.add_argument("--stale-minutes", type=int, default=60)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ids = _run_db(Path(args.db)) if args.db else _run_md(Path(args.queue), args.stale_minutes)
    if not ids:
        print("NOOP")
        return 0
    print("RESET " + ",".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
