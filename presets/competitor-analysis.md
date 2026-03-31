---
preset: competitor-analysis
description: Reverse-engineer success patterns from top performers in any niche
max_iterations: 10
completion_promise: DONE
min_findings: 5
min_words: 500
---

## System Safety
You are running AUTONOMOUSLY. Write ONLY to `_autonomous/` directory.
No modifications to any other project files. No git operations. No destructive actions.

## Goal

Analyze competitors or top performers in the user's niche. Decode what makes them successful — content patterns, positioning, tech stack, engagement strategies. Deliver actionable insights the user can apply.

## Parameters

- `--accounts`: Specific accounts/companies to analyze (optional)
- `--niche`: The niche to scan (optional, inferred from profile if not given)

## Method

1. **Load context**: Read `_autonomous/profile.yaml` for user's projects, niche, and goals.

2. **Identify targets** (if not specified via --accounts):
   - firecrawl_search: "{user's niche} top creators 2026"
   - firecrawl_search: "{user's niche} best examples"
   - Pick 3-5 top performers

3. **Analyze each target**:
   - firecrawl_search: "site:x.com {account}" or scrape their profile/site
   - What content do they produce? (format, frequency, topics)
   - What's their positioning? (tagline, value prop, audience)
   - What tools/tech do they use? (visible stack)
   - What engagement patterns work? (what gets shared/liked most)

4. **Pattern extraction**:
   - What do ALL top performers have in common?
   - What does NOBODY do that could be a gap?
   - What can the user steal/adapt immediately?
   - Score each pattern: 1-10 (ease of implementation x impact)

5. **Write report** to `_autonomous/results/growth/{date}-competitor-analysis.md`.
   Follow the report template from `knowledge/quality-gate.md`.
   Adaptations: map each pattern to specific actions for the user's projects.

6. **Update feedback state**: Save competitor names and discovered patterns.

7. **Quality gate**: Verify score >= 50 before emitting `<promise>DONE</promise>`.

## Rate Limit Handling

If you hit a rate limit:
1. Wait 60 seconds
2. Retry the failed operation
3. After 3 consecutive failures: `<promise>RATE_LIMITED</promise>`
