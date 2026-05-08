---
description: "Autonomous personalized research loop — set a topic, get a quality-gated report"
arguments:
  - name: topic
    description: "Research topic (free text) or --preset name or --setup for first-time configuration"
    required: false
---

# /auto-run

Autonomous research loop with quality gate and personalized adaptations.

## FIRST RUN CHECK

Check if `_autonomous/config.yaml` exists in the current project directory.

**If NOT exists → run setup automatically:**
1. Show the user what this plugin can do (examples, domains, presets)
2. Ask how many research domains they want (2-10)
3. Let them name their domains (with examples)
4. Ask about their projects for the adaptation section (short interview)
5. Save config to `_autonomous/config.yaml`
6. Save profile to `_autonomous/profile.yaml`
7. Create domain folders under `_autonomous/results/{domain}/`

**If exists → proceed with run.**

---

## SETUP MODE (/auto-run --setup or /auto-run setup)

Force re-run the setup flow even if config exists.

### Step 1: Show what's possible

```
Welcome to Adaptive Research!

This plugin runs autonomous research loops — you set a topic,
Claude researches it independently, writes a report, and scores
it for quality. Reports adapt findings to YOUR projects.

WHAT YOU CAN RESEARCH:

  Research Domains (knowledge sources you pick)
  Examples:
  · Psychology — cognition, bias, motivation, persuasion
    → adaptable to: agent behavior, UX, conversion optimization
  · Biology — swarm intelligence, evolution, mycelium networks
    → adaptable to: algorithms, network architecture, adaptive systems
  · Physics — entropy, resonance, network theory, thermodynamics
    → adaptable to: system optimization, load balancing, drift prevention
  · Engineering — software patterns, control theory, architecture
    → adaptable to: code quality, DevOps, system design
  · Everyday Life — habits, heuristics, systems in daily life
    → adaptable to: productivity, workflows, life design
  · Finance — income streams, monetization, pricing strategies
    → adaptable to: your business, revenue models

  Free Text (any topic, anytime)
  · /auto-run "How do ant colony patterns apply to database sharding?"
  · /auto-run "Find 10 monetization strategies for open source projects"

  Presets (pre-configured research strategies)
  · technique-scout — find new techniques in your field
  · cross-domain — transfer patterns between disciplines
  · trend-radar — spot emerging trends in any niche
```

### Step 2: Domain selection

Ask: "How many research domains do you want? (2-10, or 'skip' for free-text only)"

For each domain, let the user name it and optionally describe what it covers.

### Step 3: Profile interview

Ask 3-5 questions to build the user profile:
1. "What are you working on? (main project, side projects)"
2. "What's your role/skillset? (developer, designer, founder, researcher...)"
3. "What do you want to achieve with research? (learn, build, optimize, monetize...)"
4. "Any specific tools or frameworks you use? (optional)"

### Step 4: Save configuration

Write `_autonomous/config.yaml`:
```yaml
version: 1
domains:
  - name: psychology
    description: "Cognition, bias, motivation"
  - name: biology
    description: "Swarm, evolution, mycelium"
created: 2026-03-30
```

Write `_autonomous/profile.yaml`:
```yaml
version: 1
projects:
  - name: "My SaaS"
    description: "B2B analytics platform"
  - name: "Open Source Library"
    description: "React component library"
role: "Full-stack developer & founder"
goals: ["optimize architecture", "grow user base"]
tools: ["React", "Python", "Claude Code"]
created: 2026-03-30
```

Create domain folders: `_autonomous/results/{domain}/`

### Step 5: Confirm

```
Setup complete!

Domains: {n} created
Profile: saved
Folders: _autonomous/results/{domains}/

Try it now:
  /auto-run "your first research topic"
  /auto-run --preset technique-scout
```

---

## RUN MODE

### Parameter parsing

Extract from user input:
- `mode`: "freetext" | "preset" | "setup"
- `topic`: free-text topic (if freetext)
- `preset`: preset name (if --preset)
- `quality_tier`: "premium" (default) | "standard" (if `--quick` is in the prompt)

#### Premium-by-default contract

