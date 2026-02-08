# OpenClaw 무중단 작업 오케스트레이션 (v1)

구성 요소:
1) Queue 파일: `automation/orchestrator/QUEUE.md`
2) Dispatcher: 주기적으로 PENDING 1개를 집어 `sessions_spawn`으로 실행
3) Watchdog: 오래 멈춘 IN_PROGRESS를 PENDING으로 복구(선택)

## 운영 규칙 (권장)
- 동시에 여러 개를 병렬 실행하고 싶으면 row를 여러 개 두되, dispatcher는 한 tick에 1개만 집는다.
- 실패한 항목(FAILED)은 사람이 notes를 보고 원인 정리 후 PENDING으로 되돌려 재시도한다.
- 외부 의존(로그인/토큰/승인 필요)은 BLOCKED로 표시한다.

## 추천 스케줄
- Dispatcher: 30분마다
- Watchdog: 2시간마다

## 수동 점검
- `/subagents list`로 실행 중 확인
- `/subagents log <id>`로 로그 확인
- queue 파일에서 status/notes 확인

## 롤백
- 관련 cron job disable
- queue 파일 보관 후 비우기

## orch CLI (v1)
큐 파일을 수동/자동으로 안전하게 조작하기 위한 CLI: `automation/orchestrator/orch.py`

### 지원 명령
- `list`: 전체/필터 조회
- `add`: 새 작업 추가(PENDING으로 생성)
- `pick`: 다음 PENDING 1개를 우선순위(P0>P1>P2)로 집어 `IN_PROGRESS` 전환
- `done`: 대상 row를 `DONE`으로 전환 + notes 기록
- `fail`: 대상 row를 `FAILED`로 전환 + notes 기록

### 사용 예시
- 목록 조회: `python3 automation/orchestrator/orch.py list`
- 상태 필터: `python3 automation/orchestrator/orch.py list --status PENDING`
- 작업 추가:
  `python3 automation/orchestrator/orch.py add --id ORCH-010 --priority P1 --task "문서 보완" --success-criteria "README 반영" --due-at-kst "2026-02-08 18:00"`
- 다음 작업 집기:
  `python3 automation/orchestrator/orch.py pick --owner-session agent:main:subagent:xxx`
- 완료 처리:
  `python3 automation/orchestrator/orch.py done --id ORCH-010 --notes "테스트 통과, 문서 반영 완료"`
- 실패 처리:
  `python3 automation/orchestrator/orch.py fail --id ORCH-010 --notes "외부 토큰 누락으로 실패, 재시도 필요"`

### 운영 규칙 반영 사항
- `pick`은 항상 1개만 집고, 후보가 없으면 변경 없이 종료
- `done`/`fail`은 notes 입력을 강제해 사후 분석 가능성 확보
- 셀 내 `|` 문자는 `/`로 치환해 markdown 테이블 파손 방지

## Natural Intake CLI (MVP)
자연어 요청 1줄을 큐 row 여러 개로 분해해 추가하는 진입점입니다.

- 미리보기(큐 미반영):
  `python3 -m automation.orchestrator.nl_intake plan --request "로그 정리, 재시도 보강, 문서 업데이트" --parallel 3`
- 큐 반영:
  `python3 -m automation.orchestrator.nl_intake submit --request "로그 정리, 재시도 보강, 문서 업데이트" --parallel 3 --priority P1`

동작 요약:
- bullet/번호 목록 입력이면 항목 단위로 분해
- 구분자(, ; 그리고 및 / ->)가 있으면 분해
- 분해가 어려우면 `설계 -> 구현 -> 검증` 3단계 템플릿으로 생성
- 생성 row는 `notes`에 `nl_intake:<timestamp>` 태그를 남김

## Team Mode (MVP)
Lead 1 + Worker 3 구조로 하위 작업을 병렬 처리하는 모드입니다.
상세 규칙은 `automation/orchestrator/TEAM_MODE.md`를 참고하세요.

