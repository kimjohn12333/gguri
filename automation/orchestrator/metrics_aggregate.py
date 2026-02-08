#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from statistics import mean
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    seq = sorted(values)
    idx = int((len(seq) - 1) * p)
    return seq[idx]


def aggregate_from_logs(log_path: Path) -> dict[str, Any]:
    events = _read_jsonl(log_path)
    run_end = [e for e in events if e.get("event") == "run_end"]

    terminal = [e for e in run_end if e.get("command") in {"done", "fail"} and e.get("exit_code") == 0]
    success = sum(1 for e in terminal if e.get("command") == "done")
    failed = sum(1 for e in terminal if e.get("command") == "fail")
    total_terminal = success + failed

    durations = [int(e.get("duration_ms", 0)) for e in run_end if isinstance(e.get("duration_ms"), int)]

    return {
        "source": str(log_path),
        "total_runs": len(run_end),
        "terminal_runs": total_terminal,
        "success": success,
        "failed": failed,
        "success_rate": round(success / total_terminal, 4) if total_terminal else None,
        "latency_avg_ms": round(mean(durations), 2) if durations else None,
        "latency_p95_ms": _percentile(durations, 0.95) if durations else None,
    }


def aggregate_retry_count_from_db(db_path: Path) -> int | None:
    if not db_path.exists():
        return None
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT COUNT(*) FROM queue_events WHERE event_type = 'retried'").fetchone()
        return int(row[0]) if row else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate orchestrator success/latency/retry metrics")
    parser.add_argument("--log-path", default="automation/orchestrator/logs/orch_runs.jsonl")
    parser.add_argument("--db-path", default="automation/orchestrator/db/queue.db")
    args = parser.parse_args()

    report = aggregate_from_logs(Path(args.log_path))
    report["retry_count"] = aggregate_retry_count_from_db(Path(args.db_path))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
