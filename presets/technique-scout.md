---
preset: technique-scout
description: Find new techniques, tools, and patterns in your field
max_iterations: 10
completion_promise: DONE
min_findings: 5
min_words: 500
---

## System Safety
You are running AUTONOMOUSLY. Write ONLY to `_autonomous/` directory.
No modifications to any other project files. No git operations. No destructive actions.

## Goal

Search for new techniques, tools, frameworks, and patterns that are relevant to the user's field and projects. Evaluate each finding concretely against the user's profile (from `_autonomous/profile.yaml`).

## Method

1. **Load context**: Read `_autonomous/profile.yaml` to understand the user's projects, role, and goals.

2. **Search** using firecrawl_search (or WebSearch as fallback):
   - Reddit: `site:reddit.com` + user's field keywords
   - Hacker News: `site:news.ycombinator.com` + relevant terms
   - GitHub: new repos, trending tools in the user's tech stack
   - Research: recent papers, blog posts, tutorials

3. **Evaluate** each technique found:
   - Is it new (not already known/used by the user)?
   - Is it actionable (can be applied within a week)?
   - Does it fit the user's tech stack and goals?
   - Score: 1-10 (relevance to user's projects)

4. **Write report** to `_autonomous/results/{best-matching-domain}/{date}.md`.
   Follow the report template from `knowledge/quality-gate.md`.
   Include an Adaptations section mapping findings to user's projects.

5. **Quality gate**: Verify score >= 50 before emitting `<promise>DONE</promise>`.

## Rate Limit Handling

If you hit a rate limit:
1. Wait 60 seconds
2. Retry the failed operation
3. After 3 consecutive failures: `<promise>RATE_LIMITED</promise>`
