#!/bin/bash
#
# Auto-Run Pre-flight Check (Phase 5)
#
# Purpose: Before /auto-run kicks off a research cycle, detect:
#   1. Same-day duplicate report (slug already covered today)
#   2. Recent Kairn coverage on the topic (last 7 days)
#
# Outputs (stdout JSON):
#   {
#     "duplicate_today": bool,
#     "duplicate_path": "string or null",
#     "kairn_hits": int (0 if Kairn unreachable),
#     "delta_requirement": "string - injection text for prompt, empty if no duplicate"
#   }
#
# Always exits 0. Fails open: if anything goes wrong, returns "no duplicate" so the run proceeds.
#
# Usage:
#   _autonomous/scripts/preflight-check.sh <slug-or-preset>
#   _autonomous/scripts/preflight-check.sh --force  (skip detection, always return no-duplicate)
#

EVOLVING_HOME="${EVOLVING_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Default safe output (used on any error)
SAFE_OUT='{"duplicate_today": false, "duplicate_path": null, "kairn_hits": 0, "delta_requirement": ""}'

# Parse args
if [[ "$#" -lt 1 ]]; then
  echo "$SAFE_OUT"
  exit 0
fi

SLUG="$1"

# --force bypasses all checks
if [[ "$SLUG" == "--force" ]]; then
  echo "$SAFE_OUT"
  exit 0
fi

# Sanitize slug: only allow word-chars + dash
if ! [[ "$SLUG" =~ ^[A-Za-z0-9_-]+$ ]]; then
  # Invalid slug input - fail open
  echo "$SAFE_OUT"
  exit 0
fi

TODAY=$(date +%Y-%m-%d 2>/dev/null)
[[ -z "$TODAY" ]] && { echo "$SAFE_OUT"; exit 0; }

# 1. Same-day duplicate check
DUPLICATE_PATH=""
DUPLICATE_TODAY=false
CANDIDATE="$EVOLVING_HOME/_autonomous/results/$SLUG/$TODAY.md"
if [[ -f "$CANDIDATE" ]]; then
  DUPLICATE_PATH="$CANDIDATE"
  DUPLICATE_TODAY=true
fi

# Also check single-file slug pattern (some presets use results/{slug}-{date}.md)
ALT_CANDIDATE="$EVOLVING_HOME/_autonomous/results/${SLUG}-${TODAY}.md"
if [[ -z "$DUPLICATE_PATH" ]] && [[ -f "$ALT_CANDIDATE" ]]; then
  DUPLICATE_PATH="$ALT_CANDIDATE"
  DUPLICATE_TODAY=true
fi

# 2. Build delta requirement text if duplicate exists
DELTA_TEXT=""
if [[ "$DUPLICATE_TODAY" == "true" ]]; then
  DELTA_TEXT="### Delta to Previous (MANDATORY this run)\\n\\nA report for slug '$SLUG' already exists today at $DUPLICATE_PATH.\\n\\nDo NOT blindly re-research. Instead:\\n1. Read the existing report header + findings\\n2. Identify what is NEW since then (new evidence, new angles, new sources)\\n3. Add a Delta section to the report: New / Confirmed / Contradicted\\n4. Bypass this check next time with --force flag\\n"
fi

# 3. Output JSON (using printf for portability)
# Note: Kairn check is intentionally omitted from this lightweight pre-flight to keep
# overhead under 500ms. The auto-run skill should query Kairn separately if needed.
printf '{"duplicate_today": %s, "duplicate_path": %s, "kairn_hits": 0, "delta_requirement": %s}\n' \
  "$DUPLICATE_TODAY" \
  "$(if [[ -n "$DUPLICATE_PATH" ]]; then printf '"%s"' "$DUPLICATE_PATH"; else echo "null"; fi)" \
  "$(printf '"%s"' "$DELTA_TEXT")"

exit 0
