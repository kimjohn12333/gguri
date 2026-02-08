"""Centralized configuration for orchestrator.

All hardcoded values are now environment-variable configurable.
"""

from __future__ import annotations

import os
from pathlib import Path

# === Paths ===
BASE_DIR = Path(os.getenv("ORCH_BASE_DIR", "automation/orchestrator"))
QUEUE_MD_PATH = Path(os.getenv("ORCH_QUEUE_MD", str(BASE_DIR / "QUEUE.md")))
DB_PATH = Path(os.getenv("ORCH_DB_PATH", str(BASE_DIR / "db" / "queue.db")))
LOG_PATH = Path(os.getenv("ORCH_LOG_PATH", str(BASE_DIR / "logs" / "orch_runs.jsonl")))

# === Timezone ===
TIMEZONE_OFFSET_HOURS = int(os.getenv("ORCH_TZ_OFFSET", "9"))  # KST default

# === Lease Settings ===
DEFAULT_LEASE_SECONDS = int(os.getenv("ORCH_LEASE_SECONDS", "900"))  # 15 minutes

# === Retry Settings ===
RETRY_BACKOFF_SECONDS = tuple(
    int(x) for x in os.getenv("ORCH_RETRY_BACKOFF", "60,180,600").split(",")
)
DEFAULT_MAX_ATTEMPTS = int(os.getenv("ORCH_MAX_ATTEMPTS", "3"))

# === Token Policy ===
TOKEN_SOFT_LIMIT = int(os.getenv("ORCH_TOKEN_SOFT_LIMIT", "2000"))
TOKEN_HARD_LIMIT = int(os.getenv("ORCH_TOKEN_HARD_LIMIT", "3500"))

# === Scheduler Intervals ===
DISPATCHER_INTERVAL_MINUTES = int(os.getenv("ORCH_DISPATCHER_INTERVAL", "30"))
WATCHDOG_INTERVAL_MINUTES = int(os.getenv("ORCH_WATCHDOG_INTERVAL", "120"))

# === Priority Order ===
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

# === Display Settings ===
TOP_IN_PROGRESS_DISPLAY = int(os.getenv("ORCH_TOP_IN_PROGRESS", "5"))

# === Storage Mode ===
QUEUE_MD_READ_ONLY = os.getenv("ORCH_QUEUE_MD_READ_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}


def get_config_summary() -> dict:
    """Return current configuration as a dictionary for debugging."""
    return {
        "base_dir": str(BASE_DIR),
        "queue_md_path": str(QUEUE_MD_PATH),
        "db_path": str(DB_PATH),
        "log_path": str(LOG_PATH),
        "timezone_offset_hours": TIMEZONE_OFFSET_HOURS,
        "default_lease_seconds": DEFAULT_LEASE_SECONDS,
        "retry_backoff_seconds": RETRY_BACKOFF_SECONDS,
        "default_max_attempts": DEFAULT_MAX_ATTEMPTS,
        "token_soft_limit": TOKEN_SOFT_LIMIT,
        "token_hard_limit": TOKEN_HARD_LIMIT,
        "dispatcher_interval_minutes": DISPATCHER_INTERVAL_MINUTES,
        "watchdog_interval_minutes": WATCHDOG_INTERVAL_MINUTES,
        "queue_md_read_only": QUEUE_MD_READ_ONLY,
    }
