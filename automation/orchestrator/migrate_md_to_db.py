#!/usr/bin/env python3
"""Migrate queue rows from QUEUE.md into sqlite queue store.

Usage:
    python3 automation/orchestrator/migrate_md_to_db.py \
      --queue automation/orchestrator/QUEUE.md \
      --db automation/orchestrator/db/queue.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from automation.orchestrator.db_store import init_db, now_kst_str
from automation.orchestrator.orch import QueueFile
import sqlite3


def migrate(queue_path: str | Path, db_path: str | Path) -> int:
    init_db(db_path)
    qf = QueueFile(Path(queue_path))
    count = 0
    with sqlite3.connect(str(db_path)) as conn:
        now = now_kst_str()
        for row in qf.rows:
            conn.execute(
                """
                INSERT INTO queue_items(
                  id, status, priority, task, success_criteria, owner_session,
                  started_at_kst, due_at_kst, notes, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status,
                  priority=excluded.priority,
                  task=excluded.task,
                  success_criteria=excluded.success_criteria,
                  owner_session=excluded.owner_session,
                  started_at_kst=excluded.started_at_kst,
                  due_at_kst=excluded.due_at_kst,
                  notes=excluded.notes,
                  updated_at=excluded.updated_at
                """,
                (
                    row.id,
                    row.status,
                    row.priority,
                    row.task,
                    row.success_criteria,
                    row.owner_session,
                    row.started_at_kst,
                    row.due_at_kst,
                    row.notes,
                    now,
                    now,
                ),
            )
            count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import QUEUE.md rows into sqlite")
    parser.add_argument("--queue", default="automation/orchestrator/QUEUE.md")
    parser.add_argument("--db", default="automation/orchestrator/db/queue.db")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    count = migrate(args.queue, args.db)
    print(f"Imported {count} rows into {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
