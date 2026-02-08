# OPS Commands Spec (v1)

Operator command interface for incident handling and queue control.

CLI entrypoint: `python3 automation/orchestrator/ops.py`

## Global options
- `--queue <path>`: markdown queue path (default: `automation/orchestrator/QUEUE.md`)
- `--db <path>`: use SQLite backend instead of markdown queue

---

## `status`
**Purpose**
- Show fast operational summary by status.
- Show top `IN_PROGRESS` rows for active triage.

**Inputs**
- none (plus optional `--queue` or `--db`)

**Output format**
- Line 1: `summary PENDING=x IN_PROGRESS=y BLOCKED=z FAILED=a DONE=b`
- Next lines: `top_in_progress:` list (up to 5) or `top_in_progress: none`

**Safety checks**
- Read-only command.

**Failure modes**
- queue/db path missing
- malformed markdown table or invalid DB schema

**Examples**
- Markdown: `python3 automation/orchestrator/ops.py status`
- SQLite: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db status`

---

## `workers`
**Purpose**
- Show worker(owner_session)별 현재 작업 배분 현황.
- `IN_PROGRESS` 항목을 owner 기준으로 묶어 빠르게 관제.

**Inputs**
- none (plus optional `--queue` or `--db`)

**Output format**
- Line 1: `workers_active=<n> in_progress=<m>`
- Next lines: `- <owner_session> tasks=<k> p0=<a> p1=<b> p2=<c> ids=<id1,id2,...> oldest_start=<time>`
- 항목이 없으면: `workers: none`

**Safety checks**
- Read-only command.

**Examples**
- Markdown: `python3 automation/orchestrator/ops.py workers`
- SQLite: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db workers`

---

## `consistency-check`
**Purpose**
- `QUEUE.md`와 SQLite queue 상태가 일치하는지 검증.
- DB SSOT 전환 시 drift를 조기 발견.

**Inputs**
- `--queue-path <path>` (optional, default: `--queue` 값)
- `--db-path <path>` (optional, default: `--db` 또는 기본 DB 경로)

**Output format**
- 일치: `consistency ok total=<n>`
- 불일치: `consistency mismatch missing_in_db=<a> missing_in_md=<b> field_mismatch=<c>` + 상세 라인

**Examples**
- `python3 automation/orchestrator/ops.py consistency-check`
- `python3 automation/orchestrator/ops.py consistency-check --queue-path automation/orchestrator/QUEUE.md --db-path automation/orchestrator/db/queue.db`

---

## `kpi`
**Purpose**
- 운영 KPI를 빠르게 확인 (성공률/지연 p95/평균/재시도/stale).

**Inputs**
- `--log-path <path>` (optional, default: `automation/orchestrator/logs/orch_runs.jsonl`)
- `--db-path <path>` (optional, default: `automation/orchestrator/db/queue.db`)
- `--max-failure-rate <float>` (default: `0.2`)
- `--max-latency-p95-ms <int>` (default: `2000`)
- `--max-stale-in-progress <int>` (default: `0`)
- `--stale-minutes <int>` (default: `60`)
- `--fail-on-alert` (optional, alert 발생 시 exit code 2)

**Output format**
- `kpi success_rate=<...> latency_p95_ms=<...> latency_avg_ms=<...> retry_count=<...> stale_in_progress=<...>`
- 임계치 초과 시: `alert ...` 라인 추가

**Examples**
- `python3 automation/orchestrator/ops.py kpi`
- `python3 automation/orchestrator/ops.py kpi --max-failure-rate 0.1 --max-latency-p95-ms 1500 --fail-on-alert`

---

## `cancel --id`
**Purpose**
- Stop operator-owned work for an active item.
- Transition item to `BLOCKED` and preserve audit note.

**Inputs**
- `--id <ORCH-xxx>` (required)

**Output format**
- `<id> -> BLOCKED`

**Safety checks**
- Reject terminal rows (`DONE`, `FAILED`).
- Preserve existing notes; append `cancelled_by_operator`.

**Failure modes**
- id not found
- terminal row cancellation attempted
- queue/db write failure

**Examples**
- Markdown: `python3 automation/orchestrator/ops.py cancel --id ORCH-013`
- SQLite: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db cancel --id ORCH-013`

---

## `replan --id --notes`
**Purpose**
- Record replan rationale and move item to replan-safe status.

**Inputs**
- `--id <ORCH-xxx>` (required)
- `--notes "..."` (required)

**Status policy**
- If current status is `IN_PROGRESS` -> set `BLOCKED` (execution paused, needs explicit unblock).
- Otherwise -> set `PENDING` (ready for next scheduling pass).

**Output format**
- `<id> -> BLOCKED` or `<id> -> PENDING`

**Safety checks**
- Keep original notes; append `replan:<notes>`.
- Reset owner/lease fields when moving to `PENDING` (db mode).

**Failure modes**
- id not found
- missing notes
- queue/db write failure

**Examples**
- Markdown: `python3 automation/orchestrator/ops.py replan --id ORCH-013 --notes "scope split into W1/W2"`
- SQLite: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db replan --id ORCH-013 --notes "need schema update first"`

---

## `retry --id`
**Purpose**
- Return eligible failed/blocked work to runnable state (`PENDING`).

**Inputs**
- `--id <ORCH-xxx>` (required)

**Output format**
- `<id> -> PENDING`

**Safety checks**
- Markdown mode: only `FAILED`/`BLOCKED` can retry.
- SQLite mode: enforce Reliability Policy
  - allow only `FAILED` or timed-out `IN_PROGRESS`
  - enforce `attempt_count < max_attempts`
  - increment attempts and append backoff metadata (`retry_not_before=<epoch>`)

**Failure modes**
- id not found
- item not retry-eligible
- max attempts reached (db mode)
- queue/db write failure

**Examples**
- Markdown: `python3 automation/orchestrator/ops.py retry --id ORCH-013`
- SQLite: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db retry --id ORCH-013`
