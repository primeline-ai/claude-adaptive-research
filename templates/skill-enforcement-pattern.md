# Skill Enforcement Pattern

**Status**: Reference template extracted from /auto-run enforcement layer (2026-05-16)
**Source plan**: `.claude/plans/2026-05-16-auto-run-enforcement-layer.md`
**Working example**: /auto-run + gate-keeper.py + auto-run-gate-keeper-observer.sh
**Use when**: A skill produces structured output that follows a contract (sections, citations, format) and skill-text discipline alone is insufficient

---

## 1. Problem this pattern solves

LLM skills are instructed via markdown text ("MUST include section X"). The model often follows the contract but sometimes silently skips required sections. Reasons:
- Long skill prose: model attention degrades
- Premium-by-default rules added after the skill was tuned
- Edge cases (rate limits, ambiguity) cause partial completion

Without machine enforcement, "the skill says it works" becomes the only proof - which is action-level evidence, not outcome-level. See `~/.claude/rules/empirical-completion.md`.

This pattern adds machine-verifiable contracts on top of skill text.

---

## 2. Anatomy of the pattern (6 components)

| # | Component | Purpose | Example artifact |
|---|-----------|---------|------------------|
| 1 | Gate definitions | List of binary contracts the output must satisfy | `auto-run-enforcement-spec.md` |
| 2 | Gate-keeper script | Reads the output file, applies regex/structured checks, emits PASS/WARN/FAIL JSON | `_autonomous/scripts/gate-keeper.py` |
| 3 | Test suite | Unit tests for the gate-keeper - TDD red-green discipline | `_autonomous/scripts/test_gate_keeper.py` |
| 4 | Premise validation (Phase -1) | 30-min run against historical outputs to confirm the gap is real | `_autonomous/loop-state/baseline-premise-test.jsonl` |
| 5 | Observer hook | PostToolUse hook that runs gate-keeper on every relevant output, observe-only | `.claude/hooks/auto-run-gate-keeper-observer.sh` |
| 6 | Kill-switch | Env var + sentinel file for instant disable | `AUTORUN_GATEKEEPER_DISABLE` env + `loop-state/gatekeeper.disabled` |

---

## 3. Rollout sequence (DO NOT shortcut)

```
Phase -1: Premise Validation   (30 min)   - run skeleton against history
Phase 0:  Baseline + benchmark  (1-2 h)   - latency check + 5-report regression
Phase 0.5: TDD refinement       (1-2 h)   - tests-first detection tuning
Phase 1:  Observer integration  (2-3 h)   - wire into PostToolUse, logs only
Phase 2:  Observe-week analysis (7 days)  - measure baseline FAIL rates B
Phase 3:  Soft-block activation (2-3 h)   - FAIL --> re-prompt, NOT hard block
Phase 4:  Fire-and-forget       (1-2 h)   - autonomy contract in skill
Phase 5:  Pre-flight check      (2-3 h)   - dedup detection before skill starts
Phase 6:  Template extraction   (2-3 h)   - this document, plus source artifacts
```

**Critical**: Phase 2 cannot be compressed - it needs real-world data over multiple days. Earlier phases CAN be done in one session.

---

## 4. Hard rules (anti-patterns to avoid)

1. **No hard-blocking before observe-mode**: Phase 3 activates only after Phase 2 confirms low false-positive rate (<10%)
2. **No silent failures**: every gate FAIL must produce a log entry; missing-actions list must be specific
3. **No coupling to LLM-as-judge**: gates must be deterministic (regex, structured checks). LLM-judging gates self-justify and miss real failures
4. **No modifying the canonical loop hook**: build a SEPARATE observer hook. Modifying `ralph-loop-stop.sh` (or equivalent) during an active session causes session-wide failures. Learned 2026-05-16.
5. **No setting.json activation without smoke test**: only wire into settings.json AFTER standalone test passes
6. **No kill-switch as config-file edit**: kill-switch must be ONE env var or sentinel file, not a JSON edit
7. **No premature precision**: don't claim FAIL rate before Phase 2 measures B. Use baseline-derived targets (B+20%) not absolute numbers
8. **Premise-validation BEFORE plan-execution**: always run Phase -1 first. If the gap is <10% on all gates, the plan is overkill

---

## 5. Adapting this pattern to a new skill

To add an enforcement layer to a new skill `/foo`, follow this checklist:

### 5.1 Identify the contract
- What sections must the output contain?
- What markers indicate quality (citations, evidence, cross-references)?
- What is the FAIL case that currently slips through?
- Document in a spec file: `.claude/scenarios/{skill-category}/knowledge/foo-enforcement-spec.md`

### 5.2 Write the gate-keeper script
- Use the existing `_autonomous/scripts/gate-keeper.py` structure as reference
- Per-gate function: returns `(status: PASS|WARN|FAIL, detail: str)` tuple
- Main: aggregate JSON output with run_id, overall, gates, missing_actions, timestamp
- Exit codes: 0=PASS, 1=FAIL, 2=WARN
- Always use script-relative paths (not CWD-relative)

### 5.3 Write tests FIRST (TDD red)
- Use `_autonomous/scripts/test_gate_keeper.py` as reference (importlib.util.spec_from_file_location for hyphenated filenames)
- Test cases: explicit positive, explicit negative, edge cases (empty, code-block content, near-threshold)
- Strict assertions (assertEqual not assertIn) to catch unintended downgrades

