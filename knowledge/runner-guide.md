# Adaptive Research Runner Guide

## System Safety (READ FIRST)

This runner operates AUTONOMOUSLY without user supervision.

### Allowed write targets
- `_autonomous/results/{domain}/{date}.md` — research reports
- `_autonomous/config.yaml` — domain configuration (setup only)
- `_autonomous/profile.yaml` — user profile (setup only)
- `_autonomous/loop.state.md` — loop state (managed by hooks)
- `_autonomous/feedback-state.json` — cross-run learning

### Forbidden actions
- NO modifications outside `_autonomous/`
- NO git commits or pushes
- NO destructive operations (rm, delete, drop)
- NO changes to project source code, configs, or settings

### Read-then-Write pattern
For `feedback-state.json`: ALWAYS read first, modify only your fields, write back the complete file.

---

## How the Loop Works

```
User: /auto-run "topic"
  ↓
Command creates _autonomous/loop.state.md
  ↓
Claude researches, writes report
  ↓
Claude stops (end of turn)
  ↓
Stop Hook fires:
  - State file exists? → re-inject prompt
  - <promise>DONE</promise> found? → delete state, allow exit
  - <promise>RATE_LIMITED</promise>? → pause, block with wait message
  - Max iterations? → delete state, allow exit
  ↓
Loop continues until DONE or max iterations
```

## Quality Gate

Before emitting `<promise>DONE</promise>`, verify:

1. Report file written to `_autonomous/results/`
2. Report has: H1 + 2x H2 + list/table + findings section
3. Score calculated (4 x 25 points)
4. Score >= 50

Details: see `knowledge/quality-gate.md`

## Rate Limit Handling (3 Layers)

### Layer 1: In-prompt retry
When you hit a rate limit during research:
1. Wait 60 seconds
2. Retry the failed search
3. After 3 consecutive failures: emit `<promise>RATE_LIMITED</promise>`

### Layer 2: Stop Hook
The Stop Hook detects RATE_LIMITED:
- Does NOT count the iteration
- Writes `paused_at` timestamp to state file
- Blocks exit with a "wait and retry" message
- Re-injects the research prompt

### Layer 3: StopFailure Hook
If the API itself errors (429, 500, etc.):
- Detects error type from hook input
- Rate limit: pauses state file (same as Layer 2)
- Auth/server error: logs for debugging

## Feedback State

After each completed run, update `_autonomous/feedback-state.json`:

```json
{
  "last_reports": {
    "technique-scout": "2026-03-30",
    "cross-domain": null
  },
  "compound_score": {
    "total_runs": 1,
    "total_findings": 7,
    "first_run": "2026-03-30",
    "unique_topics": 1
  }
}
```

Read-then-write: load existing file first, update fields, write back.

## Adaptations Section

Every report MUST include an Adaptations section. Load `_autonomous/profile.yaml` and map findings to the user's projects:

```markdown
## Adaptations

### → {project name from profile}
{How finding X applies to this project specifically}

### → Personal
{How this applies to the user's productivity, learning, or goals}
```

If no profile exists, skip adaptations and note: "Run /auto-run --setup to enable personalized adaptations."
