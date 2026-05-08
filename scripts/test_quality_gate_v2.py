#!/usr/bin/env python3
"""Tests for quality_gate_v2.py - Phase 2 binary gate validation."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from quality_gate_v2 import (
    compute_tier,
    count_words,
    metric_citation_density,
    metric_cross_track_convergence,
    metric_dsv_evidence,
    metric_ecp_section,
    metric_gap_disclosure,
    score_report,
)


class TestCitationDensity(unittest.TestCase):
    def test_pass_with_urls_and_citations(self):
        text = "Word " * 200 + " https://example.com [1] (2024)"
        wc = count_words(text)
        result = metric_citation_density(text, wc)
        self.assertGreaterEqual(result["value"], 1.0)
        self.assertTrue(result["pass"])

    def test_fail_no_citations(self):
        text = "Word " * 1000
        wc = count_words(text)
        result = metric_citation_density(text, wc)
        self.assertEqual(result["value"], 0.0)
        self.assertFalse(result["pass"])

    def test_iec_dnv_patterns(self):
        text = "IEC 61400-25 covers SCADA. DNV-RP-A203 is qualification. " * 100
        wc = count_words(text)
        result = metric_citation_density(text, wc)
        self.assertGreater(result["citations"], 0)


class TestDSVEvidence(unittest.TestCase):
    def test_pass_with_dsv_markers(self):
        text = (
            "VALIDATE BY: x. Why: y. Reasoning: z. "
            "Decompose: a. IMPACT IF WRONG: b. " + "word " * 100
        )
        wc = count_words(text)
        result = metric_dsv_evidence(text, wc)
        self.assertTrue(result["pass"])

    def test_fail_no_markers(self):
        text = "Word " * 1000
        wc = count_words(text)
        result = metric_dsv_evidence(text, wc)
        self.assertFalse(result["pass"])

    def test_alternative_interpretation_counts(self):
        text = "Alternative interpretation: x. " * 50
        wc = count_words(text)
        result = metric_dsv_evidence(text, wc)
        self.assertGreater(result["matches"], 0)


class TestGapDisclosure(unittest.TestCase):
    def test_present_for_known_headers(self):
        for header in [
            "## Deferred-and-Untested",
            "## Gaps",
            "## What This Does NOT Cover",
            "## Open Questions",
            "## Limitations",
            "## Honest Gaps",
            "## Honest Weakness Map",
        ]:
            with self.subTest(header=header):
                text = f"Body\n\n{header}\n\nContent"
                self.assertTrue(metric_gap_disclosure(text)["pass"])

    def test_missing(self):
        text = "## Summary\n\nNo gap section."
        self.assertFalse(metric_gap_disclosure(text)["pass"])


class TestECPSection(unittest.TestCase):
    def test_full_3_legs(self):
        text = """## Empirical Completion Proof

Leg 1 (Trigger): Did fire.
Leg 2 (Effect): Took effect.
Leg 3 (Consumption): Consumer used it.
"""
        result = metric_ecp_section(text)
        self.assertTrue(result["header_present"])
        self.assertEqual(result["legs_count"], 3)
        self.assertTrue(result["pass"])

    def test_2_of_3_legs_passes(self):
        text = """## Empirical Completion Proof

Leg 1 (Trigger): yes.
Leg 2 (Effect): yes.
"""
        result = metric_ecp_section(text)
        self.assertEqual(result["legs_count"], 2)
        self.assertTrue(result["pass"])

    def test_1_of_3_legs_fails(self):
        text = """## Empirical Completion Proof

Leg 1 (Trigger): yes.
"""
        result = metric_ecp_section(text)
        self.assertEqual(result["legs_count"], 1)
        self.assertFalse(result["pass"])

    def test_no_header_fails(self):
        text = "## Conclusion\n\nDone."
        result = metric_ecp_section(text)
        self.assertFalse(result["header_present"])
        self.assertFalse(result["pass"])

    def test_legs_in_other_sections_do_not_falsely_pass(self):
        # CRITICAL bug fix verification: leg keywords outside ECP header should not count
        text = """## Findings

**Trigger**: This is in a findings section, not ECP.
**Effect**: Same here.
**Consumption**: Also not ECP.

## Conclusion

Done.
"""
        result = metric_ecp_section(text)
        self.assertFalse(result["header_present"])
        self.assertEqual(result["legs_count"], 0)
        self.assertFalse(result["pass"])

    def test_legs_only_after_header(self):
        # Header present but legs in earlier section
        text = """## Findings

**Trigger**: Pre-ECP usage.

## Empirical Completion Proof

Some text here. No legs here.

## Conclusion

**Effect**: post-ECP but in conclusion.
"""
        result = metric_ecp_section(text)
        self.assertTrue(result["header_present"])
        self.assertEqual(result["legs_count"], 0)
        self.assertFalse(result["pass"])

    def test_bold_legs_match(self):
        text = """## Empirical Completion Proof

