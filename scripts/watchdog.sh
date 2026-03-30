#!/bin/bash
#
# Adaptive Research Watchdog
# Monitors tmux sessions for rate-limited research loops and resumes them.
# Also detects dead sessions and restarts (max 3 attempts).
#
# Usage:
#   ./watchdog.sh           # Start monitoring (foreground)
#   ./watchdog.sh --stop    # Kill running watchdog
#   ./watchdog.sh --status  # Check if running
#
# Typically started automatically by /auto-run when using --batch mode.

set -u

CHECK_INTERVAL="${WATCHDOG_INTERVAL:-15}"
PAUSE_COOLDOWN="${WATCHDOG_PAUSE_COOLDOWN:-300}"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/adaptive-research"
LOG_FILE="$LOG_DIR/watchdog.log"
PIDFILE="$LOG_DIR/watchdog.pid"
STATE_DIR="$LOG_DIR/watchdog-state"

mkdir -p "$LOG_DIR" "$STATE_DIR" 2>/dev/null

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; echo "$1"; }

trim_log() {
    local lines
    lines=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
    [ "$lines" -gt 2000 ] && tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
}

# Find the project dir from any active autorun tmux session
find_project_dir() {
    local session_dir
    session_dir=$(tmux display-message -t autorun -p '#{pane_current_path}' 2>/dev/null)
    echo "${session_dir:-$(pwd)}"
}

handle_pause() {
    local state_file="$1"
    log "PAUSE: Detected in $state_file. Waiting ${PAUSE_COOLDOWN}s..."
    sleep "$PAUSE_COOLDOWN"

    if [ -f "$state_file" ] && grep -q '^paused_at:' "$state_file" 2>/dev/null; then
        # Remove paused_at
        TEMP="$state_file.tmp.$$"
        grep -v '^paused_at:' "$state_file" > "$TEMP" && mv "$TEMP" "$state_file"

        # Find target session
        TARGET=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -E '^autorun' | head -1)
        if [ -n "$TARGET" ]; then
            PROMISE=$(grep '^completion_promise:' "$state_file" 2>/dev/null | sed 's/completion_promise: *//' | tr -d '"')
            [ -z "$PROMISE" ] && PROMISE="DONE"
            tmux send-keys -t "$TARGET" "Rate limit pause over. Continue research. When done: <promise>${PROMISE}</promise>" Enter
            log "RESUME [$TARGET]: Pause cleared"
        else
            log "PAUSE: No target session found to resume"
        fi
    fi
}

monitor() {
    # Singleton
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Watchdog already running (PID $(cat "$PIDFILE"))"
        exit 0
    fi
    echo $$ > "$PIDFILE"
    trap 'rm -f "$PIDFILE"' EXIT

    log "START: Watchdog monitoring (interval: ${CHECK_INTERVAL}s, pause cooldown: ${PAUSE_COOLDOWN}s)"

    local counter=0
    while true; do
        PROJECT_DIR=$(find_project_dir)

        # --- Pause detection ---
        STATE_FILE="$PROJECT_DIR/_autonomous/loop.state.md"
        if [ -f "$STATE_FILE" ] && grep -q '^paused_at:' "$STATE_FILE" 2>/dev/null; then
            handle_pause "$STATE_FILE"
        fi

        # --- Dead session recovery (max 3 restarts) ---
        if [ -f "$STATE_FILE" ] && ! tmux has-session -t autorun 2>/dev/null; then
            RESTART_COUNTER="$STATE_DIR/restart_count"
            RESTART_COUNT=$(cat "$RESTART_COUNTER" 2>/dev/null || echo "0")
            DEAD_MARKER="$STATE_DIR/dead_since"

            if [ "$RESTART_COUNT" -ge 3 ]; then
                [ "$RESTART_COUNT" -eq 3 ] && log "CRITICAL: 3 restart attempts failed. Manual intervention needed." && echo "4" > "$RESTART_COUNTER"
            else
                if [ -f "$DEAD_MARKER" ]; then
                    DEAD_AGE=$(( $(date +%s) - $(cat "$DEAD_MARKER") ))
                else
                    date +%s > "$DEAD_MARKER"
                    DEAD_AGE=0
                fi

                if [ "$DEAD_AGE" -gt 120 ]; then
                    log "RECOVERY: Attempt $((RESTART_COUNT + 1))/3..."
                    PROMPT_FILE=$(mktemp)
                    awk '/^---$/{i++; next} i>=2' "$STATE_FILE" > "$PROMPT_FILE"
                    if [ -s "$PROMPT_FILE" ]; then
                        tmux new-session -d -s autorun -c "$PROJECT_DIR" "claude --permission-mode acceptEdits"
                        sleep 5
                        tmux load-buffer "$PROMPT_FILE"
                        tmux paste-buffer -t autorun
                        tmux send-keys -t autorun Enter
                        log "RECOVERY: Restarted autorun session"
                    fi
                    rm -f "$PROMPT_FILE" "$DEAD_MARKER"
                    echo "$((RESTART_COUNT + 1))" > "$RESTART_COUNTER"
                fi
            fi
        else
            rm -f "$STATE_DIR/dead_since" "$STATE_DIR/restart_count" 2>/dev/null
        fi

        # --- Rate limit detection in tmux output ---
        if tmux has-session -t autorun 2>/dev/null; then
            OUTPUT=$(tmux capture-pane -t autorun -p -S -15 2>/dev/null)
            if echo "$OUTPUT" | grep -qiE 'rate.?limit|429|too many requests|overloaded'; then
                LAST_RL="$STATE_DIR/last_ratelimit"
                NOW=$(date +%s)
                PREV=$(cat "$LAST_RL" 2>/dev/null || echo "0")
                if [ $((NOW - PREV)) -gt 30 ]; then
                    log "RATE LIMIT: Detected in autorun session. Waiting 65s..."
                    echo "$NOW" > "$LAST_RL"
                    sleep 65
                    FRESH=$(tmux capture-pane -t autorun -p -S -5 2>/dev/null)
                    if echo "$FRESH" | grep -qE '^\s*[>❯]\s*$'; then
                        tmux send-keys -t autorun "Rate limit is over. Continue your research where you left off." Enter
                        log "RESUME: Sent continue message"
                    fi
                fi
            fi
        fi

        counter=$((counter + 1))
        [ $((counter % 100)) -eq 0 ] && trim_log
        sleep "$CHECK_INTERVAL"
    done
}

case "${1:-}" in
    --stop)
        if [ -f "$PIDFILE" ]; then
            kill "$(cat "$PIDFILE")" 2>/dev/null && log "STOP: Killed" || echo "Not running"
            rm -f "$PIDFILE"
        else
            echo "Not running"
        fi
        ;;
    --status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            echo "Watchdog running (PID $(cat "$PIDFILE"))"
            tail -5 "$LOG_FILE" 2>/dev/null
        else
            echo "Watchdog not running"
            rm -f "$PIDFILE" 2>/dev/null
        fi
        ;;
    --help|-h)
        head -13 "$0" | tail -11
        ;;
    *)
        monitor
        ;;
esac
