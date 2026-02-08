# Reliability Policy (v1)

## 1) Lease lifecycle
- 대상: `IN_PROGRESS` 실행 아이템
- `acquire_lease(item_id, owner, lease_seconds)`
  - 유효 lease가 없을 때만 성공
  - 성공 시 `lease_owner`, `lease_expires_at` 설정
- `renew_lease(...)`
  - 동일 owner + 미만료 lease에서만 연장 성공
- `release_lease(...)`
  - 동일 owner만 해제 가능
- lease 만료된 `IN_PROGRESS` 항목은 timeout 후보로 간주

## 2) Idempotency behavior
- `idempotency_key`는 nullable
- `pick_next` 시 동일 `idempotency_key`로 이미 `DONE`인 항목이 있으면:
  - 중복 항목은 실행하지 않고 `DONE`으로 skip 처리
  - 이벤트(`idempotency_skipped`) 기록
- 목적: 재등록/중복 enqueue로 인한 재실행 방지

## 3) Retry/backoff and stop conditions
- 대상: `FAILED` 또는 lease 만료 timeout(`IN_PROGRESS + lease_expires_at <= now`)
- 함수: `retry_eligible_items(...)`
- 규칙:
  - `attempt_count < max_attempts` 일 때만 재시도
  - 재진입 백오프 메타: 1m, 3m, 10m (시도 횟수 기반)
  - 재시도 시 상태를 `PENDING`으로 복귀, lease/owner 초기화
- 중단 조건:
  - `attempt_count >= max_attempts`

## 4) Failure classification quick guide
- Transient (재시도 권장)
  - 네트워크 일시 장애, rate limit, 외부 서비스 타임아웃
  - 조치: `FAILED` 기록 후 retry 루프에서 자동 복귀
- Permanent (재시도 비권장)
  - 잘못된 입력, 권한 불충분, 로직 버그 확정
  - 조치: `FAILED` + 원인 명시, 사람 확인 후 재큐잉 여부 결정
