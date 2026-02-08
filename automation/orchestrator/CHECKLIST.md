# 오케스트레이터 수동 운영 체크리스트

## 일일 점검 (Daily)
- [ ] `QUEUE.md`에서 `PENDING/IN_PROGRESS/BLOCKED` 상태 작업 확인
- [ ] `IN_PROGRESS` 작업의 `owner_session`, `started_at_kst` 갱신 여부 확인
- [ ] `FAILED` 작업의 실패 원인과 재시도 계획(notes) 점검
- [ ] 크론/하트비트 실행 로그에서 최근 오류 유무 확인
- [ ] 당일 신규 요청이 우선순위(`P0/P1/P2`)에 맞게 큐에 반영됐는지 확인

## 주간 점검 (Weekly)
- [ ] 완료(`DONE`) 항목에서 재사용 가능한 운영 패턴/교훈 문서화
- [ ] 반복 실패 작업의 공통 원인 분석 및 체크리스트/가이드 업데이트
- [ ] `BLOCKED` 장기 항목 정리(해제 조건 명시 또는 보류 결정)
- [ ] 불필요하게 오래된 notes/메타데이터 정리
- [ ] 운영 문서(`README.md`, `DISPATCHER.md`, `WATCHDOG.md`) 최신성 점검

## 수동 실행 명령 (Manual Run Commands)
```bash
# 1) 큐 확인
cat automation/orchestrator/QUEUE.md

# 2) 오케스트레이터 디렉터리 빠른 점검
ls -la automation/orchestrator

# 3) 워크스페이스 변경사항 확인
git -C . status

# 4) OpenClaw 게이트웨이 상태 확인
openclaw gateway status

# 5) 최근 오케스트레이터 관련 변경 추적
git -C . log --oneline -- automation/orchestrator
```