### Quickstart
1. 팀 규칙 확인: `TEAM_MODE.md` 읽기
2. 하위 작업 정의: `team_task_template.json` 복제 후 task별로 작성
3. Lead가 Worker에 task assign (`sessions_send`, `[TASK <id>]` prefix)
4. Worker가 `TOKEN_POLICY.md`의 `Compact Report` 템플릿으로 report (`[REPORT <id>]`)
5. Lead가 결과 통합 후 큐 상태를 `DONE`/`FAILED`로 업데이트

### Token Efficiency
자세한 기준은 `automation/orchestrator/TOKEN_POLICY.md`를 따른다.

기본값(MVP):
- Worker 보고: `Compact Report` 템플릿 고정(파일 경로 + diff 요약 우선)
- Context budget: Soft 2,000 / Hard 3,500
- 트리거(장기 대화/중복 재인용/의존성 변경) 발생 시 summarize/trim 수행
- Hard 임계 근접 시 `!replan` 또는 새 턴으로 분리

실행 강제(guardrail enforcement):
- 스크립트: `automation/orchestrator/enforce_guardrails.py`
- 예시:
  `python3 automation/orchestrator/enforce_guardrails.py --id ORCH-012 --report /tmp/report.txt --current-tokens 2400 --db automation/orchestrator/db/queue.db`
- 동작:
  - `ALLOW`: 이벤트만 기록
  - `SUMMARIZE`: 이벤트 기록 + 요약 필요 상태 표시(상태는 유지)
  - `BLOCK`: `BLOCKED` 상태 전환 + reason/이벤트 기록

### Pilot Run References (ORCH-008)
- Runbook: `automation/orchestrator/PILOT_RUNBOOK.md`
- Smoke log: `automation/orchestrator/pilot_logs/ORCH-008-smoke-2026-02-07.md`

## SQLite backend (v1)
Queue productization 시작을 위해 SQLite 저장소를 추가했습니다. 목적은 queue 조회/상태전환/이벤트 로그를 코드 레벨에서 다루기 쉽게 만드는 것입니다.

- 스키마: `automation/orchestrator/db/schema.sql`
- 저장소 모듈: `automation/orchestrator/db_store.py`
- 마이그레이션: `automation/orchestrator/migrate_md_to_db.py`

초기화:
- `python3 -c "from automation.orchestrator.db_store import init_db; init_db('automation/orchestrator/db/queue.db')"`

마이그레이션:
- `python3 automation/orchestrator/migrate_md_to_db.py --queue automation/orchestrator/QUEUE.md --db automation/orchestrator/db/queue.db`

주의: 현재는 `QUEUE.md`가 계속 source of truth이며, SQLite는 보조 백엔드(v1)입니다. 명시적으로 전환하기 전까지 기존 `orch.py` 워크플로우는 그대로 유지됩니다.

## Operator Commands (ORCH-013)
- Command spec: `automation/orchestrator/OPS_COMMANDS.md`
- CLI: `automation/orchestrator/ops.py`

Quickstart:
- Markdown queue status: `python3 automation/orchestrator/ops.py status`
- SQLite queue status: `python3 automation/orchestrator/ops.py --db automation/orchestrator/db/queue.db status`
- Worker allocation view: `python3 automation/orchestrator/ops.py workers`
- Cancel/Replan/Retry: `cancel --id`, `replan --id --notes`, `retry --id`

## Reliability Layer (v1)
SQLite backend 위에 최소 신뢰성 레이어를 추가했습니다.

핵심:
- Lease: 작업 소유권(획득/갱신/해제)으로 중복 실행 방지
- Idempotency: `idempotency_key`가 이미 DONE이면 pick 단계에서 중복 항목 자동 skip
- Retry: FAILED/lease-timeout 항목을 백오프(1m/3m/10m)로 PENDING 복귀, `max_attempts` 도달 시 중단

Python 예시:
- lease 획득/갱신/해제
  ```python
  from automation.orchestrator import db_store

  ok = db_store.acquire_lease("automation/orchestrator/db/queue.db", "ORCH-010", "agent:worker-1", lease_seconds=900)
  if ok:
      db_store.renew_lease("automation/orchestrator/db/queue.db", "ORCH-010", "agent:worker-1", lease_seconds=900)
      db_store.release_lease("automation/orchestrator/db/queue.db", "ORCH-010", "agent:worker-1")
  ```

