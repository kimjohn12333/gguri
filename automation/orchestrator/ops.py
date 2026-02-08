#!/usr/bin/env python3
"""Operator CLI for orchestrator queue operations."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Iterable

from automation.orchestrator import config, db_store
from automation.orchestrator.orch import QueueFile, now_kst_str

TOP_IN_PROGRESS = config.TOP_IN_PROGRESS_DISPLAY


def _append_note(existing: str, msg: str) -> str:
    msg = msg.strip()
    if not existing.strip():
        return msg
    return f"{existing.strip()} | {msg}"


def _status_summary(rows: Iterable[dict[str, str]]) -> str:
    rows = list(rows)
    counts = Counter(r["status"] for r in rows)
    order = ["PENDING", "IN_PROGRESS", "BLOCKED", "FAILED", "DONE"]
    summary = " ".join(f"{k}={counts.get(k, 0)}" for k in order)

    in_progress = [r for r in rows if r["status"] == "IN_PROGRESS"][:TOP_IN_PROGRESS]
    lines = [f"summary {summary}"]
    if not in_progress:
        lines.append("top_in_progress: none")
    else:
        lines.append("top_in_progress:")
        for row in in_progress:
            lines.append(f"- {row['id']} ({row['priority']}) owner={row['owner_session']} started={row['started_at_kst']}")
    return "\n".join(lines)


def _workers_summary(rows: Iterable[dict[str, str]]) -> str:
    rows = list(rows)
    in_progress = [r for r in rows if r["status"] == "IN_PROGRESS"]
    if not in_progress:
        return "workers: none"

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in in_progress:
        owner = row.get("owner_session") or "-"
        grouped.setdefault(owner, []).append(row)

    lines = [f"workers_active={len(grouped)} in_progress={len(in_progress)}"]
    for owner in sorted(grouped):
        tasks = grouped[owner]
        ids = ",".join(r["id"] for r in tasks)
        oldest = next((r.get("started_at_kst", "-") for r in tasks if r.get("started_at_kst") and r.get("started_at_kst") != "-"), "-")
        priorities = Counter((r.get("priority") or "P2") for r in tasks)
        lines.append(
            f"- {owner} tasks={len(tasks)} p0={priorities.get('P0', 0)} p1={priorities.get('P1', 0)} p2={priorities.get('P2', 0)} ids={ids} oldest_start={oldest}"
        )
    return "\n".join(lines)


def cmd_status_md(queue_path: Path) -> int:
    qf = QueueFile(queue_path)
    rows = [
        {
            "id": r.id,
            "status": r.status,
            "priority": r.priority,
            "owner_session": r.owner_session,
            "started_at_kst": r.started_at_kst,
        }
        for r in qf.rows
    ]
    print(_status_summary(rows))
    return 0


def cmd_workers_md(queue_path: Path) -> int:
    qf = QueueFile(queue_path)
    rows = [
        {
            "id": r.id,
            "status": r.status,
            "priority": r.priority,
            "owner_session": r.owner_session,
            "started_at_kst": r.started_at_kst,
        }
        for r in qf.rows
    ]
    print(_workers_summary(rows))
    return 0


def cmd_cancel_md(queue_path: Path, item_id: str) -> int:
    qf = QueueFile(queue_path)
    row = qf.find_by_id(item_id)
    if row.status in {"DONE", "FAILED"}:
        raise ValueError(f"cannot cancel terminal item: {item_id} ({row.status})")
    row.status = "BLOCKED"
    row.notes = _append_note(row.notes, "cancelled_by_operator")
    qf.save()
    print(f"{item_id} -> BLOCKED")
    return 0


def cmd_replan_md(queue_path: Path, item_id: str, notes: str) -> int:
    qf = QueueFile(queue_path)
    row = qf.find_by_id(item_id)
    row.status = "BLOCKED" if row.status == "IN_PROGRESS" else "PENDING"
    row.notes = _append_note(row.notes, f"replan:{notes.strip()}")
    qf.save()
    print(f"{item_id} -> {row.status}")
    return 0


def cmd_retry_md(queue_path: Path, item_id: str) -> int:
    qf = QueueFile(queue_path)
    row = qf.find_by_id(item_id)
    if row.status not in {"FAILED", "BLOCKED"}:
        raise ValueError(f"retry allowed only for FAILED/BLOCKED in markdown mode: {item_id} ({row.status})")
    row.status = "PENDING"
    row.owner_session = "-"
    row.started_at_kst = "-"
    row.notes = _append_note(row.notes, "retry_requested")
    qf.save()
    print(f"{item_id} -> PENDING")
    return 0


def _db_row(path: Path, item_id: str) -> dict:
    items = [x for x in db_store.list_items(path) if x["id"] == item_id]
    if not items:
        raise ValueError(f"Row id not found: {item_id}")
    return items[0]


def cmd_status_db(db_path: Path) -> int:
    rows = db_store.list_items(db_path)
    print(_status_summary(rows))
    return 0


def cmd_workers_db(db_path: Path) -> int:
    rows = db_store.list_items(db_path)
    print(_workers_summary(rows))
    return 0


def cmd_cancel_db(db_path: Path, item_id: str) -> int:
    row = _db_row(db_path, item_id)
    if row["status"] in {"DONE", "FAILED"}:
        raise ValueError(f"cannot cancel terminal item: {item_id} ({row['status']})")
    notes = _append_note(row.get("notes", ""), "cancelled_by_operator")
    db_store.mark_blocked(db_path, item_id, notes)
    print(f"{item_id} -> BLOCKED")
    return 0


def cmd_replan_db(db_path: Path, item_id: str, notes: str) -> int:
    row = _db_row(db_path, item_id)
    next_status = "BLOCKED" if row["status"] == "IN_PROGRESS" else "PENDING"
    merged_notes = _append_note(row.get("notes", ""), f"replan:{notes.strip()}")

    if next_status == "BLOCKED":
        db_store.mark_blocked(db_path, item_id, merged_notes)
    else:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status='PENDING',
                    owner_session='-',
                    started_at_kst='-',
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    notes=?,
                    updated_at=?
                WHERE id=?
                """,
                (merged_notes, now_kst_str(), item_id),
            )
        db_store.append_event(db_path, item_id, "replan", {"status": "PENDING", "notes": merged_notes})
    print(f"{item_id} -> {next_status}")
    return 0


