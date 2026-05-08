#!/usr/bin/env python3
"""Tests for cross_track_aggregator.py - Auto-Run v2 Phase 3 binary gate."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
import warnings
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from cross_track_aggregator import (
    JACCARD_THRESHOLD,
    Convergence,
    _UnionFind,
    _jaccard,
    _tokenize,
    detect_convergence,
    read_track_findings,
    write_aggregate_synthesis,
)


def _finding_id(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def _make_finding(
    run_id: str,
    track_id: str,
    content: str,
    finding_type: str = "pattern",
    layer: str = "cross-cutting",
    confidence: str = "high",
    citations=None,
) -> dict:
    return {
        "run_id": run_id,
        "track_id": track_id,
        "finding_id": _finding_id(content),
        "finding_type": finding_type,
        "content": content,
        "citations": citations or [],
        "layer": layer,
        "components": [],
        "impact_tag": "test",
        "confidence": confidence,
        "timestamp": "2026-05-08T14:00:00Z",
    }


def _write_track_file(findings_dir: Path, track_id: str, findings) -> None:
    findings_dir.mkdir(parents=True, exist_ok=True)
    track_file = findings_dir / f"track-{track_id}.json"
    track_file.write_text(json.dumps(findings, indent=2), encoding="utf-8")


class TestTokenize(unittest.TestCase):
    def test_returns_frozenset(self):
        result = _tokenize("Quality gate enforcement improves output.")
        self.assertIsInstance(result, frozenset)

    def test_stop_words_excluded(self):
        result = _tokenize("the and is of for with")
        self.assertEqual(result, frozenset())

    def test_lowercases(self):
        result = _tokenize("Premium Quality GATE")
        self.assertIn("premium", result)
        self.assertIn("quality", result)


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        a = frozenset(["quality", "gate", "premium"])
        self.assertAlmostEqual(_jaccard(a, a), 1.0)

    def test_disjoint(self):
        a = frozenset(["quality", "gate"])
        b = frozenset(["research", "track"])
        self.assertAlmostEqual(_jaccard(a, b), 0.0)

    def test_partial(self):
        a = frozenset(["quality", "gate"])
        b = frozenset(["quality", "track"])
        self.assertAlmostEqual(_jaccard(a, b), 1 / 3)

    def test_both_empty(self):
        self.assertAlmostEqual(_jaccard(frozenset(), frozenset()), 1.0)


class TestUnionFind(unittest.TestCase):
    def test_initially_separate(self):
        uf = _UnionFind(5)
        for i in range(5):
            self.assertEqual(uf.find(i), i)

    def test_union_connects(self):
        uf = _UnionFind(4)
        uf.union(0, 1)
        self.assertEqual(uf.find(0), uf.find(1))


class TestReadTrackFindings(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_track_findings("none", Path(tmp)), {})

    def test_reads_multiple_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            run_id = "test-002"
            findings_dir = cache_root / f"cross-track-{run_id}"
            for tid in ["A", "B", "C"]:
                f = [_make_finding(run_id, tid, f"Track {tid} finding.")]
                _write_track_file(findings_dir, tid, f)
            result = read_track_findings(run_id, cache_root)
            self.assertEqual(sorted(result.keys()), ["A", "B", "C"])

    def test_malformed_json_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            run_id = "test-003"
            findings_dir = cache_root / f"cross-track-{run_id}"
            findings_dir.mkdir(parents=True)
            (findings_dir / "track-A.json").write_text("{ broken ]]]")
            valid = [_make_finding(run_id, "B", "Valid finding about delegation.")]
            _write_track_file(findings_dir, "B", valid)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = read_track_findings(run_id, cache_root)
            self.assertNotIn("A", result)
            self.assertIn("B", result)
            self.assertTrue(any("Malformed" in str(w.message) for w in caught))

    def test_non_array_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            run_id = "test-004"
            findings_dir = cache_root / f"cross-track-{run_id}"
            findings_dir.mkdir(parents=True)
            (findings_dir / "track-A.json").write_text('{"x": 1}')
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = read_track_findings(run_id, cache_root)
            self.assertNotIn("A", result)


class TestDetectConvergence(unittest.TestCase):
    def test_zero_tracks(self):
        self.assertEqual(detect_convergence({}), [])

    def test_single_track(self):
        f = {"A": [_make_finding("r", "A", "Quality gate premium output workflow delegation.")]}
        self.assertEqual(detect_convergence(f), [])

    def test_two_tracks_no_overlap(self):
        f = {
            "A": [_make_finding("r", "A", "Photosynthesis chlorophyll plant biology.")],
            "B": [_make_finding("r", "B", "Kubernetes container orchestration pod.")],
        }
        self.assertEqual(detect_convergence(f), [])

    def test_two_tracks_high_overlap(self):
        shared = "Premium quality gate enforcement delegation orchestration system workflow."
        f = {
            "A": [_make_finding("r", "A", shared)],
            "B": [_make_finding("r", "B", shared)],
        }
        result = detect_convergence(f)
        self.assertEqual(len(result), 1)
        self.assertIn("A", result[0].tracks)
        self.assertIn("B", result[0].tracks)

    def test_same_track_no_false_convergence(self):
        identical = "Quality gate premium output workflow."
        f = {
            "A": [
                _make_finding("r", "A", identical),
                _make_finding("r", "A", identical + " extra."),
            ],
            "B": [_make_finding("r", "B", "Photosynthesis biology chlorophyll.")],
        }
        self.assertEqual(detect_convergence(f), [])

    def test_three_tracks_two_convergences(self):
        run_id = "tc"
        c1_a = "Quality gate enforcement premium delegation workflow research output system."
        c1_b = "Workflow quality gate premium enforcement delegation research output system."
        orth_b = "Photosynthesis chlorophyll biology ecosystem plant metabolism species."
        c2_a = "Token budget cost tracking audit performance limits resource allocation monitoring."
        c2_c = "Token budget cost resource tracking allocation monitoring audit performance limits."
        f = {
            "A": [_make_finding(run_id, "A", c1_a), _make_finding(run_id, "A", c2_a)],
            "B": [_make_finding(run_id, "B", c1_b), _make_finding(run_id, "B", orth_b)],
            "C": [_make_finding(run_id, "C", orth_b), _make_finding(run_id, "C", c2_c)],
        }
        result = detect_convergence(f)
        self.assertGreaterEqual(len(result), 2)
        for c in result:
            self.assertGreaterEqual(len(c.tracks), 2)


class TestWriteAggregateSynthesis(unittest.TestCase):
    def test_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "findings"
            run_id = "smoke"
            findings_dir = cache_root / f"cross-track-{run_id}"
            shared = "Quality gate premium enforcement delegation workflow research output."
            for tid in ["A", "B"]:
                _write_track_file(findings_dir, tid, [_make_finding(run_id, tid, shared)])
            output_path = Path(tmp) / "synthesis.md"
            summary = write_aggregate_synthesis(run_id, output_path, cache_root)
            self.assertTrue(output_path.exists())
            content = output_path.read_text()
            self.assertIn("## Cross-Track Synthesis", content)
            self.assertEqual(summary["tracks_read"], ["A", "B"])

    def test_atomic_write_no_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "findings"
            run_id = "atomic"
            findings_dir = cache_root / f"cross-track-{run_id}"
            shared = "Premium quality gate enforcement delegation workflow."
            _write_track_file(findings_dir, "A", [_make_finding(run_id, "A", shared)])
            _write_track_file(findings_dir, "B", [_make_finding(run_id, "B", shared)])
            output_path = Path(tmp) / "out.md"
            write_aggregate_synthesis(run_id, output_path, cache_root)
            tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
            self.assertFalse(tmp_path.exists())

    def test_empty_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "synthesis.md"
            summary = write_aggregate_synthesis("empty", output_path, Path(tmp) / "findings")
            self.assertEqual(summary["tracks_read"], [])
            self.assertEqual(summary["findings_total"], 0)


class TestPerformance(unittest.TestCase):
    def test_under_5s_5x20(self):
        vocab = [
            "quality gate premium enforcement workflow delegation research output",
            "token budget cost tracking audit performance limits resource allocation",
            "orchestration multi-track parallel dispatch synthesis aggregation",
            "knowledge graph edges nodes coactivation context memory session",
            "delegation enforcer hook post-tool tracker module findings exchange",
        ]
        f_by_track = {}
        for t_idx, tid in enumerate("ABCDE"):
            track_findings = []
            for f_idx in range(20):
                base = vocab[(t_idx * 7 + f_idx * 3) % len(vocab)]
                content = f"{base} finding-{t_idx}-{f_idx} specific."
                track_findings.append(_make_finding("perf", tid, content))
            f_by_track[tid] = track_findings
        start = time.monotonic()
        detect_convergence(f_by_track)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
