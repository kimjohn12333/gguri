#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"
RESET="${2:-}"

WORKDIR="${ORCH_WORKDIR:-/Users/jm/.openclaw/workspace}"
SESSION="${ORCH_TMUX_SESSION:-orch-ui}"
SOCKET_DIR="${OPENCLAW_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/openclaw-tmux-sockets}"
SOCKET="${ORCH_TMUX_SOCKET:-$SOCKET_DIR/openclaw.sock}"
LOG_PATH="$WORKDIR/automation/orchestrator/logs/orch_runs.jsonl"
QUEUE_PATH="$WORKDIR/automation/orchestrator/QUEUE.md"

mkdir -p "$SOCKET_DIR"
mkdir -p "$(dirname "$LOG_PATH")"
touch "$LOG_PATH"

start_session() {
  if tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    if [[ "$RESET" == "--reset" ]]; then
      tmux -S "$SOCKET" kill-session -t "$SESSION"
    else
      return 0
    fi
  fi

  # Pane 0: status monitor
  tmux -S "$SOCKET" new-session -d -s "$SESSION" -n orchestrator \
    "cd '$WORKDIR'; while true; do clear; date; echo '=== ORCH STATUS ==='; python3 -m automation.orchestrator.ops status; sleep 2; done"

  # Pane 1: log tail (right)
  tmux -S "$SOCKET" split-window -h -t "$SESSION":0 \
    "cd '$WORKDIR'; tail -n 120 -F '$LOG_PATH'"

  # Pane 2: queue tail (bottom-left)
  tmux -S "$SOCKET" split-window -v -t "$SESSION":0.0 \
    "cd '$WORKDIR'; while true; do clear; echo '=== QUEUE (tail) ==='; tail -n 120 '$QUEUE_PATH'; sleep 4; done"

  # Pane 3: control shell (bottom-right)
  tmux -S "$SOCKET" split-window -v -t "$SESSION":0.1 \
    "cd '$WORKDIR'; clear; \
     echo '=== ORCH CONTROL SHELL ==='; \
     echo '자주 쓰는 명령:'; \
     echo '  python3 -m automation.orchestrator.ops status'; \
     echo '  python3 -m automation.orchestrator.nl_intake submit --request \"로그 정리, 재시도 보강, 문서 업데이트\" --parallel 3'; \
     echo '  python3 -m automation.orchestrator.orch add --id ORCH-016 --priority P1 --task \"...\" --success-criteria \"...\"'; \
     echo '  python3 -m automation.orchestrator.ops retry --id ORCH-016'; \
     echo '  python3 -m automation.orchestrator.ops cancel --id ORCH-016'; \
     echo '  python3 -m automation.orchestrator.ops replan --id ORCH-016 --notes \"...\"'; \
     echo; \
     echo '팁: Ctrl+b 방향키=패널 이동, Ctrl+b d=detach'; \
     exec /bin/bash -i"

  # Keep the 2x2 split shape as created above (status/log + queue/control)
  tmux -S "$SOCKET" select-pane -t "$SESSION":0.2

  # Window 1: fleet overview (worker allocation / pending / logs)
  tmux -S "$SOCKET" new-window -t "$SESSION" -n fleet \
    "cd '$WORKDIR'; while true; do clear; date; echo '=== WORKER OVERVIEW (status) ==='; python3 -m automation.orchestrator.ops status; sleep 2; done"

  tmux -S "$SOCKET" split-window -h -t "$SESSION":fleet \
    "cd '$WORKDIR'; while true; do clear; echo '=== WHO IS DOING WHAT (owner_session) ==='; python3 -m automation.orchestrator.ops workers; sleep 2; done"

  tmux -S "$SOCKET" split-window -v -t "$SESSION":fleet.0 \
    "cd '$WORKDIR'; while true; do clear; echo '=== PENDING TOP ==='; python3 -m automation.orchestrator.orch list --status PENDING | head -n 20; sleep 3; done"

  tmux -S "$SOCKET" split-window -v -t "$SESSION":fleet.1 \
    "cd '$WORKDIR'; while true; do clear; echo '=== RECENT ORCH LOGS ==='; tail -n 60 '$LOG_PATH'; sleep 3; done"

  tmux -S "$SOCKET" select-layout -t "$SESSION":fleet tiled
  tmux -S "$SOCKET" select-window -t "$SESSION":fleet
}

case "$ACTION" in
  start)
    start_session
    echo "Dashboard ready"
    echo "SOCKET=$SOCKET"
    echo "SESSION=$SESSION"
    echo
    echo "Attach: tmux -S '$SOCKET' attach -t '$SESSION'"
    ;;
  attach)
    start_session
    if [[ ! -t 1 ]]; then
      echo "TTY not detected. Run this in your terminal:"
      echo "TMUX= tmux -S '$SOCKET' attach -t '$SESSION'"
      exit 0
    fi
    TMUX= tmux -S "$SOCKET" attach -t "$SESSION"
    ;;
  fleet)
    start_session
    tmux -S "$SOCKET" select-window -t "$SESSION":fleet
    if [[ ! -t 1 ]]; then
      echo "TTY not detected. Run this in your terminal:"
      echo "TMUX= tmux -S '$SOCKET' attach -t '$SESSION'"
      exit 0
    fi
    TMUX= tmux -S "$SOCKET" attach -t "$SESSION"
    ;;
  stop)
    tmux -S "$SOCKET" kill-session -t "$SESSION"
    echo "Stopped $SESSION"
    ;;
  status)
    tmux -S "$SOCKET" list-sessions || true
    ;;
  *)
    echo "Usage: $0 {start|attach|fleet|stop|status} [--reset]"
    exit 1
    ;;
esac
