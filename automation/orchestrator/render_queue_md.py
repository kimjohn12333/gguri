#!/usr/bin/env python3
"""Render QUEUE.md table from SQLite queue (DB as source).

This keeps markdown as a readable view while DB remains operational source.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator import db_store
from automation.orchestrator.orch import QueueFile, QueueRow


def _row_from_db(item: dict) -> QueueRow:
    return QueueRow(
        id=str(item.get("id", "")),
        status=str(item.get("status", "")),
        priority=str(item.get("priority", "")),
        task=str(item.get("task", "")),
        success_criteria=str(item.get("success_criteria", "")),
        owner_session=str(item.get("owner_session", "-")),
        started_at_kst=str(item.get("started_at_kst", "-")),
        due_at_kst=str(item.get("due_at_kst", "-")),
        notes=str(item.get("notes", "")),
    )


def render(db_path: Path, queue_path: Path) -> int:
    rows = db_store.list_items(db_path)
    qf = QueueFile(queue_path)
    qf.rows = [_row_from_db(r) for r in rows]
    qf.save()
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render QUEUE.md from sqlite queue")
    p.add_argument("--db", default="automation/orchestrator/db/queue.db")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = render(Path(args.db), Path(args.queue))
    print(f"rendered {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
