#!/usr/bin/env python3
"""Operator CLI for orchestrator queue operations."""

from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from automation.orchestrator import config, db_store, metrics_aggregate
from automation.orchestrator.orch import QueueFile, now_kst_str

TOP_IN_PROGRESS = config.TOP_IN_PROGRESS_DISPLAY
KST = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))


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


def _rows_from_md(queue_path: Path) -> list[dict[str, str]]:
    qf = QueueFile(queue_path)
    return [
        {
            "id": r.id,
            "status": r.status,
            "priority": r.priority,
            "task": r.task,
            "owner_session": r.owner_session,
            "started_at_kst": r.started_at_kst,
            "due_at_kst": r.due_at_kst,
            "notes": r.notes,
        }
        for r in qf.rows
    ]


def _rows_from_db(db_path: Path) -> list[dict[str, Any]]:
    return db_store.list_items(db_path)


def cmd_status_md(queue_path: Path) -> int:
    rows = _rows_from_md(queue_path)
    print(_status_summary(rows))
    return 0


def cmd_workers_md(queue_path: Path) -> int:
    rows = _rows_from_md(queue_path)
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
    rows = _rows_from_db(db_path)
    print(_status_summary(rows))
    return 0


def cmd_workers_db(db_path: Path) -> int:
    rows = _rows_from_db(db_path)
    print(_workers_summary(rows))
    return 0


def _parse_kst(s: str | None) -> datetime | None:
    if not s or s == "-":
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return None


def _count_stale_in_progress(rows: Iterable[dict[str, Any]], stale_minutes: int) -> int:
    now = datetime.now(KST)
    cutoff = now - timedelta(minutes=stale_minutes)
    count = 0
    for row in rows:
        if row.get("status") != "IN_PROGRESS":
            continue
        started = _parse_kst(str(row.get("started_at_kst") or ""))
        if started and started <= cutoff:
            count += 1
    return count


def cmd_consistency_check(queue_path: Path, db_path: Path) -> int:
    md_rows = _rows_from_md(queue_path)
    db_rows = _rows_from_db(db_path)

    md_map = {r["id"]: r for r in md_rows}
    db_map = {str(r["id"]): r for r in db_rows}

    missing_in_db = sorted(set(md_map) - set(db_map))
    missing_in_md = sorted(set(db_map) - set(md_map))

    mismatches: list[str] = []
    fields = ["status", "priority", "owner_session", "started_at_kst", "due_at_kst"]
    for item_id in sorted(set(md_map) & set(db_map)):
        md = md_map[item_id]
        db = db_map[item_id]
        for field in fields:
            md_val = str(md.get(field) or "")
            db_val = str(db.get(field) or "")
            if md_val != db_val:
                mismatches.append(f"{item_id}:{field}:md={md_val} db={db_val}")

    if not missing_in_db and not missing_in_md and not mismatches:
        print(f"consistency ok total={len(md_map)}")
        return 0

    print(
        "consistency mismatch "
        f"missing_in_db={len(missing_in_db)} "
        f"missing_in_md={len(missing_in_md)} "
        f"field_mismatch={len(mismatches)}"
    )
    for item_id in missing_in_db[:20]:
        print(f"- missing_in_db {item_id}")
    for item_id in missing_in_md[:20]:
        print(f"- missing_in_md {item_id}")
    for row in mismatches[:30]:
        print(f"- mismatch {row}")
    return 1


def cmd_kpi(
    log_path: Path,
    db_path: Path,
    max_failure_rate: float | None,
    max_latency_p95_ms: int | None,
    max_stale_in_progress: int | None,
    stale_minutes: int,
    fail_on_alert: bool,
) -> int:
    report = metrics_aggregate.aggregate_from_logs(log_path)
    report["retry_count"] = metrics_aggregate.aggregate_retry_count_from_db(db_path)

    db_rows = _rows_from_db(db_path) if db_path.exists() else []
    stale_in_progress = _count_stale_in_progress(db_rows, stale_minutes=stale_minutes)

    success_rate = report.get("success_rate")
    success_rate_text = "-" if success_rate is None else f"{success_rate * 100:.2f}%"
    print(
        "kpi "
        f"success_rate={success_rate_text} "
        f"latency_p95_ms={report.get('latency_p95_ms')} "
        f"latency_avg_ms={report.get('latency_avg_ms')} "
        f"retry_count={report.get('retry_count')} "
        f"stale_in_progress={stale_in_progress}"
    )

    alerts: list[str] = []
    if max_failure_rate is not None and success_rate is not None:
        failure_rate = 1 - float(success_rate)
        if failure_rate > max_failure_rate:
            alerts.append(f"failure_rate={failure_rate:.4f} exceeds {max_failure_rate:.4f}")

    p95 = report.get("latency_p95_ms")
    if max_latency_p95_ms is not None and isinstance(p95, int) and p95 > max_latency_p95_ms:
        alerts.append(f"latency_p95_ms={p95} exceeds {max_latency_p95_ms}")

    if max_stale_in_progress is not None and stale_in_progress > max_stale_in_progress:
        alerts.append(f"stale_in_progress={stale_in_progress} exceeds {max_stale_in_progress}")

    for msg in alerts:
        print(f"alert {msg}")

    if alerts and fail_on_alert:
        return 2
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

    consistency = sub.add_parser("consistency-check", help="Compare markdown queue and sqlite queue consistency")
    consistency.add_argument("--queue-path")
    consistency.add_argument("--db-path")

    kpi = sub.add_parser("kpi", help="Key operation KPI summary from logs/db")
    kpi.add_argument("--log-path", default=str(config.LOG_PATH))
    kpi.add_argument("--db-path")
    kpi.add_argument("--max-failure-rate", type=float, default=0.2)
    kpi.add_argument("--max-latency-p95-ms", type=int, default=2000)
    kpi.add_argument("--max-stale-in-progress", type=int, default=0)
    kpi.add_argument("--stale-minutes", type=int, default=60)
    kpi.add_argument("--fail-on-alert", action="store_true")

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
    if args.command == "consistency-check":
        check_queue = Path(args.queue_path) if args.queue_path else queue_path
        check_db = Path(args.db_path) if args.db_path else (db_path if db_path else config.DB_PATH)
        return cmd_consistency_check(check_queue, check_db)
    if args.command == "kpi":
        target_db = Path(args.db_path) if args.db_path else (db_path if db_path else config.DB_PATH)
        return cmd_kpi(
            Path(args.log_path),
            target_db,
            max_failure_rate=args.max_failure_rate,
            max_latency_p95_ms=args.max_latency_p95_ms,
            max_stale_in_progress=args.max_stale_in_progress,
            stale_minutes=args.stale_minutes,
            fail_on_alert=args.fail_on_alert,
        )
    if args.command == "cancel":
        return cmd_cancel_db(db_path, args.id) if db_path else cmd_cancel_md(queue_path, args.id)
    if args.command == "replan":
        return cmd_replan_db(db_path, args.id, args.notes) if db_path else cmd_replan_md(queue_path, args.id, args.notes)
    if args.command == "retry":
        return cmd_retry_db(db_path, args.id) if db_path else cmd_retry_md(queue_path, args.id)

    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
