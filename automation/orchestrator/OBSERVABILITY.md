# OBSERVABILITY.md

## 1) JSON 로그 포맷 (v1)

파일: `automation/orchestrator/logs/orch_runs.jsonl` (JSON Lines)

공통 필드:
- `ts_kst` (string, ISO8601): 이벤트 시각(KST)
- `ts_epoch_ms` (number): epoch milliseconds
- `event` (string): `run_start` | `run_end`
- `trace_id` (string): 실행(run) 단위 상관관계 ID
- `command` (string): `list|add|pick|done|fail`

`run_end` 추가 필드:
- `exit_code` (number): 프로세스 결과 코드
- `status` (string): `ok|error`
- `item_id` (string|null): 해당 실행에서 다룬 queue row id
- `duration_ms` (number): 실행 지연 시간(ms)
- `error` (string, optional): 실패 시 에러 메시지

예시:
```json
{"ts_kst":"2026-02-07T23:50:41+09:00","ts_epoch_ms":1770475841000,"event":"run_start","trace_id":"trace-a1b2c3d4e5f6","command":"done"}
{"ts_kst":"2026-02-07T23:50:41+09:00","ts_epoch_ms":1770475841121,"event":"run_end","trace_id":"trace-a1b2c3d4e5f6","command":"done","exit_code":0,"status":"ok","item_id":"ORCH-011","duration_ms":121}
```

## 2) run별 trace_id 기록

`orch.py`는 기본적으로 실행마다 `trace-<12hex>`를 생성합니다.
필요 시 `--trace-id`로 외부에서 주입 가능합니다.

## 3) 핵심 메트릭 집계

스크립트: `automation/orchestrator/metrics_aggregate.py`

집계 항목:
- 성공률: `success / (success + failed)` (`done/fail` terminal run 기준)
- 지연: `latency_avg_ms`, `latency_p95_ms`
- 재시도 수: SQLite `queue_events.event_type='retried'` 카운트

실행 예:
```bash
python automation/orchestrator/metrics_aggregate.py \
  --log-path automation/orchestrator/logs/orch_runs.jsonl \
  --db-path automation/orchestrator/db/queue.db
```
