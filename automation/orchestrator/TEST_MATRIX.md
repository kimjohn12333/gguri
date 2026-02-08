# 테스트 매트릭스 (ORCH-014)

> 체크리스트를 위에서 아래 순서로 실행하고, 각 항목의 증빙 아티팩트를 남긴다.

## Unit Tests (Core Modules)

- [ ] U-ORCH-PARSE: `orch.py` queue 파싱/직렬화/상태 전환 규칙
  - Command: `pytest automation/orchestrator/tests/test_orch.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_orch.txt`
- [ ] U-DB-STORE: lease/idempotency/retry/backoff 핵심 로직
  - Command: `pytest automation/orchestrator/tests/test_db_store.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_db_store.txt`
- [ ] U-GUARDRAIL: token budget + compact report validator
  - Command: `pytest automation/orchestrator/tests/test_token_guardrails.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_token_guardrails.txt`
- [ ] U-ENFORCE: `enforce_guardrails.py` 상태 반영
  - Command: `pytest automation/orchestrator/tests/test_enforce_guardrails.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_enforce_guardrails.txt`
- [ ] U-OPS: 운영 명령 인자/상태 정책
  - Command: `pytest automation/orchestrator/tests/test_ops.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_ops.txt`
- [ ] U-OBS: trace/log/metrics 집계 로직
  - Command: `pytest automation/orchestrator/tests/test_observability.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_observability.txt`
- [ ] U-UI-VALIDATE: `ui_validate.py` 스모크 판정 로직
  - Command: `pytest automation/orchestrator/tests/test_ui_validate.py -q`
  - Evidence: `automation/orchestrator/reports/unit/test_ui_validate.txt`

## Integration Tests (DB + Ops + Guardrails + Retry)

- [ ] I-MD-CLI: Markdown queue + orch/ops 상태 전환 왕복 검증
  - Command: `pytest automation/orchestrator/tests/test_orch.py automation/orchestrator/tests/test_ops.py -q`
  - Evidence: `automation/orchestrator/reports/integration/md_cli_roundtrip.txt`
- [ ] I-DB-MIGRATE: `QUEUE.md -> queue.db` 마이그레이션 일관성
  - Command: `pytest automation/orchestrator/tests/test_migrate_md_to_db.py -q`
  - Evidence: `automation/orchestrator/reports/integration/migrate_md_to_db.txt`
- [ ] I-GUARDRAIL-BLOCK: hard exceeded 시 BLOCKED 강제
  - Command: `pytest automation/orchestrator/tests/test_enforce_guardrails.py -q`
  - Evidence: `automation/orchestrator/reports/integration/guardrail_block.txt`
- [ ] I-RETRY-FLOW: FAILED/lease-timeout → backoff 후 PENDING 복귀
  - Command: `pytest automation/orchestrator/tests/test_db_store.py -q`
  - Evidence: `automation/orchestrator/reports/integration/retry_flow.txt`
- [ ] I-OPS-RETRY: `ops.py retry` 정책/제약(max_attempts) 검증
  - Command: `pytest automation/orchestrator/tests/test_ops.py -q`
  - Evidence: `automation/orchestrator/reports/integration/ops_retry_policy.txt`
- [ ] I-REVIEW-UI-GATE: `review_and_route.py` + UI 스모크 결합 라우팅
  - Command: `pytest automation/orchestrator/tests/test_review_and_route_md.py automation/orchestrator/tests/test_review_and_route_db.py -q`
  - Evidence: `automation/orchestrator/reports/integration/review_ui_gate.txt`

## E2E Scenarios (Dispatcher/Watchdog/Worker Lifecycle)

- [ ] E2E-01 정상 라이프사이클: PENDING → IN_PROGRESS → DONE
  - Evidence: `automation/orchestrator/logs/e2e/e2e_01_happy_path.jsonl`
- [ ] E2E-02 실패 복구: worker 실패 후 FAILED → retry → DONE
  - Evidence: `automation/orchestrator/logs/e2e/e2e_02_retry_recovery.jsonl`
- [ ] E2E-03 watchdog 복구: stale IN_PROGRESS 감지/복귀
  - Evidence: `automation/orchestrator/logs/e2e/e2e_03_watchdog_recover.jsonl`
- [ ] E2E-04 운영 개입: status → cancel/replan/retry 시나리오
  - Evidence: `automation/orchestrator/logs/e2e/e2e_04_ops_incident.jsonl`

## Soak Scenarios (Long-running/Stress)

- [ ] SOAK-24H 안정성 프로파일 (정상 부하 + 경미한 장애 주입)
  - Evidence: `automation/orchestrator/logs/soak/soak_24h.jsonl`
- [ ] SOAK-72H 스트레스 프로파일 (burst + lock + timeout + retry storm)
  - Evidence: `automation/orchestrator/logs/soak/soak_72h.jsonl`
- [ ] SOAK-REPORT 집계 리포트 생성(성공률/지연/재시도/중복)
  - Evidence: `automation/orchestrator/reports/soak/soak_summary.md`

## 실패 시나리오 커버리지 체크

- [ ] F-01 Lease contention: 단일 lease 보장/경합자 실패 처리
- [ ] F-02 Stuck IN_PROGRESS: timeout 후 retry 복귀
- [ ] F-03 Duplicate dispatch: idempotency skip 이벤트 확인
- [ ] F-04 Budget hard exceed: BLOCKED 전환 + reason 로그
- [ ] F-05 DB lock/timeouts: backoff/재시도 후 복구 또는 FAIL-fast
- [ ] F-06 Max attempts exceeded: 자동 재시도 중단/운영자 escalate

Evidence index:
- 운영 로그: `automation/orchestrator/logs/`
- 테스트 리포트: `automation/orchestrator/reports/`
