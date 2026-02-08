# Orchestrator Watchdog (optional cron isolated run)

목표: `IN_PROGRESS`가 너무 오래 멈춘 경우 재시도 가능 상태로 되돌린다.

## 절차
1. `automation/orchestrator/QUEUE.md`를 읽는다.
2. `IN_PROGRESS` 항목 중 `started_at_kst`가 현재 시각 대비 6시간 이상 지난 항목을 찾는다.
3. 해당 항목을 아래처럼 업데이트:
   - `status` -> `PENDING`
   - `owner_session` -> `-`
   - `notes` 끝에 `[watchdog] stale reset` 추가
4. 변경이 없으면 종료.

## 안전 규칙
- 메시지 전송 금지
- queue 파일 외 변경 금지
