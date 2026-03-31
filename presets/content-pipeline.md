---
preset: content-pipeline
description: Research and draft a content piece (blog post, article, guide) on any topic
max_iterations: 12
completion_promise: DONE
min_findings: 0
min_words: 1000
---

## System Safety
You are running AUTONOMOUSLY. Write ONLY to `_autonomous/` directory.
No modifications to any other project files. No git operations. No destructive actions.

## Goal

Research a topic thoroughly, then write a structured content draft (blog post, article, or guide). The output should be publication-ready with proper structure, evidence, and actionable takeaways.

## Parameters

- `--topic`: The content topic (required)

## Method

1. **Load context**: Read `_autonomous/profile.yaml` for the user's projects, role, and audience.

2. **Research phase** (3-5 searches):
   - firecrawl_search: "{topic} best practices 2026"
   - firecrawl_search: "{topic} examples case studies"
   - firecrawl_search: "{topic} common mistakes pitfalls"
   - firecrawl_search: "site:reddit.com {topic} tips"
   - If `injected_context` has `extra_keywords`: search those too

3. **Outline** the content:
   - Hook (why should the reader care?)
   - Problem statement (what pain point does this address?)
   - 5-7 key points with evidence from research
   - Actionable takeaways
   - Conclusion with call-to-action

4. **Write the draft** (1000+ words):
   - Clear, scannable structure (H2s, H3s, bullet points)
   - Evidence from research (cite sources)
   - Practical examples, not just theory
   - Written for the user's target audience (from profile)

5. **Write report** to `_autonomous/results/growth/{date}-{topic-slug}.md`.
   Follow the report template from `knowledge/quality-gate.md`.
   The Adaptations section should map content ideas to the user's specific projects.

6. **Update feedback state**: Save discovered keywords and content angles for future runs.

7. **Quality gate**: Verify score >= 50 before emitting `<promise>DONE</promise>`.

## Rate Limit Handling

If you hit a rate limit:
1. Wait 60 seconds
2. Retry the failed operation
3. After 3 consecutive failures: `<promise>RATE_LIMITED</promise>`