The default tier is **premium**. Premium runs:
- target the v2 quality rubric in [`knowledge/quality-gate-v2.md`](../knowledge/quality-gate-v2.md) (5 metrics: citation density, DSV evidence, gap disclosure, ECP section, cross-track convergence)
- require an `## Empirical Completion Proof` section in the report (header + at least 2 of 3 legs: Trigger / Effect / Consumption)
- require a `## Deferred-and-Untested` (or `## Gaps` / `## Open Questions`) section
- target Premium tier (5/5 metrics) but accept Standard (3-4/5)

The `--quick` flag opts down to **standard** tier (the original v1 prose gate at score >= 50). Use `--quick` for casual / throwaway research. Examples:

```
/auto-run "How does mycelium share nutrients?"          # premium (default)
/auto-run --quick "Quick scan of LLM eval frameworks"   # standard, looser bar
```

### Concurrency check

Check if `_autonomous/loop.state.md` exists.
If yes: "A research loop is already running. Stop it first with /cancel-loop"

### Permission mode check

If current permission mode is `default`:
"Note: Auto-run writes reports autonomously. Consider using --permission-mode acceptEdits for uninterrupted runs."

### Cost awareness

On first run of session, show once:
"Heads up: Each research loop uses multiple API calls. On API billing, a typical run costs $2-8 depending on depth. On Max/Pro subscription, it uses your included quota."

### Model recommendation

If model is Haiku: "Recommendation: Use Opus or Sonnet for best research quality. Haiku may struggle with the quality gate."

### Load config

Read `_autonomous/config.yaml` and `_autonomous/profile.yaml`.

### Build prompt

#### Free-text mode

Build research prompt with:
1. The user's topic
2. System safety rules (write only to `_autonomous/`)
3. Quality gate requirements:
   - **Premium tier (default)**: target the 5-metric rubric in [`knowledge/quality-gate-v2.md`](../knowledge/quality-gate-v2.md). Reach Premium (5/5) or Standard (3-4/5). Require `## Empirical Completion Proof` (with Trigger/Effect/Consumption legs) and `## Deferred-and-Untested` (or `## Gaps` / `## Open Questions`) sections.
   - **Standard tier (`--quick`)**: target the v1 rubric in [`knowledge/quality-gate.md`](../knowledge/quality-gate.md), score >= 50.
4. Adaptation section template (from profile.yaml — user's projects)
5. Output path: `_autonomous/results/{best-matching-domain-or-slug}/{date}.md`

#### Preset mode

Load preset from `presets/{preset-name}.md`.
Inject user profile context for adaptations.

### Create state file

Write `_autonomous/loop.state.md`:
```markdown
---
iteration: 1
max_iterations: 10
completion_promise: "DONE"
verify: null
started: {ISO_TIMESTAMP}
---

{AUGMENTED_PROMPT}
```

### Start research

Begin immediately. The Stop hook keeps the loop running until `<promise>DONE</promise>`.

### After completion

1. Verify report exists and passes quality gate.

   **For premium runs (default):**
   - Run the v2 scorer:
     ```bash
     python3 scripts/quality_gate_v2.py "{report_path}" --json
     ```
   - Read the `tier` field:
     - `premium` (5/5 metrics) → pass, write `**Quality Gate v2**: Premium (5/5)` in report header
     - `standard` (3-4/5) → accepted as standard tier, write `**Quality Gate v2**: Standard (X/5)`
     - `reject` (<3/5) → identify which metric failed, fix the report, re-run scorer. Do NOT emit DONE.
   - The report MUST contain:
     - `## Empirical Completion Proof` section with at least 2 of 3 legs (Trigger / Effect / Consumption)
     - `## Deferred-and-Untested` (or equivalent gap-disclosure header) section listing what was NOT verified

   **For `--quick` runs (standard tier):**
   - Use the original v1 prose gate from [`knowledge/quality-gate.md`](../knowledge/quality-gate.md) (4 criteria, score >= 50)
   - ECP and gap-disclosure sections are optional but encouraged

2. Output: `<promise>DONE</promise>`

---

## EXAMPLES

```bash
# Free-text — any topic (premium tier by default)
/auto-run "What can software engineers learn from how ant colonies optimize foraging?"

# Quick / casual — opts down to standard tier (looser bar, no ECP/gap-disclosure required)
/auto-run --quick "Quick scan of LLM eval frameworks"

# Preset
/auto-run --preset technique-scout

# Re-run setup
/auto-run --setup

# With domain hint
/auto-run "Swarm patterns in load balancing" --domain biology
```
