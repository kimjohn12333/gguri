# Orchestrator Queue

이 파일이 장기 작업의 단일 진실 소스(SSOT)입니다.

## Status 규칙
- `PENDING`: 아직 시작 안 함
- `IN_PROGRESS`: 서브에이전트가 작업 중
- `DONE`: 완료
- `FAILED`: 실패(재시도 필요)
- `BLOCKED`: 외부 입력 대기

## Priority 규칙
- `P0` > `P1` > `P2`

## Queue

| id | status | priority | task | success_criteria | owner_session | started_at_kst | due_at_kst | notes |
|---|---|---|---|---|---|---|---|---|
| ORCH-001 | DONE | P1 | OpenClaw에서 무중단 작업 패턴(크론+하트비트+서브에이전트) 검증 | 1) 짧은 운영 가이드 작성 2) 실패/재시도 규칙 정의 | agent:main:subagent:0e00c142-c2cc-4e8a-90c9-2afbb32daa15 | 2026-02-07 20:08 | - | 운영 가이드 작성 완료(automation/orchestrator/CONTINUOUS_WORK_PATTERN.md). 일시적/영구 실패 분류와 3회 백오프(1m/3m/10m) 재시도 규칙 정의. |
| ORCH-002 | DONE | P1 | 오케스트레이터 수동 운영용 체크리스트 파일 작성 | 1) CHECKLIST.md 생성 2) 일일/주간 점검 항목 분리 3) 수동 실행 명령 5개 포함 | agent:main:subagent:1ce56b85-bb83-446b-b342-443662d35a0f | 2026-02-07 20:18 | - | CHECKLIST.md를 생성해 일일/주간 점검을 분리하고, 수동 실행 명령 5개를 포함해 완료했습니다. |
| ORCH-003 | DONE | P1 | 오케스트레이터 실패 재시도 실행 로그 템플릿 작성 | 1) RETRY_LOG_TEMPLATE.md 생성 2) 실패 유형(일시적/영구)별 기록 필드 분리 3) 실제 기록 예시 2건(재시도 성공 1, 최종 실패 1) 포함 | agent:main:subagent:1d8aa8c2-68f4-4512-9c8d-344ced9555ea | 2026-02-07 20:20 | - | RETRY_LOG_TEMPLATE.md 생성 완료. 일시적/영구 실패 기록 필드를 분리하고, 재시도 성공 1건·최종 실패 1건 예시를 포함함. |
| ORCH-004 | DONE | P1 | 오케스트레이터 CLI 고도화(대규모 리팩토링 준비 v1) | 1) orch CLI(list/add/pick/done/fail) 구현 2) 테스트 10개 이상 3) README 사용 예시+운영 규칙 반영 | agent:main:subagent:4da39901-431a-40f4-9fbb-5aba116d273e | 2026-02-07 20:56 | - | orch.py에 list/add/pick/done/fail CLI와 QUEUE.md 파싱/갱신 로직을 구현함. test_orch.py에 11개 테스트를 추가해 모두 통과했고 README에 사용 예시/운영 규칙을 반영함. |
| ORCH-005 | DONE | P0 | Agent Team 모드 MVP(리드+워커 3) 설계/구현 | 1) TEAM_MODE.md 작성 2) team-task 템플릿(JSON) 추가 3) 운영 명령(!status/!cancel/!replan) 규칙 문서화 | agent:main:subagent:f8652370-4510-4302-bdb4-16b66c09fc07 | 2026-02-07 22:15 | 2026-02-08 01:00 | TEAM_MODE.md 및 team_task_template.json 추가, README에 Team Mode quickstart 반영. Worker 출력(최대 8 bullets + Risks), Soft/Hard budget(2000/3500), 파일 경로 참조 우선 정책을 MVP로 문서화. |
| ORCH-006 | DONE | P0 | 토큰 효율화 정책 v1 도입 | 1) TOKEN_POLICY.md 작성 2) 서브에이전트 compact 출력 포맷 정의 3) context budget(soft/hard) 규칙 추가 | agent:main:subagent:ae34e1aa-738c-4094-9318-f6a955dd037c | 2026-02-07 22:20 | 2026-02-08 01:30 | TOKEN_POLICY.md 신설 및 TEAM_MODE/README 연동 반영. Compact Report, Soft/Hard(2000/3500), summarize/trim+escalation 규칙을 MVP로 적용. |
| ORCH-007 | DONE | P1 | Dispatcher 팀 병렬 운영 가이드 업데이트 | 1) DISPATCHER.md에 병렬/순차 선택 규칙 추가 2) 최대 워커 수 규칙 명시 3) 실패시 복구 플로우 반영 | agent:main:subagent:343be538-b15a-40af-8bb1-3b91b643d42f | 2026-02-07 22:35 | 2026-02-08 02:00 | DISPATCHER.md에 순차/병렬 모드 선택 규칙과 공통 후보 선정 원칙을 추가함. 최대 워커(기본 3, 하드캡 5) 및 스폰 실패/타임아웃/부분 실패 복구 플로우를 반영함. |
| ORCH-008 | DONE | P1 | 팀 모드 파일럿 실행(runbook + smoke test) | 1) PILOT_RUNBOOK.md 작성 2) 샘플 작업 1건 실행 로그 남김 3) lessons learned 3개 기록 | agent:main:subagent:971468f5-188f-4e61-9fd5-1dd7a3221702 | 2026-02-07 22:36 | 2026-02-08 02:30 | Pilot runbook/smoke log completed with TOKEN_POLICY-aligned compact flow. README linked to PILOT_RUNBOOK.md and pilot_logs/ORCH-008-smoke-2026-02-07.md. |
| ORCH-009 | DONE | P0 | Queue 저장소를 SQLite로 전환(v1) | 1) queue.db 스키마(sql) 추가 2) queue CRUD 파이썬 모듈 구현 3) 기존 QUEUE.md와 동기화/마이그레이션 스크립트 제공 | agent:main:subagent:75c7e0c4-bf23-496d-9fb7-4ce8b1aa4e12 | 2026-02-07 23:13 | 2026-02-08 01:00 | SQLite queue backend v1 added (schema/db_store/migration) with idempotent md->db upsert. Added deterministic tests (db store+migration) and all orchestrator tests pass. |
| ORCH-010 | DONE | P0 | 실행 신뢰성 레이어(lease/idempotency/retry) 구현 | 1) lease timeout/heartbeat 로직 구현 2) idempotency key 중복 실행 방지 3) 재시도 백오프/최대횟수 규칙 코드 반영 | agent:main:subagent:80927bf7-5e9e-40ba-86c7-52ad2cb17cbf | 2026-02-07 23:15 | 2026-02-08 02:00 | SQLite reliability layer v1 shipped: lease acquire/renew/release, idempotency skip on pick, retry helper(1m/3m/10m,max_attempts). Added RELIABILITY_POLICY.md + README section and deterministic db_store tests; full orchestrator test suite passes. |
| ORCH-011 | DONE | P1 | 관측성(구조화 로그+핵심 메트릭) 도입 | 1) JSON 로그 포맷 정의 2) run별 trace_id 기록 3) 성공률/지연/재시도 집계 스크립트 추가 | agent:main:subagent:0467a6ac-f31c-436c-8808-b48a6334c06b | 2026-02-07 23:35 | 2026-02-08 03:00 | OBSERVABILITY.md에 JSONL 로그 스키마와 trace_id 규칙을 정의했고 orch.py에 run별 구조화 로그 기록을 추가함. metrics_aggregate.py로 성공률/지연/재시도 집계를 구현했으며 관련 테스트 통과. |
| ORCH-012 | DONE | P0 | 토큰/비용 가드레일을 실행 정책으로 강제 | 1) soft/hard budget 초과시 분기 코드화 2) Compact Report 검증기 추가 3) 초과시 BLOCKED/요약 처리 규칙 반영 | agent:main:subagent:76e5a9c9-218b-4541-9f20-40c042859f7f | 2026-02-07 23:35 | 2026-02-08 03:30 | Executable token guardrails shipped (validator/budget/action + SQLite enforcement script/events). Added policy mapping docs and tests; full orchestrator test suite passes. |
| ORCH-013 | DONE | P1 | 운영 명령 인터페이스(status/cancel/replan/retry) 정비 | 1) 명령 스펙 문서화 2) 최소 CLI 진입점 구현 3) runbook에 운영 절차 반영 | agent:main:subagent:b5091a31-5f83-401c-a320-3dd464f3d626 | 2026-02-07 23:37 | 2026-02-08 04:00 | Added ops.py/OPS_COMMANDS.md with status-cancel-replan-retry for markdown+sqlite; updated runbook/README and added deterministic ops CLI tests (suite passing). |
| ORCH-014 | DONE | P1 | 제품화 테스트 매트릭스+soak test 설계 | 1) 단위/통합/E2E/장시간 테스트 목록 2) 실패 시나리오 5개 이상 3) 릴리즈 체크리스트 작성 | agent:main:subagent:cf2193bc-b4e0-48cd-a9cd-141c8e3975a7 | 2026-02-07 23:39 | 2026-02-08 05:00 | 제품화 테스트 전략/매트릭스/soak plan 문서 추가 및 README 실행순서 반영 완료. python3 -m pytest automation/orchestrator/tests -q 실행(38 passed)으로 회귀 이상 없음 확인. |
| ORCH-015 | DONE | P0 | Reviewer Gate 자동 검토/재시도 루프 도입 | 1) reviewer_gate.py 구현(판정 PASS/RETRY/BLOCK) 2) 실행 결과 기반 자동 재큐잉 로직 추가 3) README/정책 문서에 운영 플로우 반영 | agent:main:subagent:cbb451c1-e50e-4350-91e3-c0d135a4ea4d | 2026-02-07 23:53 | 2026-02-08 02:00 | Implemented reviewer_gate + review_and_route (md/sqlite), added policy/docs, added deterministic tests for pass/retry/block and routing; full orchestrator test suite green (45 passed). |
| ORCH-016 | DONE | P1 | tmux 관제에서 작업 즉시 생성 명령(예시 포함) 정리 | tmux 관제에서 작업 즉시 생성 명령(예시 포함)... 수행 완료 + 변경사항/검증결과 notes 기록 | worker:doc-1 | 2026-02-08 14:49 | - | tmux/README에 자연어 즉시 작업 생성 명령 정리 완료 |
| ORCH-017 | DONE | P1 | run_dashboard.sh 사용법을 한글 quickstart로 정리 | run_dashboard.sh 사용법을 한글 qui... 수행 완료 + 변경사항/검증결과 notes 기록 | worker:doc-2 | 2026-02-08 14:49 | - | TMUX_QUICKSTART_KO.md 작성 및 README 링크 추가 완료 |
| ORCH-018 | DONE | P1 | ops workers 출력을 fleet 패널에서 더 잘 보이게 문구 개선 | ops workers 출력을 fleet 패널에서 더... 수행 완료 + 변경사항/검증결과 notes 기록 | worker:ux-1 | 2026-02-08 14:49 | - | ops workers 출력에 우선순위 분포(p0/p1/p2) 추가 + fleet 문구 개선 완료 |
| ORCH-019 | BLOCKED | P0 | [쿠팡구매/safe] 생수 2L 6개 / qty=1 / max_price=20000 / must=로켓배송 | 1) 쿠팡 후보 3개 비교(가격/배송/판매자/리뷰); 2) 제약 충족 최종 1개 선정; 3) 장바구니 담기 및 옵션/수량 확인; 4) 결제 직전 도달 후 사용자 승인 요청 | worker:coupang-1 | 2026-02-08 20:34 | - | coupang_intake:20260208-2034 mode=safe / replan:사용자 포커스 변경(72h 고도화 우선), 구매자동화 대기 / replan:user_drop:coupang_scope / cancelled_by_operator |
| ORCH-020 | BLOCKED | P0 | [쿠팡구매/safe] 키친타월 / qty=2 / must=리뷰 1천개 이상 | 1) 쿠팡 후보 3개 비교(가격/배송/판매자/리뷰); 2) 제약 충족 최종 1개 선정; 3) 장바구니 담기 및 옵션/수량 확인; 4) 결제 직전 도달 후 사용자 승인 요청 | worker:coupang-2 | 2026-02-08 20:35 | - | coupang_intake:20260208-2035 mode=safe / replan:사용자 포커스 변경(72h 고도화 우선), 구매자동화 대기 / replan:user_drop:coupang_scope / cancelled_by_operator |
| ORCH-021 | DONE | P0 | dispatcher.py 실행 엔트리포인트 구현(DB 우선, md fallback) | 1) automation/orchestrator/dispatcher.py 추가 2) PENDING 선점/owner_session 기록 3) 단위테스트 3개 이상 통과 | worker:core-1 | 2026-02-08 23:41 | 2026-02-09 12:00 | dispatcher.py 추가(DB/md pick) + test_dispatcher.py 3개 통과 |
| ORCH-022 | DONE | P0 | watchdog.py 실행 엔트리포인트 구현(stale IN_PROGRESS 복구) | 1) automation/orchestrator/watchdog.py 추가 2) lease/stale 판정 기반 복구 3) 단위테스트 3개 이상 통과 | worker:core-2 | 2026-02-08 23:41 | 2026-02-09 18:00 | watchdog.py 추가(stale reset/retry) + test_watchdog.py 3개 통과 |
| ORCH-023 | DONE | P0 | ops kpi 커맨드 추가(지연/성공률/재시도 집계) | 1) ops.py에 kpi 서브커맨드 2) metrics_aggregate 연계 출력 3) 테스트 2개 이상 통과 | worker:core-3 | 2026-02-08 23:42 | 2026-02-10 12:00 | ops kpi 커맨드 추가 + OPS_COMMANDS/README 반영 + test_ops kpi 스모크 포함 |
| ORCH-024 | DONE | P1 | DB SSOT 전환 가드(consistency-check + md read-only 규칙) | 1) consistency-check 추가 2) README/OPS 문서 반영 3) 테스트 통과 | worker:core-4 | 2026-02-08 23:44 | 2026-02-10 18:00 | consistency-check 추가(md/db drift 검증) + ORCH_QUEUE_MD_READ_ONLY 규칙 도입 + docs 반영 |
| ORCH-025 | BLOCKED | P1 | 쿠팡 워크플로우 상태머신 v1(SEARCH/CANDIDATE/CART/APPROVAL/ORDERED) | 1) 상태전이 규칙 코드화 2) safe/auto 분기 3) 테스트 통과 | - | - | 2026-02-11 18:00 | 72h:D3 / cancelled_by_operator |
| ORCH-026 | DONE | P1 | 운영 알림 규칙 추가(실패율/지연 p95/stale 감지) | 1) alert 규칙 문서화 2) CLI 출력 임계치 경고 추가 3) 테스트 통과 | worker:core-5 | 2026-02-08 23:46 | 2026-02-11 18:00 | ops kpi 임계치(alert) 추가(실패율/latency p95/stale) + fail-on-alert 옵션 + 문서/테스트 통과 |

## 작성 팁
- 새 작업은 위 테이블에 한 줄 추가
- task는 짧고 명확하게, success_criteria는 체크 가능한 조건으로 작성
- 사람이 개입해야 하면 `BLOCKED`로 바꾸고 notes에 필요한 입력을 적기
