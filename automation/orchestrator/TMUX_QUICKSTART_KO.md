# tmux 관제 Quickstart (KO)

## 0) 한 번에 관제창 띄우기
```bash
cd /Users/jm/.openclaw/workspace
automation/orchestrator/run_dashboard.sh fleet
```

## 1) 화면 구성
- `orchestrator` 창: 상태/큐/로그/컨트롤 쉘
- `fleet` 창: 워커 배분(`ops workers`) + pending + 로그

창 전환:
- `Ctrl+b` 후 `n` (다음)
- `Ctrl+b` 후 `p` (이전)
- `Ctrl+b` 후 `d` (분리/백그라운드)

## 2) 자연어로 작업 넣기 (컨트롤 쉘에서)
```bash
python3 -m automation.orchestrator.nl_intake submit \
  --request "로그 정리, 재시도 보강, 문서 업데이트" \
  --parallel 3 \
  --priority P1
```

## 3) 진행 확인
```bash
python3 -m automation.orchestrator.ops status
python3 -m automation.orchestrator.ops workers
python3 -m automation.orchestrator.orch list --status IN_PROGRESS
```

## 4) 운영 명령
```bash
python3 -m automation.orchestrator.ops retry --id ORCH-016
python3 -m automation.orchestrator.ops cancel --id ORCH-016
python3 -m automation.orchestrator.ops replan --id ORCH-016 --notes "범위 분리"
```

## 5) 종료
```bash
automation/orchestrator/run_dashboard.sh stop
```
