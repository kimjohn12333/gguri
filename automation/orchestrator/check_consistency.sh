#!/usr/bin/env bash
set -euo pipefail

QUEUE_PATH="${ORCH_QUEUE_MD:-automation/orchestrator/QUEUE.md}"
DB_PATH="${ORCH_DB_PATH:-automation/orchestrator/db/queue.db}"
LOG_PATH="${ORCH_LOG_PATH:-automation/orchestrator/logs/orch_runs.jsonl}"

MAX_FAILURE_RATE="${ORCH_KPI_MAX_FAILURE_RATE:-0.2}"
MAX_LATENCY_P95_MS="${ORCH_KPI_MAX_LATENCY_P95_MS:-2000}"
MAX_STALE_IN_PROGRESS="${ORCH_KPI_MAX_STALE_IN_PROGRESS:-0}"
STALE_MINUTES="${ORCH_KPI_STALE_MINUTES:-60}"

CONSISTENCY_CODE=0
KPI_CODE=0

python3 -m automation.orchestrator.ops consistency-check \
  --queue-path "$QUEUE_PATH" \
  --db-path "$DB_PATH" || CONSISTENCY_CODE=$?

python3 -m automation.orchestrator.ops kpi \
  --log-path "$LOG_PATH" \
  --db-path "$DB_PATH" \
  --max-failure-rate "$MAX_FAILURE_RATE" \
  --max-latency-p95-ms "$MAX_LATENCY_P95_MS" \
  --max-stale-in-progress "$MAX_STALE_IN_PROGRESS" \
  --stale-minutes "$STALE_MINUTES" \
  --fail-on-alert || KPI_CODE=$?

if [[ "$CONSISTENCY_CODE" -eq 0 && "$KPI_CODE" -eq 0 ]]; then
  echo "HEALTH_OK"
  exit 0
fi

if [[ "$CONSISTENCY_CODE" -ne 0 ]]; then
  echo "HEALTH_FAIL consistency_mismatch code=$CONSISTENCY_CODE"
  exit 10
fi

if [[ "$KPI_CODE" -eq 2 ]]; then
  echo "HEALTH_WARN kpi_alert code=$KPI_CODE"
  exit 20
fi

echo "HEALTH_ERROR unknown consistency=$CONSISTENCY_CODE kpi=$KPI_CODE"
exit 30