def cmd_retry_db(db_path: Path, item_id: str, now_ts: int | None = None) -> int:
    row = _db_row(db_path, item_id)
    attempts = int(row.get("attempt_count") or 0)
    max_attempts = int(row.get("max_attempts") or 3)
    if attempts >= max_attempts:
        raise ValueError(f"max attempts reached: {item_id} ({attempts}/{max_attempts})")

    status = row["status"]
    now_epoch = now_ts if now_ts is not None else db_store.now_epoch()
    lease_expires_at = row.get("lease_expires_at")
    timed_out = status == "IN_PROGRESS" and lease_expires_at is not None and int(lease_expires_at) <= now_epoch
    if status != "FAILED" and not timed_out:
        raise ValueError(f"retry allowed only for FAILED or timed-out IN_PROGRESS in db mode: {item_id} ({status})")

    backoff = db_store.RETRY_BACKOFF_SECONDS[min(attempts, len(db_store.RETRY_BACKOFF_SECONDS) - 1)]
    notes = _append_note(row.get("notes", ""), f"retry_not_before={now_epoch + backoff}")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE queue_items
            SET status='PENDING',
                owner_session='-',
                started_at_kst='-',
                lease_owner=NULL,
                lease_expires_at=NULL,
                attempt_count=attempt_count+1,
                notes=?,
                updated_at=?
            WHERE id=?
            """,
            (notes, now_kst_str(), item_id),
        )
    db_store.append_event(db_path, item_id, "retried", {"reason": "operator_retry"})
    print(f"{item_id} -> PENDING")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Orchestrator operator CLI")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md", help="Queue markdown path")
    p.add_argument("--db", help="SQLite queue DB path")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Summary by status + top in-progress")
    sub.add_parser("workers", help="Owner-session(worker) distribution for IN_PROGRESS items")

    cancel = sub.add_parser("cancel", help="Cancel an active item (moves to BLOCKED)")
    cancel.add_argument("--id", required=True)

    replan = sub.add_parser("replan", help="Apply replan note and status transition")
    replan.add_argument("--id", required=True)
    replan.add_argument("--notes", required=True)

    retry = sub.add_parser("retry", help="Move eligible item back to PENDING")
    retry.add_argument("--id", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else None
    queue_path = Path(args.queue)

    if args.command == "status":
        return cmd_status_db(db_path) if db_path else cmd_status_md(queue_path)
    if args.command == "workers":
        return cmd_workers_db(db_path) if db_path else cmd_workers_md(queue_path)
    if args.command == "cancel":
        return cmd_cancel_db(db_path, args.id) if db_path else cmd_cancel_md(queue_path, args.id)
    if args.command == "replan":
        return cmd_replan_db(db_path, args.id, args.notes) if db_path else cmd_replan_md(queue_path, args.id, args.notes)
    if args.command == "retry":
        return cmd_retry_db(db_path, args.id) if db_path else cmd_retry_md(queue_path, args.id)

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
