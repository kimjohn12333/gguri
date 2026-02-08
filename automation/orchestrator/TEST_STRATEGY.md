# 제품화 테스트 전략 (ORCH-014)

## 1) 목표
오케스트레이터를 제품화 가능한 수준으로 검증하기 위해, 테스트 피라미드(단위→통합→E2E→Soak)를 정의하고 릴리즈 후보(RC) 게이트를 명문화한다.

## 2) 테스트 피라미드
권장 비중(케이스 수 기준):
- **Unit (약 60%)**: 순수 로직/파서/정책 함수의 결정성 검증
- **Integration (약 25%)**: DB/CLI/정책 결합 흐름 검증
- **E2E (약 10%)**: dispatcher-watchdog-worker 운영 시나리오 검증
- **Soak (약 5%)**: 장시간 안정성/누수/재시도 행태 검증

## 3) 레이어별 대상 컴포넌트

### Unit
- `orch.py` 테이블 파싱/상태 전환(`list/add/pick/done/fail`) 규칙
- `db_store.py` lease/idempotency/retry/backoff 순수 로직
- `token_guardrails.py` budget 판정/compact report 검증/액션 결정
- `ops.py` status/cancel/replan/retry 인자 검증 및 상태 정책
- `metrics_aggregate.py` 지표 집계(성공률/지연/재시도)

### Integration
- Markdown Queue(`QUEUE.md`) ↔ CLI(`orch.py`, `ops.py`) 상호작용
- SQLite(`db/queue.db`) + `db_store.py` + `ops.py --db` 연동
- Guardrail 강제(`enforce_guardrails.py`) + queue event/blocked 반영
- Retry 흐름: FAILED 또는 lease-timeout 항목의 PENDING 복귀

### E2E
- Dispatcher가 PENDING 1건 pick 후 worker 세션으로 진행
- Worker 완료/실패 시 `done`/`fail` 처리 및 notes 감사 추적
- Watchdog가 stale `IN_PROGRESS`를 탐지하고 retry 후보화
- Ops incident 대응(status→cancel/replan/retry) 후 복구

### Soak
- 24h 운영 부하에서 queue 처리량/실패율/중복 실행 방지 검증
- 72h 스트레스 부하에서 lease 경합/DB lock/재시도 누적 안정성 검증

## 4) 공통 실패 시나리오와 기대 처리
1. **Lease contention(동시 lease 획득 경쟁)**
   - 기대: 단일 owner만 획득 성공, 나머지는 획득 실패 후 재시도 대기.
2. **Stuck IN_PROGRESS(heartbeat/lease 갱신 누락)**
   - 기대: lease timeout 후 retry 루프에서 `PENDING` 복귀, owner/lease 필드 초기화.
3. **Duplicate dispatch(중복 enqueue 또는 중복 pick 시도)**
   - 기대: 동일 `idempotency_key`가 DONE이면 `idempotency_skipped` 이벤트 후 실행 skip.
4. **Budget hard exceed(토큰 하드 임계 초과)**
   - 기대: guardrail이 `BLOCK` 결정, 상태 `BLOCKED` 전환 및 reason/event 기록.
5. **DB lock/timeout(SQLite busy)**
   - 기대: transient 분류 후 재시도(backoff), 반복 시 FAILED 기록 + 운영자 개입.
6. **Retry max_attempts 도달**
   - 기대: 자동 재시도 중단, FAILED 유지 및 notes에 next action 명시.

## 5) RC(Release Candidate) Pass/Fail Gate

### Pass (모두 충족)
- 단위/통합/기능 테스트 전부 통과 (pytest 100% pass)
- E2E 필수 시나리오 3종 이상(정상/실패복구/운영개입) 통과
- 24h soak 완료, SLO 위반 없음
- 72h soak에서 치명적 장애 없음(Abort condition 미충족)
- 주요 실패 시나리오(위 1~5 중 최소 5개) 재현/완화 증빙 확보
- 아티팩트(로그/리포트) 경로가 `automation/orchestrator/logs/` 또는 `reports/`에 보존

### Fail (하나라도 해당)
- 데이터 무결성 훼손(중복 완료/유실/상태 전이 불일치)
- guardrail 미작동(하드 초과인데 BLOCKED 미전환)
- soak 중 서비스 중단 또는 반복 abort 조건 충족
- 테스트 증빙 누락(결과 로그/리포트 파일 부재)

## 6) 실행 순서(요약)
1. Unit/Integration: `pytest automation/orchestrator/tests -q`
2. E2E 시나리오: dispatcher/watchdog/ops 커맨드 기반 수동+자동 스모크
3. Soak: `SOAK_TEST_PLAN.md` 24h → 72h 순서로 진행
4. RC 게이트 판정 및 큐/릴리즈 노트 업데이트
