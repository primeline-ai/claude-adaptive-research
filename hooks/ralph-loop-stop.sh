#!/bin/bash
#
# Ralph Loop Stop Hook — keeps autonomous research loops running
# Fires on every session stop. If a loop is active and not complete,
# re-injects the prompt to continue the research.
#
# State file: _autonomous/loop.state.md (in user's project dir)
# Completion: <promise>DONE</promise> in Claude's output
# Rate limit: <promise>RATE_LIMITED</promise> pauses without counting iteration

set -euo pipefail

HOOK_INPUT=$(cat)

# Dynamic project root — works in any directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATE_FILE="$PROJECT_DIR/_autonomous/loop.state.md"

# No active loop — allow normal exit
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Parse frontmatter
# Parse frontmatter (strip \r for Windows/cross-platform safety)
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | tr -d '\r')
ITERATION=$(echo "$FRONTMATTER" | grep '^iteration:' | sed 's/iteration: *//')
MAX_ITERATIONS=$(echo "$FRONTMATTER" | grep '^max_iterations:' | sed 's/max_iterations: *//')
COMPLETION_PROMISE=$(echo "$FRONTMATTER" | grep '^completion_promise:' | sed 's/completion_promise: *//' | sed 's/^"\(.*\)"$/\1/')

# Validate
if [[ ! "$ITERATION" =~ ^[0-9]+$ ]] || [[ ! "$MAX_ITERATIONS" =~ ^[0-9]+$ ]]; then
  echo "Warning: Loop state corrupted, removing" >&2
  rm "$STATE_FILE"
  exit 0
fi

# Max iterations reached
if [[ $MAX_ITERATIONS -gt 0 ]] && [[ $ITERATION -ge $MAX_ITERATIONS ]]; then
  echo "Loop: Max iterations ($MAX_ITERATIONS) reached." >&2
  rm "$STATE_FILE"
  exit 0
fi

# Get last assistant output
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | jq -r '.transcript_path')
if [[ ! -f "$TRANSCRIPT_PATH" ]]; then
  rm "$STATE_FILE"
  exit 0
fi

# Try hook input first (CC 2.1.47+), fallback to transcript
LAST_OUTPUT=$(echo "$HOOK_INPUT" | jq -r '.last_assistant_message // empty')
if [[ -z "$LAST_OUTPUT" ]]; then
  if ! grep -q '"role":"assistant"' "$TRANSCRIPT_PATH"; then
    rm "$STATE_FILE"
    exit 0
  fi
  LAST_LINE=$(grep '"role":"assistant"' "$TRANSCRIPT_PATH" | tail -1)
  LAST_OUTPUT=$(echo "$LAST_LINE" | jq -r '
    .message.content |
    map(select(.type == "text")) |
    map(.text) |
    join("\n")
  ' 2>/dev/null || echo "")
fi

# Verify command removed — completion promise is the standard exit mechanism.
# If you need custom verification, use the completion_promise field.

# Check completion promise
if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
  PROMISE_TEXT=$(echo "$LAST_OUTPUT" | perl -0777 -pe 's/.*?<promise>(.*?)<\/promise>.*/$1/s; s/^\s+|\s+$//g; s/\s+/ /g' 2>/dev/null || echo "")

  # DONE — loop complete
  if [[ -n "$PROMISE_TEXT" ]] && [[ "$PROMISE_TEXT" = "$COMPLETION_PROMISE" ]]; then
    rm "$STATE_FILE"
    exit 0
  fi

  # RATE_LIMITED — pause without counting iteration, block with wait message
  if [[ -n "$PROMISE_TEXT" ]] && [[ "$PROMISE_TEXT" = "RATE_LIMITED" ]]; then
    TEMP_FILE="${STATE_FILE}.tmp.$$"
    PAUSE_TS="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    if grep -q '^paused_at:' "$STATE_FILE"; then
      sed "s/^paused_at: .*/paused_at: $PAUSE_TS/" "$STATE_FILE" > "$TEMP_FILE"
    else
      awk -v ts="$PAUSE_TS" '/^iteration:/{print; print "paused_at: " ts; next}1' \
        "$STATE_FILE" > "$TEMP_FILE"
    fi
    mv "$TEMP_FILE" "$STATE_FILE"

    # Extract prompt for re-injection after pause
    PROMPT_TEXT=$(awk '/^---$/{i++; next} i>=2' "$STATE_FILE")

    # Block exit: tell Claude to wait and retry
    jq -n \
      --arg prompt "$PROMPT_TEXT" \
      '{
        "decision": "block",
        "reason": $prompt,
        "systemMessage": "Rate limit hit. Waiting 60 seconds before retrying. Iteration NOT counted. After the wait, continue your research where you left off."
      }'
    exit 0
  fi
fi

# Not complete — continue loop
NEXT_ITERATION=$((ITERATION + 1))

# Extract prompt (everything after closing ---)
PROMPT_TEXT=$(awk '/^---$/{i++; next} i>=2' "$STATE_FILE")
if [[ -z "$PROMPT_TEXT" ]]; then
  rm "$STATE_FILE"
  exit 0
fi

# Update iteration counter
TEMP_FILE="${STATE_FILE}.tmp.$$"
sed "s/^iteration: .*/iteration: $NEXT_ITERATION/" "$STATE_FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$STATE_FILE"

# Block exit and re-prompt
if [[ "$COMPLETION_PROMISE" != "null" ]] && [[ -n "$COMPLETION_PROMISE" ]]; then
  SYSTEM_MSG="Loop iteration $NEXT_ITERATION/$MAX_ITERATIONS | Complete: <promise>$COMPLETION_PROMISE</promise>"
else
  SYSTEM_MSG="Loop iteration $NEXT_ITERATION/$MAX_ITERATIONS"
fi

jq -n \
  --arg prompt "$PROMPT_TEXT" \
  --arg msg "$SYSTEM_MSG" \
  '{
    "decision": "block",
    "reason": $prompt,
    "systemMessage": $msg
  }'

exit 0
