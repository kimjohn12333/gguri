# Reviewer Gate Policy (ORCH-015)

목적: Worker report가 성공 기준을 만족하는지 자동으로 판정하여 큐 상태를 일관되게 전이한다.

## Verdict Decision Table

| Verdict | 조건 | 상태 전이 | 기록 |
|---|---|---|---|
| PASS | 성공 기준 체크리스트가 충족되고, 명시적 실패/블로커 마커가 없음(선택 UI 검증도 통과) | DONE | `review:PASS ...` note + (sqlite) review_gate event |
| RETRY | 체크리스트 일부 미충족 또는 실패 마커 감지, 또는 UI 검증 실패(재시도 여유 있음) | PENDING | attempt 증가 + `review:RETRY attempt=x/y ...` |
| BLOCK | 블로커 마커 감지 또는 재시도 한도 소진(포함: UI 검증 반복 실패) | BLOCKED | `review:BLOCK ...` reason + (sqlite) review_gate event |

## Marker Rules (deterministic)

- Failure marker 예시: `fail`, `error`, `exception`, `incomplete`, `missing`, `todo`
- Block marker 예시: `blocker`, `blocked`, `cannot proceed`, `escalation`
- Block marker가 존재하면 우선순위가 가장 높음(즉시 BLOCK)

## UI Smoke Gate (optional)

`review_and_route.py`에 `--ui-url`(및 `--ui-contains`)를 주면 Playwright-CLI 스모크 검증을 추가한다.

- UI 통과: 기존 verdict 유지(사유에 `ui_validation_passed` 추가)
- UI 실패: 기본적으로 RETRY로 강등
- 단, 이미 재시도 한도에 도달한 경우 UI 실패는 즉시 BLOCK으로 승격

## Retry / Escalation Rules

- `max-retries` 기본값: `3`
- RETRY 판정 시 attempt를 1 증가
- 다음 조건이면 RETRY 대신 BLOCK으로 승격:
  - `attempt_count >= max_retries`
- 즉, 재시도 횟수 소진 시 무한 루프 없이 `BLOCKED`로 종료

## Auditability

- 판정 결과는 `verdict + reasons + missing_checks` 구조로 반환
- note/event에 시도 횟수와 누락 항목을 남겨 사후 분석 가능하도록 유지
- 외부 API/비결정적 모델 호출 없음 (local deterministic heuristic)
