# Agent Team Mode (MVP)

목표: 기존 오케스트레이터 위에서 **Lead 1 + Worker 3** 구조로 병렬 처리하되, 토큰 사용량을 제어한다.

## 1) 팀 모델
- **Team Lead (1)**
  - 작업 분해, 우선순위/의존성 관리
  - Worker 할당/취소/재계획 처리
  - 최종 통합 보고(중복 제거, 파일 경로 중심 요약)
- **Worker A/B/C (3)**
  - 할당된 하위 작업만 수행
  - 결과는 `TOKEN_POLICY.md`의 `Compact Report` 템플릿으로만 보고

## 2) 라이프사이클
1. **create**
   - Lead가 상위 작업을 하위 작업으로 분해
   - `team_task_template.json` 스키마로 task 객체 작성
2. **assign**
   - Lead가 Worker 세션별로 task 할당
   - 의존성(`dependencies`) 미충족 task는 대기
3. **report**
   - Worker는 compact 포맷으로 보고
   - Lead는 중간 요약/최종 요약 작성
4. **shutdown**
   - 모든 task가 DONE/FAILED/BLOCKED면 팀 세션 종료
   - 큐(notes)에 1~2줄 결과 기록

## 3) 명령 프로토콜
- `!status`
  - Lead가 전체 진행률, 남은 작업, blocker를 한 번에 요약
- `!cancel <task-id|worker-role>`
  - 지정 작업/워커 수행 중지, 상태를 `FAILED` 또는 `BLOCKED`로 정리
- `!replan [reason]`
  - 현재 계획 폐기/수정 후 재할당
  - 변경사항: 영향 task, 새 의존성, 예상 토큰 비용

## 4) Worker 메시지 라우팅 (`sessions_send`)
권장 패턴:
1. Lead가 Worker 세션 ID를 보관한다.
2. 할당 시 `sessions_send`로 task payload 전송.
3. Worker는 동일 채널로 결과를 반환.
4. Lead가 응답을 task ID 기준으로 매핑해 상태 갱신.

메시지 본문 규칙:
- 맨 앞에 `[TASK <id>]` 또는 `[REPORT <id>]` prefix 필수
- **핸드오프 기본 규칙**: 결과는 항상 `Files`(경로) + `Diff-Summary`를 먼저 보고하고, 긴 본문/전체 paste는 금지

## 5) Token Efficiency 연동 규칙
세부 기준은 `automation/orchestrator/TOKEN_POLICY.md`를 따른다.

핵심 기본값:
- 보고 포맷: `Compact Report` (섹션 고정)
- Context budget: Soft 2,000 / Hard 3,500
- 트리거 발생 시 요약/trim 후 지속, Hard 근접 시 `!replan` 또는 턴 분리

## 6) 최소 운영 규칙
- Worker는 범위 밖 작업 금지(요청된 task만 수행)
- Lead만 최종 결론/큐 상태 업데이트 수행
- 실패 시 원인 + 다음 액션을 1~2줄로 기록
