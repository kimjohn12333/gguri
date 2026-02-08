from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from automation.orchestrator import config

KST = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))
PRIORITY_ORDER = config.PRIORITY_ORDER
RETRY_BACKOFF_SECONDS = config.RETRY_BACKOFF_SECONDS


def now_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _conn(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(queue_items)").fetchall()}
    add_cols: list[tuple[str, str]] = []
    if "lease_owner" not in cols:
        add_cols.append(("lease_owner", "TEXT"))
    if "lease_expires_at" not in cols:
        add_cols.append(("lease_expires_at", "INTEGER"))
    if "attempt_count" not in cols:
        add_cols.append(("attempt_count", "INTEGER NOT NULL DEFAULT 0"))
    if "max_attempts" not in cols:
        add_cols.append(("max_attempts", "INTEGER NOT NULL DEFAULT 3"))
    if "idempotency_key" not in cols:
        add_cols.append(("idempotency_key", "TEXT"))
    if "last_error" not in cols:
        add_cols.append(("last_error", "TEXT NOT NULL DEFAULT ''"))

    for name, ddl in add_cols:
        conn.execute(f"ALTER TABLE queue_items ADD COLUMN {name} {ddl}")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_items_lease ON queue_items(lease_expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_items_idempotency ON queue_items(idempotency_key)")


def init_db(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    with _conn(db_path) as conn:
        conn.executescript(schema)
        _ensure_schema_migrations(conn)


def list_items(path: str | Path, status: str | None = None, priority: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM queue_items"
    where = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if priority:
        where.append("priority = ?")
        params.append(priority)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 99 END, created_at ASC"

    with _conn(path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def append_event(path: str | Path, item_id: str, event_type: str, payload: dict[str, Any] | None = None) -> int:
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    now = now_kst_str()
    with _conn(path) as conn:
        cur = conn.execute(
            "INSERT INTO queue_events(item_id, event_type, payload_json, created_at) VALUES(?, ?, ?, ?)",
            (item_id, event_type, payload_json, now),
        )
        return int(cur.lastrowid)


def add_item(
    path: str | Path,
    *,
    id: str,
    priority: str,
    task: str,
    success_criteria: str,
    due_at_kst: str = "-",
    notes: str = "",
    idempotency_key: str | None = None,
    max_attempts: int = 3,
) -> None:
    now = now_kst_str()
    with _conn(path) as conn:
        conn.execute(
            """
            INSERT INTO queue_items(
              id, status, priority, task, success_criteria, owner_session,
              started_at_kst, due_at_kst, notes, created_at, updated_at,
              attempt_count, max_attempts, idempotency_key, last_error
            ) VALUES(?, 'PENDING', ?, ?, ?, '-', '-', ?, ?, ?, ?, 0, ?, ?, '')
            """,
            (id, priority, task, success_criteria, due_at_kst or "-", notes, now, now, max_attempts, idempotency_key),
        )
    append_event(path, id, "added", {"priority": priority, "idempotency_key": idempotency_key})


def _completed_idempotency_exists(conn: sqlite3.Connection, key: str, exclude_id: str | None = None) -> bool:
    sql = "SELECT 1 FROM queue_items WHERE status = 'DONE' AND idempotency_key = ?"
    params: list[Any] = [key]
    if exclude_id:
        sql += " AND id != ?"
        params.append(exclude_id)
    sql += " LIMIT 1"
    return conn.execute(sql, params).fetchone() is not None


def _mark_duplicate_done(conn: sqlite3.Connection, item_id: str) -> None:
    now = now_kst_str()
    conn.execute(
        """
        UPDATE queue_items
        SET status = 'DONE',
            notes = CASE
              WHEN notes = '' THEN 'Skipped duplicate by idempotency_key'
              ELSE notes || ' | Skipped duplicate by idempotency_key'
            END,
            updated_at = ?
        WHERE id = ?
        """,
        (now, item_id),
    )


def pick_next(path: str | Path, owner_session: str) -> dict[str, Any] | None:
    picked_item_id: str | None = None
    skipped_duplicates: list[str] = []
    with _conn(path) as conn:
        while True:
            row = conn.execute(
                """
                SELECT * FROM queue_items
                WHERE status = 'PENDING'
                ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 99 END,
                         created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                break

            key = row["idempotency_key"]
            if key and _completed_idempotency_exists(conn, key, exclude_id=row["id"]):
                _mark_duplicate_done(conn, row["id"])
                skipped_duplicates.append(row["id"])
                continue

            now = now_kst_str()
            conn.execute(
                """
                UPDATE queue_items
                SET status = 'IN_PROGRESS', owner_session = ?, started_at_kst = ?, updated_at = ?
                WHERE id = ?
                """,
                (owner_session, now, now, row["id"]),
            )
            picked_item_id = row["id"]
            break

    for duplicate_id in skipped_duplicates:
        append_event(path, duplicate_id, "idempotency_skipped", {"reason": "already_done"})

    if picked_item_id is None:
        return None

    append_event(path, picked_item_id, "picked", {"owner_session": owner_session})
    items = list_items(path)
    return next((i for i in items if i["id"] == picked_item_id), None)


def acquire_lease(path: str | Path, item_id: str, owner_session: str, lease_seconds: int = 900) -> bool:
    now = now_epoch()
    expires = now + lease_seconds
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE queue_items
            SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
            WHERE id = ?
              AND (lease_owner IS NULL OR lease_owner = '' OR lease_expires_at IS NULL OR lease_expires_at <= ?)
            """,
            (owner_session, expires, now_kst_str(), item_id, now),
        )
        ok = cur.rowcount == 1
    if ok:
        append_event(path, item_id, "lease_acquired", {"owner_session": owner_session, "expires_at": expires})
    return ok


def renew_lease(path: str | Path, item_id: str, owner_session: str, lease_seconds: int = 900) -> bool:
    now = now_epoch()
    expires = now + lease_seconds
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE queue_items
            SET lease_expires_at = ?, updated_at = ?
            WHERE id = ? AND lease_owner = ? AND lease_expires_at IS NOT NULL AND lease_expires_at > ?
            """,
            (expires, now_kst_str(), item_id, owner_session, now),
        )
        ok = cur.rowcount == 1
    if ok:
        append_event(path, item_id, "lease_renewed", {"owner_session": owner_session, "expires_at": expires})
    return ok


def release_lease(path: str | Path, item_id: str, owner_session: str) -> bool:
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE queue_items
            SET lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE id = ? AND lease_owner = ?
            """,
            (now_kst_str(), item_id, owner_session),
        )
        ok = cur.rowcount == 1
    if ok:
        append_event(path, item_id, "lease_released", {"owner_session": owner_session})
    return ok


def retry_eligible_items(path: str | Path, now_ts: int | None = None) -> list[str]:
    now = now_ts if now_ts is not None else now_epoch()
    retried: list[str] = []
    with _conn(path) as conn:
        rows = conn.execute(
            """
            SELECT id, status, attempt_count, max_attempts, lease_expires_at
            FROM queue_items
            WHERE status IN ('FAILED', 'IN_PROGRESS')
            ORDER BY created_at ASC
            """
        ).fetchall()

        for row in rows:
            attempt_count = int(row["attempt_count"] or 0)
            max_attempts = int(row["max_attempts"] or 3)
            if attempt_count >= max_attempts:
                continue

            is_failed = row["status"] == "FAILED"
            is_timeout = row["status"] == "IN_PROGRESS" and row["lease_expires_at"] is not None and int(row["lease_expires_at"]) <= now
            if not (is_failed or is_timeout):
                continue

            backoff_idx = min(attempt_count, len(RETRY_BACKOFF_SECONDS) - 1)
            backoff_seconds = RETRY_BACKOFF_SECONDS[backoff_idx]
            notes = f"retry_not_before={now + backoff_seconds}"

            conn.execute(
                """
                UPDATE queue_items
                SET status = 'PENDING',
                    owner_session = '-',
                    started_at_kst = '-',
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    attempt_count = attempt_count + 1,
                    notes = CASE WHEN notes = '' THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                WHERE id = ?
                """,
                (notes, notes, now_kst_str(), row["id"]),
            )
            retried.append(row["id"])

    for item_id in retried:
        append_event(path, item_id, "retried", {"reason": "failed_or_timeout"})
    return retried


def _mark_terminal(path: str | Path, item_id: str, status: str, notes: str) -> None:
    now = now_kst_str()
    with _conn(path) as conn:
        cur = conn.execute(
            "UPDATE queue_items SET status = ?, notes = ?, last_error = ?, updated_at = ? WHERE id = ?",
            (status, notes.strip(), notes.strip() if status == "FAILED" else "", now, item_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Row id not found: {item_id}")
    append_event(path, item_id, status.lower(), {"notes": notes.strip()})


def mark_done(path: str | Path, id: str, notes: str) -> None:
    _mark_terminal(path, id, "DONE", notes)


def mark_failed(path: str | Path, id: str, notes: str) -> None:
    _mark_terminal(path, id, "FAILED", notes)


def mark_blocked(path: str | Path, id: str, reason: str) -> None:
    _mark_terminal(path, id, "BLOCKED", reason)


def append_guardrail_event(
    path: str | Path,
    item_id: str,
    *,
    state: str,
    action: str,
    current_tokens: int,
    estimated_tokens: int,
    violations: list[dict[str, Any]] | None = None,
) -> int:
    payload: dict[str, Any] = {
        "state": state,
        "action": action,
        "current_tokens": int(current_tokens),
        "estimated_tokens": int(estimated_tokens),
        "violations": violations or [],
    }
    return append_event(path, item_id, "guardrail", payload)
