#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from automation.orchestrator import db_store
from automation.orchestrator.orch import QueueFile, now_kst_str
from automation.orchestrator.reviewer_gate import BLOCK, PASS, RETRY, evaluate_result
from automation.orchestrator.ui_validate import validate_ui


def _append_note(existing: str, msg: str) -> str:
    msg = msg.strip()
    if not existing.strip():
        return msg
    return f"{existing.strip()} | {msg}"


def _extract_attempts(notes: str) -> int:
    parts = [p.strip() for p in notes.split("|") if p.strip()]
    for p in reversed(parts):
        if p.startswith("review_attempts="):
            try:
                return int(p.split("=", 1)[1])
            except ValueError:
                return 0
    return 0


def _set_attempts_note(notes: str, attempts: int) -> str:
    parts = [p.strip() for p in notes.split("|") if p.strip() and not p.strip().startswith("review_attempts=")]
    parts.append(f"review_attempts={attempts}")
    return " | ".join(parts)


def _read_report(report_arg: str) -> str:
    p = Path(report_arg)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return report_arg


def _apply_ui_gate(
    verdict: dict,
    *,
    ui_result: dict | None,
    attempt_count: int,
    max_retries: int,
) -> dict:
    if not ui_result:
        return verdict

    out = {
        "verdict": verdict["verdict"],
        "reasons": list(verdict.get("reasons") or []),
        "missing_checks": list(verdict.get("missing_checks") or []),
        "covered_checks": verdict.get("covered_checks", 0),
        "total_checks": verdict.get("total_checks", 0),
    }

    if ui_result.get("ok"):
        out["reasons"].append("ui_validation_passed")
        return out

    ui_reasons = ui_result.get("reasons") or ["ui_validation_failed"]
    out["reasons"].append("ui:" + ";".join(ui_reasons))
    if "ui_validation" not in out["missing_checks"]:
        out["missing_checks"].append("ui_validation")

    if out["verdict"] != BLOCK:
        if attempt_count >= max_retries:
            out["verdict"] = BLOCK
            out["reasons"].append(f"retry_limit_reached:{attempt_count}/{max_retries}")
        else:
            out["verdict"] = RETRY

    return out


def route_markdown(queue_path: Path, item_id: str, verdict: dict, max_retries: int) -> str:
    qf = QueueFile(queue_path)
    row = qf.find_by_id(item_id)
    attempts = _extract_attempts(row.notes)

    if verdict["verdict"] == PASS:
        row.status = "DONE"
        row.notes = _append_note(row.notes, f"review:PASS {';'.join(verdict['reasons'])}")
    elif verdict["verdict"] == RETRY:
        attempts += 1
        row.status = "PENDING"
        row.owner_session = "-"
        row.started_at_kst = "-"
        row.notes = _set_attempts_note(row.notes, attempts)
        row.notes = _append_note(
            row.notes,
            f"review:RETRY attempt={attempts}/{max_retries} missing={','.join(verdict['missing_checks'])}",
        )
    else:
        row.status = "BLOCKED"
        row.notes = _append_note(row.notes, f"review:BLOCK {';'.join(verdict['reasons'])}")

    qf.save()
    return row.status


def _db_row(path: Path, item_id: str) -> dict:
    items = [x for x in db_store.list_items(path) if x["id"] == item_id]
    if not items:
        raise ValueError(f"Row id not found: {item_id}")
    return items[0]


def route_sqlite(db_path: Path, item_id: str, verdict: dict, max_retries: int) -> str:
    row = _db_row(db_path, item_id)
    if verdict["verdict"] == PASS:
        notes = _append_note(row.get("notes", ""), f"review:PASS {';'.join(verdict['reasons'])}")
        db_store.mark_done(db_path, item_id, notes)
        db_store.append_event(db_path, item_id, "review_gate", {"verdict": PASS, "reasons": verdict["reasons"]})
        return "DONE"

    if verdict["verdict"] == RETRY:
        attempts = int(row.get("attempt_count") or 0) + 1
        missing = verdict.get("missing_checks") or []
        notes = _append_note(
            row.get("notes", ""),
            f"review:RETRY attempt={attempts}/{max_retries} missing={','.join(missing)}",
        )
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                UPDATE queue_items
                SET status='PENDING',
                    owner_session='-',
                    started_at_kst='-',
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    attempt_count=?,
                    notes=?,
                    updated_at=?
                WHERE id=?
                """,
                (attempts, notes, now_kst_str(), item_id),
            )
        db_store.append_event(
            db_path,
            item_id,
            "review_gate",
            {"verdict": RETRY, "attempt": attempts, "max_retries": max_retries, "missing_checks": missing},
        )
        return "PENDING"

    reason = ";".join(verdict["reasons"]) or "review_gate_blocked"
    notes = _append_note(row.get("notes", ""), f"review:BLOCK {reason}")
    db_store.mark_blocked(db_path, item_id, notes)
    db_store.append_event(db_path, item_id, "review_gate", {"verdict": BLOCK, "reasons": verdict["reasons"]})
    return "BLOCKED"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Review worker report and route queue state")
    p.add_argument("--id", required=True)
    p.add_argument("--success-criteria", required=True)
    p.add_argument("--report", required=True, help="Report text or file path")
    p.add_argument("--queue", default="automation/orchestrator/QUEUE.md")
    p.add_argument("--db", help="SQLite queue DB path")
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--ui-url", help="Optional URL for UI smoke validation")
    p.add_argument("--ui-contains", action="append", default=[], help="Required terms in UI snapshot")
    p.add_argument("--ui-timeout-seconds", type=int, default=45)
    p.add_argument("--ui-session", help="Optional playwright-cli session name")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report_text = _read_report(args.report)

    if args.db:
        row = _db_row(Path(args.db), args.id)
        attempt_count = int(row.get("attempt_count") or 0)
    else:
        qf = QueueFile(Path(args.queue))
        row = qf.find_by_id(args.id)
        attempt_count = _extract_attempts(row.notes)

    verdict = evaluate_result(
        args.success_criteria,
        report_text,
        attempt_count=attempt_count,
        max_retries=args.max_retries,
    )

    ui_result = None
    if args.ui_url:
        ui_result = validate_ui(
            args.ui_url,
            args.ui_contains,
            timeout_seconds=args.ui_timeout_seconds,
            session=args.ui_session,
        )
        verdict = _apply_ui_gate(
            verdict,
            ui_result=ui_result,
            attempt_count=attempt_count,
            max_retries=args.max_retries,
        )

    if args.db:
        status = route_sqlite(Path(args.db), args.id, verdict, args.max_retries)
    else:
        status = route_markdown(Path(args.queue), args.id, verdict, args.max_retries)

    print(f"{args.id} -> {status} ({verdict['verdict']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
