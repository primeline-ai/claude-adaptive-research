# Quality Gate

Every research report is scored before the loop completes. Score >= 50 required for `<promise>DONE</promise>`.

> **Premium rubric available**: For stricter premium-by-default scoring, use the
> Python rubric at [`knowledge/quality-gate-v2.md`](quality-gate-v2.md) backed by
> [`scripts/quality_gate_v2.py`](../scripts/quality_gate_v2.py). v1 (this doc) and
> v2 are independent gates; v2 raises the bar with citation density, DSV evidence,
> gap disclosure, ECP section, and cross-track convergence checks.

## Prerequisites (all must pass)

| Check | Requirement |
|-------|-------------|
| Report file exists | Written to `_autonomous/results/` |
| Structure | H1 heading + at least 2x H2 + at least 1 list or table |
| Findings section | Section named "Findings", "Results", "Ergebnisse", or "Key Insights" exists |

If any prerequisite fails: fix the report, do NOT emit DONE.

## Quality Score (4 x 25 = max 100)

| Criterion | Points | How to check |
|-----------|--------|-------------|
| Report exists (prerequisites pass) | 25 | File exists + structure valid |
| Word count >= minimum | 25 | Free-text: 500 words. Presets: see preset frontmatter `min_words` |
| Originality | 25 | If previous reports exist in same domain folder: Jaccard similarity < 0.7. First report = 25 auto. |
| Findings count >= minimum | 25 | Free-text: 3 findings. Presets: see preset frontmatter `min_findings` |

## Scoring Process

1. After writing the report, calculate the score
2. Write score in report header: `**Quality Score**: {score}/100`
3. If score >= 50: emit `<promise>DONE</promise>`
4. If score < 50: identify weakest criterion, improve report, re-score
5. After 3 failed attempts: write partial report with score, emit DONE anyway

## Report Template

```markdown
# {Title}

**Date**: {YYYY-MM-DD}
**Topic**: {original topic or preset name}
**Quality Score**: {score}/100
**Domain**: {domain folder name}

---

## Summary

{2-3 sentences: what was researched, key insight}

## Findings

### 1. {Finding title}
{Description, evidence, source}

### 2. {Finding title}
...

## Adaptations

{This section uses the user's profile from _autonomous/profile.yaml}

### → {Project 1 from profile}
{How this finding applies to this project}

### → {Project 2 from profile}
{How this finding applies}

### → Personal
{How this applies to the user personally}

## Sources

- {Source 1}
- {Source 2}
```
