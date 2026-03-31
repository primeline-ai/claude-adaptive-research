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

## Feedback Injection (Compound Learning)

This is what makes the research truly ADAPTIVE. Each run leaves context for the next.

### How it works

After completing a run, the runner updates `_autonomous/feedback-state.json` with:
1. **Keywords discovered** — interesting terms, concepts, tools found during research
2. **Trending topics** — patterns that appeared across multiple sources
3. **Follow-up questions** — unanswered questions that emerged

### Injection format

When starting a new run, check `feedback-state.json` for the current preset or topic:

```json
{
  "injected_context": {
    "technique-scout": {
      "extra_keywords": ["pattern-A", "tool-B", "concept-C"],
      "trending_topics": ["emerging-trend-X"]
    },
    "cross-domain": {
      "trending_topics": ["biology-pattern-Y", "physics-concept-Z"]
    }
  }
}
```

If `injected_context` exists for the current preset:
- Use `extra_keywords` as ADDITIONAL search terms (alongside the preset's default searches)
- Use `trending_topics` as context in the system prompt: "Previous runs identified these trending topics: {list}. Build on them if relevant."

If no `injected_context` exists: run normally (first run).

### Writing feedback after completion

After each run, extract and save:
```json
{
  "injected_context": {
    "{preset-or-topic-slug}": {
      "extra_keywords": ["top 5-10 novel terms discovered"],
      "trending_topics": ["2-3 patterns that deserve follow-up"]
    }
  }
}
```

This creates a **compound learning effect**: Run 1 finds keywords → Run 2 searches deeper → Run 3 connects cross-domain → each run builds on the last.

## Compound Score

Track cumulative research progress in `feedback-state.json`:

```json
{
  "compound_score": {
    "total_runs": 6,
    "total_findings": 43,
    "unique_topics": 6,
    "first_run": "2026-03-30",
    "streak_days": 3
  }
}
```

Update after EVERY run:
- `total_runs` += 1
- `total_findings` += number of findings in report
- `unique_topics` += 1 if this topic/preset hasn't been run before
- `streak_days`: check if `last_reports` has an entry from yesterday. Yes → streak += 1. No (gap > 1 day) → streak = 1.

Display in completion message:
```
Research complete! Score: 75/100

Compound: 7 runs | 50 findings | 4-day streak
```

## Optional: Kairn Integration

If the user has [Kairn](https://github.com/primeline-ai/kairn) installed as an MCP server, the runner can persist findings across sessions:

### Detection
Check if `kn_learn` tool is available. If yes → Kairn is active.

### After Quality Gate passes
Save top 3 findings via `kn_learn`:
- Type: `pattern` (technique-scout), `decision` (cross-domain), `solution` (trend-radar, content-pipeline, competitor-analysis)
- Tags: `[adaptive-research, {preset-or-topic-slug}]`
- Content: one-sentence summary of each finding

### On next run
Use `kn_recall` with the current topic to load relevant past findings. Inject as context:
"Previous research found: {recalled findings}. Build on these, don't repeat them."

### Without Kairn
Everything works — findings live in report files. Kairn adds cross-session memory on top.

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
