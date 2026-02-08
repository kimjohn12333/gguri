# Token Efficiency Policy v1 (MVP)

목적: 오케스트레이터 운영 시 **컨텍스트 낭비를 줄이고**, Lead/Worker 보고를 짧고 재사용 가능하게 표준화한다.

## 1) 적용 범위
- **Main session(Lead)**
  - 작업 분해, 우선순위, 의존성/리스크 판단 담당
  - Worker 결과를 통합해 최종 결론만 보고
- **Subagent(Worker)**
  - 할당 범위 내 실행만 수행
  - 아래 `Compact Report` 템플릿으로만 결과 보고

## 2) Compact Report (엄격 템플릿)
Worker 최종 응답은 아래 형식만 허용:

```md
[REPORT <task-id>]
Status: DONE | FAILED | BLOCKED
Files:
- <path1>
- <path2>
Diff-Summary:
- <변경 요약 1>
- <변경 요약 2>
Validation:
- <검증 명령/결과 1>
Risks:
- <없으면 None>
Next:
- <필요 시 1줄>
```

규칙:
- 본문 장문 붙여넣기 금지(코드/문서 전체 paste 금지)
- `Files` + `Diff-Summary`를 항상 먼저 작성
- bullet 총량 권장 10개 이내, 섹션 생략 금지(`없으면 None`)

## 3) Context Budget 정책
- **Soft threshold: 2,000 tokens**
  - 조치: 이전 경과를 3~5줄로 압축 요약 후 진행
  - 조치: 중복 설명/재인용 제거, 파일 경로 참조로 대체
- **Hard threshold: 3,500 tokens**
  - 조치: 즉시 진행 중단 후 요약 체크포인트 작성
  - 조치: `!replan` 또는 새 턴으로 분리 후 계속

## 4) Summarize/Trim 트리거 & Escalation
트리거(하나라도 충족 시 요약 실행):
- 대화가 10턴 초과
- 동일 파일/로그 재인용 2회 이상
- 범위 변경 또는 의존성 변경 발생

Escalation 규칙:
1. Worker: 요약본으로 전환(핵심 변경 + 리스크만)
2. Lead: 필요 시 작업 재분할(`!replan`) 또는 후속 task로 분리
3. Hard 초과 위험: 장문 분석 중단, 결정/다음 액션만 남김

## 5) 실행 정책 매핑 (condition -> action -> queue status)

| Condition | Action | Queue status transition |
|---|---|---|
| budget state = `OK` AND compact violations 없음 | `ALLOW` | 상태 유지(변경 없음) |
| budget state = `SOFT_EXCEEDED` OR 경미한 위반(요약 필요) | `SUMMARIZE` | 상태 유지 + `queue_events`에 `guardrail` 기록 |
| budget state = `HARD_EXCEEDED` | `BLOCK` | `IN_PROGRESS/PENDING -> BLOCKED` + reason 기록 |
| compact report 중대 위반(예: 헤더/필수섹션 누락, code fence paste) | `BLOCK` | `IN_PROGRESS/PENDING -> BLOCKED` + reason 기록 |

실행 기준(코드):
- 상태 판정: `token_guardrails.check_budget()`
- 위반 검증: `token_guardrails.validate_compact_report()`
- 최종 액션: `token_guardrails.decide_action()`
- DB 반영: `enforce_guardrails.py` + `db_store.append_guardrail_event()/mark_blocked()`

## 6) Good vs Bad 보고 예시
### Good
- 파일 경로와 변경 요약 먼저 제시
- 검증 결과를 명령/결과로 1줄씩 표기
- 리스크 없으면 `None` 명시

예시:
```md
[REPORT ORCH-006-W1]
Status: DONE
Files:
- automation/orchestrator/TOKEN_POLICY.md
- automation/orchestrator/TEAM_MODE.md
Diff-Summary:
- Token 정책 문서 신설(범위/템플릿/threshold 추가)
- TEAM_MODE handoff 규칙을 Files-first로 정렬
Validation:
- markdown lint 수동 확인: 헤더/목록 구조 이상 없음
Risks:
- None
Next:
- ORCH-006 done 처리 필요
```

### Bad
- 변경 파일 경로 없이 장문 배경 설명만 작성
- 문서 전체를 붙여넣어 토큰 과다 사용
- 검증/리스크 섹션 누락
