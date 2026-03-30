---
preset: trend-radar
description: Spot emerging trends and opportunities in any niche
max_iterations: 10
completion_promise: DONE
min_findings: 5
min_words: 500
---

## System Safety
You are running AUTONOMOUSLY. Write ONLY to `_autonomous/` directory.
No modifications to any other project files. No git operations. No destructive actions.

## Goal

Detect early-stage trends, rising tools, shifting sentiment, and emerging opportunities in the user's niche or a specified area. Focus on signals that are GROWING but not yet mainstream.

## Method

1. **Load context**: Read `_autonomous/profile.yaml` for user's field, tools, and goals.

2. **Signal search** across multiple sources:
   - firecrawl_search: "[niche] trends 2026", "[niche] emerging tools"
   - Reddit: "site:reddit.com [niche] new OR rising OR underrated"
   - Hacker News: "site:news.ycombinator.com [niche]" (last 30 days)
   - GitHub: trending repos in relevant languages/topics
   - X/Twitter: search for niche hashtags + "just discovered" OR "game changer"

3. **Trend classification** for each signal:
   | Stage | Description | Action |
   |-------|------------|--------|
   | Emerging | < 1000 mentions, growing fast | Watch closely |
   | Rising | 1K-10K mentions, clear momentum | Evaluate for adoption |
   | Mainstream | > 10K mentions, established | Too late for first-mover |
   | Declining | Mentions dropping, alternatives emerging | Avoid |

4. **Opportunity analysis**:
   - Is there a gap the user could fill? (content, tool, service)
   - First-mover advantage window: how long?
   - Effort to capitalize vs. potential return
   - Score: 1-10 (opportunity size × user fit)

5. **Write report** to `_autonomous/results/{best-matching-domain}/{date}.md`.
   Follow the report template from `knowledge/quality-gate.md`.
   Adaptations section: map each trend to specific actions for the user's projects.

6. **Quality gate**: Verify score >= 50 before emitting `<promise>DONE</promise>`.

## Rate Limit Handling

If you hit a rate limit:
1. Wait 60 seconds
2. Retry the failed operation
3. After 3 consecutive failures: `<promise>RATE_LIMITED</promise>`
