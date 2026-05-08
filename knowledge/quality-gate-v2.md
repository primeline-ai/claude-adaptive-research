# Quality Gate v2 - Premium Rubric

A stricter, mechanically scored rubric for research reports. Where [v1](quality-gate.md) is a 4-criterion prose check (`>= 50/100` to pass), v2 is a 5-metric Python-backed rubric with a tier contract:

- **Premium**: 5/5 metrics pass
- **Standard**: 3-4/5 metrics pass
- **Reject**: < 3 metrics pass

v1 and v2 are **independent gates**. Run whichever fits the loop; v2 is the choice when "premium-by-default" matters.

---

## How to invoke

```bash
python3 scripts/quality_gate_v2.py path/to/report.md
python3 scripts/quality_gate_v2.py --json path/to/report.md
```

Exit codes: `0 = premium`, `1 = standard`, `2 = reject (or error)`.

JSON output schema (`--json`):

```json
{
  "tier": "premium",
  "passed": 5,
  "total": 5,
  "word_count": 1820,
  "metrics": [
    {"name": "citation_density", "pass": true, "count": 12, "threshold": 9, "...": "..."},
    {"name": "dsv_evidence", "pass": true, "count": 11, "threshold": 9, "...": "..."},
    {"name": "gap_disclosure", "pass": true, "header_present": true, "match": "Deferred-and-Untested"},
    {"name": "ecp_section", "pass": true, "header_present": true, "trigger": true, "effect": true, "consumption": true},
    {"name": "cross_track_convergence", "pass": true, "multi_track": false, "note": "N/A (single-track report)"}
  ]
}
```

---

## The 5 metrics

### 1. Citation Density (>= 1 per 200 words)

Recognized citation forms:
- Bare URLs: `https://...`
- Numbered brackets: `[12]`
- Author-year: `(2024)`, `(Smith 2024)`, `et al., 2024`, `Smith and Lee 2024`
- Page/section refs: `p. 42`, `Section 3.2`, `§ 3.2`
- DOIs: `DOI: 10.xxx`
- Standards refs: `IEC 61400`, `DNV-GL-...`, `ISO 9001`
- Short hex node IDs: `` `a1b2c3d4` `` (8-char hex backtick-wrapped)
- Dated handoff filenames: `2026-05-08-some-doc.md`

The minimum density forces every ~200 words of prose to surface at least one external anchor.

### 2. DSV Evidence Count (>= 1 per 200 words)

Looks for explicit reasoning markers, including:
- `VALIDATE BY:` (assumption + validation method)
- `Why:`, `Reasoning:` (causal claims)
- `Decompose:`, `Suspend:`, `Validate:` (Decompose-Suspend-Validate framework)
- `Alternative interpretation`
- `Counterargument:`, `Confidence:`, `Assumption:`

Forces report to show its reasoning chain rather than asserting conclusions.

### 3. Gap Disclosure section

The report must contain at least one section whose header matches:
- `## Deferred-and-Untested`
- `## Gaps`
- `## What This Does NOT Cover`
- `## Open Questions`
- `## Limitations`
- `## Known Unknowns`

This forces explicit gap disclosure: what was NOT verified, what stayed open.

### 4. Empirical Completion Proof (ECP) section

Header pattern: `## Empirical Completion Proof` (or `## ECP`).

Below the header, scorer looks (within the same section, before any same-or-higher-level header) for at least 2 of these 3 leg markers:

- **Trigger** ("Leg 1", "Trigger:")
- **Effect** ("Leg 2", "Effect:")
- **Consumption** ("Leg 3", "Consumption:")

Pattern enforces 3-leg completion proof: thing fires + thing produces effect + downstream consumer reads the effect. Action evidence alone is not enough.

### 5. Cross-Track Convergence (multi-track only, >= 2 convergences)

Detects multi-track mode by looking for either:
- 2+ distinct `Track [A-Z]` headers in the document, or
- the keyword `multi-track` / `2 tracks` / etc., or
- at least one `### Convergence ...` header (which on its own implies multi-track)

For multi-track reports: requires >= 2 `### Convergence` headers in the report.

For single-track reports: **auto-pass with `note: "N/A (single-track report)"`**. A single-track run can still earn 5/5 = Premium. This is by design - convergence is a multi-track-only concept.

---

## Tier contract

```
passed = sum of metrics that returned pass: true

premium  if passed == total              (5/5)
standard if passed >= max(3, total - 2)  (3-4/5)
reject   otherwise                       (<3/5)
```

`reject` should NOT emit `<promise>DONE</promise>`. Standard and premium both pass the gate; the tier label goes into the report header so the reader sees what was achieved.

---

## Performance budget

Scorer is a single regex sweep over the markdown plus a few small structural lookups. < 2s on a 1000-line markdown report.

---

## When to use v2 vs v1

| Situation | Choice |
|---|---|
| Casual research, "good enough" output | v1 |
| Premium-by-default contract, citation-heavy work | v2 |
| Multi-track parallel research with cross-track synthesis | v2 (only v2 has the convergence metric) |
| Reports that must surface gaps + reasoning explicitly | v2 |

v1's report header looks like `**Quality Score**: 75/100`. v2 adds `**Quality Gate v2**: Premium (5/5)` or `**Quality Gate v2**: Standard (4/5)`.

Both can run in the same loop if you want both signals.

---

## Test coverage

Scorer has 31 unit tests covering each metric, edge cases (empty report, header-only, false-positive ECP detection, single-track auto-pass), tier boundaries, and end-to-end scoring.

Run the suite:

```bash
python3 -m unittest scripts.test_quality_gate_v2 -v
```