### 5.4 Refine until green
- Run tests, fix gate logic until all green
- Code review via `feature-dev:code-reviewer` agent
- Apply review findings before moving on

### 5.5 Run Phase -1 premise validation
- 30 min: run gate-keeper against 10-15 historical outputs
- If <10% FAIL on all gates: STOP, the gap doesn't justify the rest of the plan. Park.
- If >30% FAIL on any gate: full plan justified
- 10-30% range: adjusted scope (Phases 0-4 only)

### 5.6 Build the PostToolUse observer hook
- Filename: `.claude/hooks/{skill-name}-gate-keeper-observer.sh`
- Trigger: `PostToolUse` on `Write` with file-path filter matching the skill's output convention
- 9 safety invariants (timeouts, kill-switches, always-exit-0)
- DO NOT wire into settings.json yet

### 5.7 Standalone test the observer hook
- Pipe controlled JSON inputs simulating PostToolUse hook calls
- Verify: gate-results entries are correct shape, kill-switches work, file-path filter excludes wrong matches
- Code review

### 5.8 Wire into settings.json (the live activation step)
- Add a PostToolUse entry with the new hook
- USE A SAFER SESSION (not the one you developed in) - hook modifications can affect the dev session
- Verify by checking gate-results.jsonl gets entries after a real skill invocation

### 5.9 Observe week (Phase 2)
- Let the skill run normally for 7 days with observer-mode active
- Analyze gate-results.jsonl: FAIL rate per gate, false-positive examples, threshold tuning candidates
- Document in `_autonomous/loop-state/{skill}-observe-report.md`

### 5.10 Activate soft-block (Phase 3)
- If observe-week false-positive rate <20%: switch hook from observe-only to soft-block
- FAIL output triggers re-prompt (NOT hard block, NOT exit-non-zero)
- Test with deliberate-FAIL fixture

### 5.11 Document deferred-and-untested
- Closeout MUST list which gates were observed but never triggered
- Which thresholds were guessed vs measured
- What known bugs / edge cases remain

---

## 6. Known limitations of this pattern

- **Regex-based detection has false-positive ceilings**: For nuanced semantic checks (e.g., "did the agent actually understand X?"), regex is insufficient. Use this pattern for structural contracts (sections, citations, format) where deterministic checks work.
- **Cannot enforce on subagent transcripts**: PostToolUse fires on tool calls, not on subagent reasoning. If the skill's quality lives in subagent thinking, you need a different observation point.
- **Adds 1 background process per skill output**: <100ms typical but adds load on busy sessions. Use timeouts to prevent runaway.
- **Stop hooks have implicit consumers**: Modifying any Stop/PostToolUse hook in an active CC session can affect the developing session. Always use SEPARATE hook files, not modifications to canonical ones.

---

## 7. Known candidates for this pattern (as of 2026-05-16)

Candidate skills where enforcement could add value. Each entry: rationale + open question.

| Skill | Why this pattern could help | Open question |
|-------|----------------------------|---------------|
| `/auto-run` | Premium-by-default reports skip ECP/Synthesis. Empirically validated. | DONE - this is the reference example |
| `/quantum-full` | Lens output structure inconsistent across runs | Is the contract well-enough defined to write gate-keeper? |
| `/quantum-lens` | Same as above for single-lens runs | Same |
| `/run-workflow` | Multi-step workflows have hidden skip-steps | Skill output is ambiguous - may need structured logging first |
| `/full-audit` | Audit reports vary in section presence | Pattern fits, audit-fix already has some enforcement |
| `/plan-new` | UPF stages can be skipped silently | Already has interview/refine/review - meta-enforcement on top |
| Future ReVane buyer-pilot reports | Industrial safety reports must satisfy compliance contracts | Different domain - pattern transfers but contracts come from IEC/DNV |

Adding a candidate to this list does NOT commit to porting. Track via Wiedervorlage or task list.

---

## 8. Source artifacts (the reference implementation)

| Artifact | Path |
|----------|------|
| Plan | `.claude/plans/2026-05-16-auto-run-enforcement-layer.md` |
| Spec | `.claude/scenarios/autonomous-loops/knowledge/auto-run-enforcement-spec.md` |
| Gate-keeper | `_autonomous/scripts/gate-keeper.py` |
| Tests | `_autonomous/scripts/test_gate_keeper.py` |
| Observer hook | `.claude/hooks/auto-run-gate-keeper-observer.sh` |
| Pre-flight | `_autonomous/scripts/preflight-check.sh` |
| Skill skill text | `.claude/scenarios/autonomous-loops/commands/auto-run.md` (Autonomy Contract section) |
| Baseline data | `_autonomous/loop-state/baseline-premise-test-refined.jsonl` |
| Benchmark | `_autonomous/loop-state/gate-keeper-benchmark.log` |

Kairn entries for cross-reference:
- `4a25e168` (pattern): Late-DSV catches premise gaps after Stage 3
- `332bc9fc` (gotcha): gate-keeper Kairn regex bug + fix
- `9d1d52e7` (decision): Plan GO with adjusted scope

---

## 9. Pattern maintenance

This template should be updated when:
- A new skill successfully ports the pattern (add to section 7)
- A new failure mode is discovered (add to section 4 anti-patterns)
- Source artifacts move or are renamed (update section 8)
- Phase 2/3 of /auto-run produces lessons (update sequence in section 3)

Owner: Robin (solo dev)
Reviewed: 2026-05-16 (initial version)
Next review: post-/auto-run Phase 2 closeout (target 2026-05-30)
