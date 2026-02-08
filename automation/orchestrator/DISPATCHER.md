# Orchestrator Dispatcher (for cron isolated runs)

목표: `automation/orchestrator/QUEUE.md`에서 작업을 집어 서브에이전트로 실행한다.

## 디스패치 모드 선택 규칙 (순차/병렬)
- 기본 모드: **순차(single-pick)**
  - 일반 cron tick에서는 항상 1개만 집는다.
- 병렬 모드: **명시적으로 활성화된 경우에만** 허용
  - 조건 예시: 백로그 급증, 마감 임박 작업 다수, 운영자가 병렬 실행을 지시한 경우
  - 병렬에서도 우선순위/정렬 규칙은 동일하게 적용한다.
- 순차/병렬 공통으로 `BLOCKED`, `IN_PROGRESS` 항목은 새로 집지 않는다.

## 최대 워커 수 규칙
- 기본 최대 워커 수: **3**
- 절대 상한(hard cap): **5** (어떤 경우에도 초과 금지)
- 현재 `IN_PROGRESS` 개수를 먼저 계산하고, `남은 슬롯 = max_workers - in_progress` 만큼만 추가 dispatch 한다.
- 남은 슬롯이 0이면 이번 tick에서는 dispatch 하지 않는다.

## 절차
1. `automation/orchestrator/QUEUE.md`를 읽는다.
2. 후보 선택:
   - `status == PENDING` 우선
   - 우선순위: `P0 > P1 > P2`
   - 동률이면 테이블에서 먼저 나온 항목
3. 후보가 없으면 종료한다(아무 메시지도 보내지 않음).
4. 후보가 있으면(순차 1개 / 병렬 N개):
   - 해당 row의 `status`를 `IN_PROGRESS`로 변경
   - `started_at_kst`를 현재 KST 시각(YYYY-MM-DD HH:mm)으로 기록
5. 각 항목에 대해 `sessions_spawn`으로 작업 실행:
   - `label`: `orch-<id>`
   - `runTimeoutSeconds`: 5400
   - `cleanup`: `keep`
   - `task` 본문에 아래를 포함:
     - queue 파일 경로: `automation/orchestrator/QUEUE.md`
     - 대상 row id: `<id>`
     - 완료 시 row 업데이트 규칙:
       - 성공: `DONE`
       - 실패: `FAILED`
       - `notes`에 1~2줄 요약 남기기
6. `owner_session`에 spawn된 `childSessionKey`를 기록한다.

## 실패 시 복구 플로우
1. 스폰 실패(세션 생성 실패):
   - row를 즉시 `FAILED`로 변경
   - `notes`에 실패 원인(1줄)과 재시도 필요 여부 기록
2. 워커 타임아웃/비정상 종료:
   - row를 `FAILED`로 변경
   - `notes`에 타임아웃/종료 유형과 마지막 확인 시각 기록
3. 부분 실패(병렬 중 일부만 실패):
   - 성공 건은 `DONE`, 실패 건은 `FAILED`로 개별 처리
   - 다음 tick에서 `FAILED` 항목은 운영 규칙에 따라 재큐잉(add 또는 status 조정)한다.
4. 복구 원칙:
   - 조용히 자동 무한 재시도 금지
   - 원인 불명 실패가 2회 이상 반복되면 `BLOCKED` 전환 후 사람 입력을 요청한다.

## 안전 규칙
- 사용자에게 선제 메시지 전송 금지 (요청받았을 때만 보고)
- queue 파일 외의 설정/시스템 변경 금지
- 병렬 모드가 아니면 항상 1개만 dispatch
