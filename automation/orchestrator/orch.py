#!/usr/bin/env python3
"""Simple CLI for managing automation/orchestrator/QUEUE.md."""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

from automation.orchestrator import config

KST = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))
PRIORITY_ORDER = config.PRIORITY_ORDER
DEFAULT_LOG_PATH = config.LOG_PATH


@dataclasses.dataclass
class QueueRow:
    id: str
    status: str
    priority: str
    task: str
    success_criteria: str
    owner_session: str
    started_at_kst: str
    due_at_kst: str
    notes: str

    def to_cells(self) -> List[str]:
        return [
            self.id,
            self.status,
            self.priority,
            self.task,
            self.success_criteria,
            self.owner_session,
            self.started_at_kst,
            self.due_at_kst,
            self.notes,
        ]


class QueueFile:
    def __init__(self, path: Path):
        self.path = path
        self.lines = self.path.read_text(encoding="utf-8").splitlines()
        self.table_start, self.table_end = self._find_table_bounds()
        self.rows = self._parse_rows()

    def _find_table_bounds(self) -> Tuple[int, int]:
        start = None
        for i, line in enumerate(self.lines):
            if line.strip().startswith("| id | status | priority | task |"):
                start = i
                break
        if start is None:
            raise ValueError("Queue table header not found")

        end = len(self.lines)
        for i in range(start + 2, len(self.lines)):
            if not self.lines[i].strip().startswith("|"):
                end = i
                break
        return start, end

    @staticmethod
    def _split_row(line: str) -> List[str]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 9:
            raise ValueError(f"Expected 9 cells in row, got {len(cells)}: {line}")
        return cells

    def _parse_rows(self) -> List[QueueRow]:
        rows: List[QueueRow] = []
        for line in self.lines[self.table_start + 2 : self.table_end]:
            if not line.strip() or not line.strip().startswith("|"):
                continue
            cells = self._split_row(line)
            rows.append(QueueRow(*cells))
        return rows

    def save(self) -> None:
        header = self.lines[self.table_start]
        separator = self.lines[self.table_start + 1]
        row_lines = [self._row_to_line(row) for row in self.rows]
        rebuilt = self.lines[: self.table_start] + [header, separator] + row_lines + self.lines[self.table_end :]
        self.path.write_text("\n".join(rebuilt) + "\n", encoding="utf-8")

    @staticmethod
    def _sanitize_cell(value: str) -> str:
        return value.replace("\n", " ").replace("|", "/").strip()

    def _row_to_line(self, row: QueueRow) -> str:
        cells = [self._sanitize_cell(c) for c in row.to_cells()]
        return "| " + " | ".join(cells) + " |"

    def find_by_id(self, row_id: str) -> QueueRow:
        for row in self.rows:
            if row.id == row_id:
                return row
        raise ValueError(f"Row id not found: {row_id}")


def now_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def now_kst_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def emit_log(log_path: Path, payload: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts_kst": now_kst_iso(),
        "ts_epoch_ms": int(time.time() * 1000),
        **payload,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_list(qf: QueueFile, args: argparse.Namespace) -> int:
    rows = qf.rows
    if args.status:
        rows = [r for r in rows if r.status == args.status]
    if args.priority:
        rows = [r for r in rows if r.priority == args.priority]

    for row in rows:
        print(f"{row.id}\t{row.status}\t{row.priority}\t{row.task}")
    return 0


def cmd_add(qf: QueueFile, args: argparse.Namespace) -> int:
    if any(r.id == args.id for r in qf.rows):
        raise ValueError(f"Row id already exists: {args.id}")

    qf.rows.append(
        QueueRow(
            id=args.id,
            status="PENDING",
            priority=args.priority,
            task=args.task,
            success_criteria=args.success_criteria,
            owner_session="-",
            started_at_kst="-",
            due_at_kst=args.due_at_kst or "-",
            notes=args.notes or "",
        )
    )
    qf.save()
    args._item_id = args.id
    print(f"Added {args.id}")
    return 0


def _pick_candidate(rows: List[QueueRow]) -> QueueRow | None:
    pending = [r for r in rows if r.status == "PENDING"]
    if not pending:
        return None
    pending.sort(key=lambda r: PRIORITY_ORDER.get(r.priority, 99))
    return pending[0]


def cmd_pick(qf: QueueFile, args: argparse.Namespace) -> int:
    row = _pick_candidate(qf.rows)
    if row is None:
        print("No pending tasks")
        return 0

    row.status = "IN_PROGRESS"
    row.started_at_kst = now_kst_str()
    if args.owner_session:
        row.owner_session = args.owner_session
    qf.save()
    args._item_id = row.id
    print(row.id)
    return 0


def _update_terminal_status(qf: QueueFile, row_id: str, status: str, notes: str) -> int:
    row = qf.find_by_id(row_id)
    row.status = status
    row.notes = notes.strip()
    qf.save()
    print(f"{row_id} -> {status}")
    return 0


def cmd_done(qf: QueueFile, args: argparse.Namespace) -> int:
    args._item_id = args.id
    return _update_terminal_status(qf, args.id, "DONE", args.notes)


def cmd_fail(qf: QueueFile, args: argparse.Namespace) -> int:
    args._item_id = args.id
    return _update_terminal_status(qf, args.id, "FAILED", args.notes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orchestrator queue CLI")
    parser.add_argument("--queue", default="automation/orchestrator/QUEUE.md", help="Queue markdown file path")
    parser.add_argument("--trace-id", help="Trace id for this CLI run (default: auto-generated)")
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH), help="JSONL log output path")

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List queue rows")
    p_list.add_argument("--status")
    p_list.add_argument("--priority")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add queue row")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--priority", choices=["P0", "P1", "P2"], required=True)
    p_add.add_argument("--task", required=True)
    p_add.add_argument("--success-criteria", required=True)
    p_add.add_argument("--due-at-kst")
    p_add.add_argument("--notes")
    p_add.set_defaults(func=cmd_add)

    p_pick = sub.add_parser("pick", help="Pick next pending item")
    p_pick.add_argument("--owner-session")
    p_pick.set_defaults(func=cmd_pick)

    p_done = sub.add_parser("done", help="Mark row done")
    p_done.add_argument("--id", required=True)
    p_done.add_argument("--notes", required=True)
    p_done.set_defaults(func=cmd_done)

    p_fail = sub.add_parser("fail", help="Mark row failed")
    p_fail.add_argument("--id", required=True)
    p_fail.add_argument("--notes", required=True)
    p_fail.set_defaults(func=cmd_fail)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    trace_id = args.trace_id or f"trace-{uuid.uuid4().hex[:12]}"
    log_path = Path(args.log_path)
    command = args.command
    started = time.perf_counter()
    emit_log(log_path, {"event": "run_start", "trace_id": trace_id, "command": command})

    try:
        qf = QueueFile(Path(args.queue))
        code = args.func(qf, args)
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit_log(
            log_path,
            {
                "event": "run_end",
                "trace_id": trace_id,
                "command": command,
                "exit_code": code,
                "status": "ok",
                "item_id": getattr(args, "_item_id", None),
                "duration_ms": duration_ms,
            },
        )
        return code
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.perf_counter() - started) * 1000)
        emit_log(
            log_path,
            {
                "event": "run_end",
                "trace_id": trace_id,
                "command": command,
                "exit_code": 1,
                "status": "error",
                "item_id": getattr(args, "_item_id", None),
                "duration_ms": duration_ms,
                "error": str(exc),
            },
        )
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
