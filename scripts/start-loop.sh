#!/bin/bash
#
# Start an autonomous research loop in tmux
# Used for batch runs and persistent sessions.
#
# Usage:
#   ./start-loop.sh "research topic"
#   ./start-loop.sh --preset technique-scout
#   ./start-loop.sh stop
#   ./start-loop.sh status

SESSION="autorun"

case "${1:-}" in
  stop)
    tmux kill-session -t "$SESSION" 2>/dev/null && echo "Research loop stopped." || echo "Not running."
    STATE=$(find . -path "*/_autonomous/loop.state.md" 2>/dev/null | head -1)
    [ -n "$STATE" ] && rm -f "$STATE"
    ;;
  status)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "Research loop is running."
      echo "  Attach: tmux attach -t $SESSION"
      STATE=$(find . -path "*/_autonomous/loop.state.md" 2>/dev/null | head -1)
      if [ -n "$STATE" ] && [ -f "$STATE" ]; then
        grep -E '^iteration:|^max_iterations:|^paused_at:' "$STATE"
      fi
      tmux capture-pane -t "$SESSION" -p -S -3 2>/dev/null
    else
      echo "Research loop not running."
    fi
    ;;
  *)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "Already running. Stop first: $0 stop"
      exit 1
    fi
    if ! command -v tmux > /dev/null 2>&1; then
      echo "Error: tmux is required for persistent research loops."
      echo "Install: brew install tmux (macOS) or apt install tmux (Linux)"
      exit 1
    fi
    PROMPT="$*"
    if [ -z "$PROMPT" ]; then
      echo "Usage: $0 \"research topic\" or $0 --preset name"
      exit 1
    fi
    echo "Note: Starting Claude with bypassPermissions (autonomous writes to _autonomous/)."
    echo "Press Ctrl-C within 3 seconds to cancel..."
    sleep 3
    # Start interactive Claude session, inject prompt via tmux buffer
    tmux new-session -d -s "$SESSION" "claude --permission-mode acceptEdits"
    sleep 5
    PROMPT_FILE=$(mktemp)
    printf '%s' "/auto-run $PROMPT" > "$PROMPT_FILE"
    tmux load-buffer "$PROMPT_FILE"
    tmux paste-buffer -t "$SESSION"
    tmux send-keys -t "$SESSION" Enter
    rm -f "$PROMPT_FILE"
    echo "Research loop started: $PROMPT"
    echo "  Attach: tmux attach -t $SESSION"
    echo "  Stop:   $0 stop"
    echo "  Status: $0 status"
    ;;
esac