**Trigger**: fired.
**Effect**: landed.
**Consumption**: read.
"""
        result = metric_ecp_section(text)
        self.assertEqual(result["legs_count"], 3)
        self.assertTrue(result["pass"])


class TestCrossTrackConvergence(unittest.TestCase):
    def test_single_track_auto_pass(self):
        text = "## Summary\n\nThis is a single-topic report."
        result = metric_cross_track_convergence(text)
        self.assertFalse(result["multi_track"])
        self.assertTrue(result["pass"])

    def test_multi_track_pass_with_2_convergences(self):
        text = """Track A delivered.
Track B delivered.
Track C delivered.

## Convergence 1: foo
## Convergence 2: bar
"""
        result = metric_cross_track_convergence(text)
        self.assertTrue(result["multi_track"])
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["pass"])

    def test_multi_track_fail_with_1_convergence(self):
        text = "Track A. Track B. Track C.\n\n## Convergence 1: x\n"
        result = metric_cross_track_convergence(text)
        self.assertTrue(result["multi_track"])
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["pass"])

    def test_multi_track_keyword_detection(self):
        # multi-track keyword OR 5 tracks phrase = multi-track
        for keyword in ["multi-track", "5 tracks"]:
            with self.subTest(keyword=keyword):
                text = f"Report on {keyword}."
                result = metric_cross_track_convergence(text)
                self.assertTrue(result["multi_track"])

    def test_single_track_a_mention_is_not_multi_track(self):
        # HIGH bug fix: single "Track A" mention should NOT trigger multi-track
        text = "Keep Track A of this pattern. Single topic report."
        result = metric_cross_track_convergence(text)
        self.assertFalse(result["multi_track"])
        self.assertTrue(result["pass"])  # auto-pass for single-track

    def test_two_distinct_tracks_is_multi_track(self):
        # 2+ distinct tracks = multi-track
        text = "Track A delivered. Track B delivered.\n\n## Convergence 1: x\n## Convergence 2: y"
        result = metric_cross_track_convergence(text)
        self.assertTrue(result["multi_track"])
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["pass"])


class TestTier(unittest.TestCase):
    def test_premium_5_of_5(self):
        metrics = [{"pass": True}] * 5
        self.assertEqual(compute_tier(metrics), "premium")

    def test_standard_3_of_5(self):
        metrics = [{"pass": True}] * 3 + [{"pass": False}] * 2
        self.assertEqual(compute_tier(metrics), "standard")

    def test_standard_4_of_5(self):
        metrics = [{"pass": True}] * 4 + [{"pass": False}]
        self.assertEqual(compute_tier(metrics), "standard")

    def test_reject_2_of_5(self):
        metrics = [{"pass": True}] * 2 + [{"pass": False}] * 3
        self.assertEqual(compute_tier(metrics), "reject")

    def test_reject_0_of_5(self):
        metrics = [{"pass": False}] * 5
        self.assertEqual(compute_tier(metrics), "reject")


class TestScoreReportEndToEnd(unittest.TestCase):
    def test_nonexistent_file_returns_error(self):
        result = score_report("/tmp/nonexistent_xyz_123_abc.md")
        self.assertIn("error", result)

    def test_empty_file_rejects(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("")
            tmppath = f.name
        try:
            result = score_report(tmppath)
            self.assertEqual(result["tier"], "reject")
        finally:
            os.unlink(tmppath)

    def test_premium_report_strict(self):
        text = (
            "# Premium Report\n\n"
            "Body content with citations [1] (2024) https://example.com "
            "and IEC 61400-25 references. " * 50
            + "\n\n"
            + "Why: because. VALIDATE BY: testing. Reasoning: clear. "
            "Decompose: yes. IMPACT IF WRONG: large. " * 10
            + "\n\n## Deferred-and-Untested\n\nNothing pending.\n\n"
            + "## Empirical Completion Proof\n\n"
            + "**Trigger**: ran. **Effect**: passed. **Consumption**: read.\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(text)
            tmppath = f.name
        try:
            result = score_report(tmppath)
            # Strict: this synthetic report has all 5 metric passes (single-track auto-pass on convergence)
            self.assertEqual(result["tier"], "premium")
            self.assertEqual(result["passed"], 5)
        finally:
            os.unlink(tmppath)

    def test_real_synthesis_doc(self):
        synthesis = os.environ.get("QG_V2_REAL_REPORT")
        if not synthesis or not os.path.exists(synthesis):
            self.skipTest(
                "Real synthesis doc not present "
                "(set QG_V2_REAL_REPORT=/path/to/report.md to enable)"
            )
        result = score_report(synthesis)
        self.assertIn(result["tier"], ["premium", "standard"])
        ecp = next(m for m in result["metrics"] if m["name"] == "ecp_section")
        self.assertTrue(ecp["header_present"])


class TestPerformance(unittest.TestCase):
    def test_under_2s_on_1000_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            for i in range(1000):
                f.write(
                    f"## Section {i}\n\nWord [1] https://example.com "
                    f"VALIDATE BY: x.\n\n"
                )
            tmppath = f.name
        try:
            start = time.time()
            score_report(tmppath)
            elapsed = time.time() - start
            self.assertLess(
                elapsed, 2.0, f"Took {elapsed:.2f}s, expected <2s"
            )
        finally:
            os.unlink(tmppath)


if __name__ == "__main__":
    unittest.main(verbosity=2)
