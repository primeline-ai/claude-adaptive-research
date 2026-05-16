#!/bin/bash
#
# Auto-Run Gate Keeper Observer (Phase 1 - observe mode only)
#
# Trigger: PostToolUse on Write tool
# Purpose: When /auto-run writes a report to _autonomous/results/{slug}/{date}.md,
#          run gate-keeper.py against it and append the result to gate-results.jsonl.
#          OBSERVE MODE: log only, never block, never fail the parent tool call.
#
# Plan: .claude/plans/2026-05-16-auto-run-enforcement-layer.md (Phase 1)
# Architecture: Separate PostToolUse hook (NOT modifying ralph-loop-stop.sh) to
#               minimize blast radius. Hook is independent of Ralph Loop lifecycle
#               and can be disabled cleanly by removing from settings.json.
#
# Kill switches (any one disables the hook):
#   - env var AUTORUN_GATEKEEPER_DISABLE=1
#   - sentinel file _autonomous/loop-state/gatekeeper.disabled
#
# Safety invariants (NEVER violate):
#   1. ALWAYS exit 0 - PostToolUse failures must not break the parent tool call
#   2. Run with hard timeout (10s) to prevent hangs
#   3. Catch ALL errors and log to fallback, never propagate
#   4. Skip on any unexpected input format - do not assume
#

# Intentionally NOT using set -e here: any sub-command failure is logged and ignored.
# This file is on the hot path of every Write tool call - it MUST be ultra-safe.

EVOLVING_HOME="${EVOLVING_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_FILE="$EVOLVING_HOME/_autonomous/loop-errors.log"
RESULTS_FILE="$EVOLVING_HOME/_autonomous/loop-state/gate-results.jsonl"
GATEKEEPER="$EVOLVING_HOME/_autonomous/scripts/gate-keeper.py"
DISABLE_SENTINEL="$EVOLVING_HOME/_autonomous/loop-state/gatekeeper.disabled"

# Helper: log + exit 0. Used for all early-exit branches.
safe_exit() {
  exit 0
}

# 1. Read hook input safely (timeout if stdin blocks for some reason)
input=$(timeout 2 cat 2>/dev/null) || safe_exit
[[ -z "$input" ]] && safe_exit

# 2. Kill-switch checks
[[ -n "${AUTORUN_GATEKEEPER_DISABLE:-}" ]] && safe_exit
[[ -f "$DISABLE_SENTINEL" ]] && safe_exit

# 3. Parse tool name and file path (tolerate missing jq, missing fields)
tool_name=$(echo "$input" | jq -r '.tool_name // empty' 2>/dev/null)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Only react to Write tool (NOT Edit - Edits don't fully reset the report content)
[[ "$tool_name" != "Write" ]] && safe_exit
[[ -z "$file_path" ]] && safe_exit

# 4. File-path filter: only /auto-run reports under _autonomous/results/
case "$file_path" in
  */_autonomous/results/_briefing/*) safe_exit ;;   # exclude briefing aggregates
  */_autonomous/results/*/*.md) ;;                  # match: results/{slug}/*.md
  */_autonomous/results/*.md)     ;;                # match: results/*.md (single-file slugs)
  *) safe_exit ;;
esac

# 5. Verify required deps are present (silent skip if not)
[[ ! -x "$GATEKEEPER" ]] && safe_exit
[[ ! -f "$file_path" ]] && safe_exit
command -v python3 >/dev/null 2>&1 || safe_exit

# 6. Run gate-keeper with hard timeout (10s should be plenty for sub-1s typical run)
result=$(timeout 10 python3 "$GATEKEEPER" --report-path "$file_path" --json 2>/dev/null)
# Empty result = crash or timeout - log and exit
if [[ -z "$result" ]]; then
  mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') gate-keeper-observer-empty-output file=$file_path" >> "$LOG_FILE" 2>/dev/null
  safe_exit
fi

# 7. Annotate with observation metadata and append (with hard timeout on python too)
annotated=$(echo "$result" | timeout 5 python3 -c "
import sys, json, datetime
try:
    d = json.loads(sys.stdin.read())
except Exception as e:
    d = {'error': 'observer-annotation-failed: ' + str(e)}
d['_observed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
d['_source'] = 'PostToolUse-Write-observer'
d['_report_path'] = sys.argv[1] if len(sys.argv) > 1 else ''
d['_mode'] = 'observe'
print(json.dumps(d))
" "$file_path" 2>/dev/null)

if [[ -z "$annotated" ]]; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') gate-keeper-observer-annotation-failed file=$file_path" >> "$LOG_FILE" 2>/dev/null
  safe_exit
fi

# 8. Append to results log (best-effort, never fail)
mkdir -p "$(dirname "$RESULTS_FILE")" 2>/dev/null
echo "$annotated" >> "$RESULTS_FILE" 2>/dev/null

# 9. ALWAYS exit 0
safe_exit
