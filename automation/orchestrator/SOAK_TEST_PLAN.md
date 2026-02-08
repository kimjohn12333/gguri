# Soak Test Plan (ORCH-014)

## 1) 목적
장시간 실행에서 오케스트레이터의 안정성, 재시도 복원력, 중복 실행 방지, 운영 개입 가능성을 검증한다.

## 2) 사전 조건
- 테스트 기준 버전 고정(커밋 SHA 기록)
- SQLite DB 초기화 및 로그 경로 준비
  - `automation/orchestrator/db/queue.db`
  - `automation/orchestrator/logs/soak/`
- 기본 테스트(단위/통합) 선통과

## 3) Soak Profile

### Profile A: 24h 안정성 검증
- 기간: 24시간
- 목표: 정상 운영 중 지표 안정성 확인
- 부하 형태:
  - task arrival: 평균 분당 2건, 15분마다 burst(분당 8건, 3분 지속)
  - 실패 주입: 전체의 5% transient error(timeout/rate-limit)
  - retry: 정책(backoff 1m/3m/10m)에 따른 자동 복귀
- 기대 결과:
  - 처리 성공률(Success Rate) >= 99.0%
  - duplicate dispatch 0건
  - lease timeout 복구율 >= 99%

### Profile B: 72h 스트레스 검증
- 기간: 72시간
- 목표: 경합/잠금/재시도 누적 상황에서도 무중단 운영 가능 여부 확인
- 부하 형태:
  - task arrival: 평균 분당 5건, 시간당 1회 burst(분당 20건, 5분 지속)
  - 실패 주입:
    - transient 10% (네트워크/timeout)
    - DB lock/busy 2%
    - duplicate enqueue 시도 1%
    - guardrail hard exceed 이벤트 1%
  - retry: 최대 3회, max_attempts 도달 시 실패 고정
- 기대 결과:
  - 처리 성공률 >= 97.0%
  - p95 end-to-end latency <= 120s
  - idempotency skip이 중복 실행을 100% 차단

## 4) SLO / SLI
- SLI-1 성공률: `DONE / (DONE + FAILED)`
- SLI-2 지연: enqueue→terminal 상태 전환 시간 (p95)
- SLI-3 복구율: transient 실패 후 retry로 DONE 전환 비율
- SLI-4 중복 방지: duplicate dispatch 발생 대비 실제 중복 실행 비율

SLO 기준:
- 24h: 성공률 >= 99.0%, p95 <= 90s
- 72h: 성공률 >= 97.0%, p95 <= 120s
- 공통: 실제 중복 실행 0건

## 5) Abort Conditions (즉시 중단/에스컬레이션)
다음 중 하나라도 만족하면 soak를 중단하고 incident 전환:
1. 30분 이동창 성공률 < 95%
2. 실제 중복 실행 1건 이상 확인
3. DB lock/timeout으로 10분 이상 상태 전이 정지
4. guardrail hard exceed 미차단(차단 실패) 1건 이상
5. 로그 누락 또는 지표 수집 불능 15분 이상

## 6) 주요 실패 시나리오 및 기대 처리
1. **Lease contention**: 동시 pick 경합 시 한 세션만 lease 성공, 나머지 재시도 대기
2. **Stuck IN_PROGRESS**: lease 만료 감지 후 retry 루프로 PENDING 복귀
3. **Duplicate dispatch**: idempotency key 기준 skip + 이벤트 기록
4. **Budget hard exceed**: `BLOCKED` 전환, 운영자 replan 필요
5. **DB lock/timeouts**: transient로 분류하여 backoff 재시도, 반복 시 failover/운영개입
6. **Retry storm**: max_attempts 도달 항목 격리 후 원인군 분석

## 7) 실행 절차
1. 사전 테스트 실행: `pytest automation/orchestrator/tests -q`
2. 24h profile 실행 및 로그 저장
3. 중간 점검(6h 간격): status/metrics/에러 버킷 확인
4. 72h profile 실행 및 incident 대응
5. 결과 집계:
   - `automation/orchestrator/logs/soak/soak_24h.jsonl`
   - `automation/orchestrator/logs/soak/soak_72h.jsonl`
   - `automation/orchestrator/reports/soak/soak_summary.md`

## 8) On-call Runbook Snippet (Incident 대응)
```bash
# 1) 현재 상태 확인
python3 automation/orchestrator/ops.py status

# 2) 문제 항목 격리(취소)
python3 automation/orchestrator/ops.py cancel --id ORCH-XXX

# 3) 재계획(원인/조치 기록)
python3 automation/orchestrator/ops.py replan --id ORCH-XXX --notes "DB lock hotspot, split workload"

# 4) 복구 재시도
python3 automation/orchestrator/ops.py retry --id ORCH-XXX

# 5) 최종 종료 처리
python3 automation/orchestrator/orch.py done --id ORCH-XXX --notes "incident mitigated"
# 또는
python3 automation/orchestrator/orch.py fail --id ORCH-XXX --notes "persistent failure; action required"
```

Incident 기록 필수 항목:
- 발생 시각(KST), 영향 범위, 탐지 지표(SLI), 임시조치, 근본원인, 재발방지 액션