- retry 실행
  ```python
  from automation.orchestrator import db_store

  retried_ids = db_store.retry_eligible_items("automation/orchestrator/db/queue.db")
  print(retried_ids)
  ```

CLI 예시(현행):
- 큐 상태 변경: `python3 automation/orchestrator/orch.py done --id ORCH-010 --notes "reliability v1 done"`
- 실패 기록: `python3 automation/orchestrator/orch.py fail --id ORCH-010 --notes "transient error"`

정책 요약은 `automation/orchestrator/RELIABILITY_POLICY.md`를 참고하세요.

## Observability (ORCH-011)
- 로그 스펙: `automation/orchestrator/OBSERVABILITY.md`
- 구조화 로그(JSONL): `automation/orchestrator/logs/orch_runs.jsonl`
- `orch.py`는 run별 `trace_id`를 자동 생성하며 `--trace-id`로 주입 가능
- 메트릭 집계: `python3 automation/orchestrator/metrics_aggregate.py --log-path automation/orchestrator/logs/orch_runs.jsonl --db-path automation/orchestrator/db/queue.db`

## Productization Test Pack (ORCH-014)
사전 릴리즈 검증을 위한 테스트 문서:
- 전략: `automation/orchestrator/TEST_STRATEGY.md`
- 매트릭스: `automation/orchestrator/TEST_MATRIX.md`
- 장시간 검증 계획: `automation/orchestrator/SOAK_TEST_PLAN.md`

권장 실행 순서(Pre-release):
1. `pytest automation/orchestrator/tests -q` (unit/integration 회귀)
2. `TEST_MATRIX.md`의 E2E 시나리오 체크(Dispatcher/Watchdog/Worker)
3. `SOAK_TEST_PLAN.md`의 24h profile 실행 및 SLO 확인
4. 72h profile 실행 후 abort condition 미충족 확인
5. RC pass/fail gate를 `TEST_STRATEGY.md` 기준으로 판정

## Reviewer Gate Loop (ORCH-015)
작업 결과(report)가 성공 기준(success criteria)을 만족하는지 자동 판정하고, 결과에 따라 큐 상태를 라우팅합니다.

구성:
- 판정기: `automation/orchestrator/reviewer_gate.py`
  - verdict: `PASS | RETRY | BLOCK`
  - 기준: checklist 키워드 커버리지 + explicit failure/block marker
- 라우터 CLI: `automation/orchestrator/review_and_route.py`

기본 사용법 (Markdown queue):
- `python3 automation/orchestrator/review_and_route.py --id ORCH-010 --success-criteria "README 반영; 테스트 통과" --report "/tmp/report.txt"`

SQLite 모드:
- `python3 automation/orchestrator/review_and_route.py --db automation/orchestrator/db/queue.db --id ORCH-010 --success-criteria "README 반영; 테스트 통과" --report "README 반영 완료, 테스트 통과" --max-retries 3`

UI 스모크 검증 포함(선택):
- 검증기 CLI: `python3 automation/orchestrator/ui_validate.py --url https://example.com --contains Dashboard`
- 리뷰 라우팅에 UI 조건 결합:
  - `python3 automation/orchestrator/review_and_route.py --id ORCH-010 --success-criteria "README 반영; 테스트 통과" --report "/tmp/report.txt" --ui-url https://example.com --ui-contains Dashboard --ui-contains Settings`

라우팅 규칙:
- `PASS` -> `DONE`
- `RETRY` -> 시도 가능하면 `PENDING`(attempt 증가 + retry note/event)
- `BLOCK` -> `BLOCKED` (이유 기록)
- UI 검증 실패 시: `RETRY` 우선, 재시도 한도 도달 시 `BLOCK`

자세한 정책은 `automation/orchestrator/REVIEWER_GATE_POLICY.md` 참고.
