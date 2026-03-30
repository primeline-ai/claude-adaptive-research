#!/bin/bash
#
# StopFailure Hook — handles API errors during autonomous loops
# Detects rate limits, auth errors, server errors.
# Rate limit: pauses the loop (watchdog resumes after cooldown).
# Other errors: logs and allows exit.
#
# Fail-open: any error in THIS script → exit 0, never block the session.

# Fail-open: no set -e (intentional). set -u for undefined var safety.
set -u

session_id="${CLAUDE_SESSION_ID:-$PPID}"
# Use per-user temp dir (macOS: private, Linux: check $TMPDIR first)
_log_dir="${TMPDIR:-${XDG_STATE_HOME:-$HOME/.local/state}/adaptive-research}"
mkdir -p "$_log_dir" 2>/dev/null
log_file="$_log_dir/errors.log"

input=$(cat 2>/dev/null || true)
ts=$(date '+%Y-%m-%dT%H:%M:%S%z')

# Detect error type
error_type="unknown"
if [ -n "$input" ]; then
  input_lower=$(echo "$input" | tr '[:upper:]' '[:lower:]')
  if echo "$input_lower" | grep -qE '429|rate.?limit|too many requests'; then
    error_type="rate_limit"
  elif echo "$input_lower" | grep -qE '401|403|auth|unauthorized|forbidden'; then
    error_type="auth_error"
  elif echo "$input_lower" | grep -qE '500|502|503|504|server|overloaded'; then
    error_type="server_error"
  fi
fi

echo "${ts} [StopFailure] type=${error_type} session=${session_id}" >> "$log_file"

# Rate limit → pause active loop (compatible with watchdog resume)
if [ "$error_type" = "rate_limit" ]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  STATE_FILE="$PROJECT_DIR/_autonomous/loop.state.md"
  PAUSE_TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  if [ -f "$STATE_FILE" ]; then
    TEMP_FILE="${STATE_FILE}.tmp.$$"
    trap 'rm -f "$TEMP_FILE" 2>/dev/null' EXIT
    if grep -q '^paused_at:' "$STATE_FILE" 2>/dev/null; then
      sed "s/^paused_at: .*/paused_at: $PAUSE_TS/" "$STATE_FILE" > "$TEMP_FILE"
    else
      awk -v ts="$PAUSE_TS" '/^iteration:/{print; print "paused_at: " ts; next}1' \
        "$STATE_FILE" > "$TEMP_FILE"
    fi
    mv "$TEMP_FILE" "$STATE_FILE"
    echo "${ts} [StopFailure] Loop paused at ${PAUSE_TS}" >> "$log_file"
  fi
fi

echo '{}'
exit 0
