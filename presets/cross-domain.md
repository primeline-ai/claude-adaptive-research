---
preset: cross-domain
description: Transfer patterns and principles between disciplines
max_iterations: 10
completion_promise: DONE
min_findings: 5
min_words: 600
---

## System Safety
You are running AUTONOMOUSLY. Write ONLY to `_autonomous/` directory.
No modifications to any other project files. No git operations. No destructive actions.

## Goal

Find patterns, principles, and mental models from one discipline that can be transferred to the user's field. The magic is in the CONNECTIONS — not the individual facts.

## Method

1. **Load context**: Read `_autonomous/profile.yaml` and `_autonomous/config.yaml`.
   Identify the user's domains and projects.

2. **Pick a source domain**: Choose one of the user's configured domains (or a random adjacent field if no domains configured). Examples:
   - Biology → software architecture (swarm, evolution, mycelium networks)
   - Psychology → UX/conversion (cognitive bias, motivation, persuasion)
   - Physics → system design (entropy, resonance, network theory)
   - Everyday life → productivity (habits, heuristics, kitchen physics)

3. **Deep search** in the source domain:
   - Use firecrawl_search (or WebSearch) for fundamental principles
   - Look for: universal patterns, scaling laws, optimization strategies, failure modes
   - Search for: "[source domain] principles applied to [user's field]"

4. **Transfer analysis** for each pattern found:
   - What is the original principle? (1-2 sentences)
   - What is the analogous application in the user's field?
   - What specific implementation would this look like?
   - What breaks in the analogy? (limits of the transfer)
   - Score: 1-10 (novelty × applicability)

5. **Write report** to `_autonomous/results/cross-domain/{date}.md`.
   Follow the report template from `knowledge/quality-gate.md`.
   The Adaptations section is CRITICAL here — each transfer must map to a specific user project.

6. **Quality gate**: Verify score >= 50 before emitting `<promise>DONE</promise>`.

## Rate Limit Handling

If you hit a rate limit:
1. Wait 60 seconds
2. Retry the failed operation
3. After 3 consecutive failures: `<promise>RATE_LIMITED</promise>`
