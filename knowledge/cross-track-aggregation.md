# Cross-Track Aggregation

When you run **multiple research tracks in parallel** on related topics, the cross-track aggregator detects where independent tracks converged on the same idea. Convergence across independent observers is a much stronger signal than a single track finding something interesting.

## When this applies

You run the same `/auto-run` workflow as N separate sub-agents, each with a different angle on a problem. For example:

- Track A: deep technical research on a specific algorithm
- Track B: competitor / market-side scan on the same problem space
- Track C: prior-art / literature review on a related field
- Track D: pressure-test of an existing roadmap

Each track produces its own findings. The aggregator reads all tracks and reports where the same concept showed up independently in 2+ tracks.

This is **not** for single-track runs - those just write a normal report.

## Pipeline

```
[Track A sub-agent] ──┐
[Track B sub-agent] ──┼──→ each writes track-{ID}.json
[Track C sub-agent] ──┤    to {cache_root}/cross-track-{run_id}/
[Track D sub-agent] ──┘
                          │
                          v
                  [cross_track_aggregator.py]
                          │
                          v
                  ## Cross-Track Synthesis
                  ### Convergence 1: ...
                  ### Convergence 2: ...
                  (or "no convergence detected")
```

## Findings file format

Each sub-agent writes its findings to:

```
{cache_root}/cross-track-{run_id}/track-{TRACK_ID}.json
```

- `cache_root` defaults to `./_autonomous/cross-track-cache/`
- `run_id` is a string identifier shared across all sub-agents in the same parallel run
- `TRACK_ID` is a single uppercase letter (`A`, `B`, ...)

The file contains a **JSON array** of finding objects matching [`schemas/cross_track_findings_schema.json`](../schemas/cross_track_findings_schema.json):

```json
[
  {
    "run_id": "swarm-intel-2026-06-01",
    "track_id": "A",
    "finding_id": "a1b2c3d4",
    "finding_type": "pattern",
    "content": "Stigmergy emerges as a coordination primitive in...",
    "citations": ["https://example.org/paper.pdf", "Smith 2024"],
    "layer": "algorithms",
    "components": ["scheduler", "task-router"],
    "impact_tag": "coordination-primitive",
    "confidence": "high",
    "timestamp": "2026-06-01T12:34:56Z"
  }
]
```

`finding_id` is an 8-char SHA256-hex prefix of the content. Generate with:

```python
import hashlib
finding_id = hashlib.sha256(content.encode()).hexdigest()[:8]
```

## Running the aggregator

After all tracks have finished writing their JSON files:

```bash
python3 scripts/cross_track_aggregator.py <run_id> <output_path> [--cache-root PATH] [--json]
```

For example:

```bash
python3 scripts/cross_track_aggregator.py \
    swarm-intel-2026-06-01 \
    _autonomous/results/swarm-intel-2026-06-01-synthesis.md \
    --json
```

This reads every `track-*.json` under `{cache_root}/cross-track-{run_id}/`, runs Union-Find clustering on the findings using Jaccard similarity (threshold 0.5) over the content tokens, and writes a `## Cross-Track Synthesis` section to `output_path`.

Atomic write semantics: writes to `output_path.tmp`, then `os.replace()` to final path. No partial files on failure.

## Output schema

JSON summary (when `--json` is set):

```json
{
  "run_id": "swarm-intel-2026-06-01",
  "tracks_read": ["A", "B", "C"],
  "findings_total": 18,
  "convergences_found": 2,
  "output_path": "_autonomous/results/swarm-intel-2026-06-01-synthesis.md"
}
```

Markdown body:

```markdown
## Cross-Track Synthesis

**Run**: swarm-intel-2026-06-01
**Tracks analysed**: A, B, C
**Total findings**: 18
**Convergences detected**: 2

### Convergence 1: stigmergy, coordination, indirect

**Tracks**: A, C
**Findings in cluster**: 4
**Shared keywords**: stigmergy, coordination, indirect, pheromone, ...

> {anchor finding content}

_Anchor finding ID_: `a1b2c3d4`
_All finding IDs_: `a1b2c3d4`, `e5f6g7h8`, ...
```

## Convergence detection

- **Tokenization**: lowercase, words >= 3 chars, common stop words removed (the/and/of/etc.)
- **Similarity**: Jaccard over token sets (`|A ∩ B| / |A ∪ B|`)
- **Threshold**: >= 0.5 to consider two findings related
- **Clustering**: Union-Find connects related findings into clusters
- **Filter**: a cluster only counts as a "convergence" if it contains findings from 2+ different tracks (same-track-only clusters are dropped)

## Cleanup

Aggregator output dirs accumulate over time. To remove old `cross-track-*` dirs:

```bash
bash scripts/cleanup_cross_track_orphans.sh [--dry-run] [--cache-root PATH]
```

Removes any `cross-track-*` dir older than 7 days. Use `--dry-run` to preview.

## Performance

Single regex sweep + Union-Find. < 5s on 5 tracks * 20 findings each (verified by test suite).

## Tests

```bash
python3 -m unittest scripts.test_cross_track_aggregator -v
```

23 unit tests covering tokenization, Jaccard, Union-Find, file reading (incl. malformed JSON), convergence detection (zero/single/two/three-track cases), atomic writes, and a 5x20 performance test.

## Dependencies

Python 3.9+ standard library only. No external packages.
