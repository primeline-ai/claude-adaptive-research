#!/usr/bin/env python3
"""Tests for gate-keeper.py - Phase 0.5 detection refinement.

These tests document the EXPECTED behavior after refinement.
Run before Phase 0.5b: some tests will FAIL (TDD red).
Run after Phase 0.5b: all tests must PASS (TDD green).
"""

import importlib.util
import sys
import unittest
from pathlib import Path

# Load gate-keeper.py via spec because filename has hyphen (not valid Python module name)
_spec = importlib.util.spec_from_file_location(
    "gate_keeper",
    str(Path(__file__).parent / "gate-keeper.py"),
)
gate_keeper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_keeper)


class TestKairnDetection(unittest.TestCase):
    """Kairn gate: detect actual Kairn usage in reports.

    Current bug (Phase -1 finding): regex `kn_learn|mcp__kairn__kn_learn` only
    matches literal tool-name string. Reports that referenced 5+ Kairn node IDs
    and the word 'Kairn' extensively were marked FAIL because the literal
    `kn_learn` string was not in the report text. This is wrong: those reports
    clearly engaged with Kairn.

    Expected behavior after refinement:
    - Literal kn_learn call: PASS
    - Kairn node-ID references (8-char hex): WARN (engaged but writes not verified)
    - 3+ "Kairn" word references AND at least one node-ID: WARN
    - Loop-errors log contains kairn-fail: PASS (acceptable fallback)
    - Zero Kairn evidence of any kind: FAIL
    """

    def test_kn_learn_literal_passes(self):
        report = "## Findings\nCalled kn_learn with type=pattern."
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "PASS")

    def test_node_id_references_warn(self):
        """Reports referencing Kairn node IDs (8-char hex) should WARN, not FAIL.

        Strict threshold: 2+ node IDs AND 2+ Kairn word mentions required.
        """
        report = (
            "## 6. Kairn Past Findings Cross-Reference\n"
            "- Pattern Memory: `83ea68b8` shows decay logic.\n"
            "- Cross-cutting: `aebb0c07` batch query, 8 topic clusters.\n"
            "- Conflict: `92621c69` and `d1dc493d` Robin pushback.\n"
            "### Kairn alerts (active)\n### Top 5 cross-cutting insights per Kairn synth\n"
        )
        status, detail = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "WARN", f"Expected WARN, got {status}: {detail}")
        self.assertIn("node", detail.lower())

    def test_kairn_word_mentions_alone_fail(self):
        """Word 'Kairn' alone (no node IDs, no kn_learn) should still FAIL."""
        report = "## Findings\nWe should consider Kairn for memory but didn't use it."
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "FAIL")

    def test_zero_evidence_fails(self):
        report = "## Findings\nThis report has nothing to do with memory."
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "FAIL")

    def test_kn_recall_kn_memories_also_count(self):
        """Other Kairn tool calls (kn_recall, kn_memories) should also count."""
        report = "## Findings\nCalled kn_recall and kn_memories to look up context."
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "PASS")

    def test_kn_learn_only_in_code_block_does_not_pass(self):
        """A kn_learn shown inside a fenced code block (example/template) should
        not count as actual usage."""
        report = (
            "## Methodology\n"
            "Each finding can be saved with:\n"
            "```python\n"
            "kn_learn(content='example', type='pattern')\n"
            "```\n"
            "## Findings\nNo actual calls were made.\n"
        )
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "FAIL")

    def test_single_node_id_with_one_kairn_mention_fails(self):
        """One commit SHA + one Kairn mention is too weak - prevent false WARN.

        Risk: reports that mention Kairn once and contain one commit SHA in a
        code block would previously trigger WARN even though there is zero
        actual Kairn engagement.
        """
        report = (
            "## Findings\nRefactor of Kairn integration is pending.\n"
            "Reference: commit `ae01f820` from last week.\n"
        )
        status, _ = gate_keeper.check_kairn(None, report)
        self.assertEqual(status, "FAIL")


class TestEcpDetection(unittest.TestCase):
    """ECP gate: requires both Empirical Completion Proof + Deferred-and-Untested sections."""

    def test_both_sections_pass(self):
        report = (
            "## Findings\nstuff\n\n"
            "## Empirical Completion Proof\n"
            "**Leg 1 (Trigger)**: x\n"
            "**Leg 2 (Effect)**: y\n"
            "**Leg 3 (Consumption)**: z\n\n"
            "## Deferred-and-Untested\nNone.\n"
        )
        status, _ = gate_keeper.check_ecp(report)
        self.assertEqual(status, "PASS")

    def test_ecp_with_suffix_in_header_passes(self):
        """Real-world: ## Empirical Completion Proof (3-leg) should match."""
        report = (
            "## Empirical Completion Proof (3-leg)\n"
            "**TRIGGER**: x\n**EFFECT**: y\n**CONSUMPTION**: z\n\n"
            "## Deferred-and-Untested\nNone.\n"
        )
        status, _ = gate_keeper.check_ecp(report)
        self.assertEqual(status, "PASS")

    def test_missing_deferred_fails(self):
        report = (
            "## Empirical Completion Proof\n"
            "**Trigger**: x\n**Effect**: y\n"
        )
        status, detail = gate_keeper.check_ecp(report)
        self.assertEqual(status, "FAIL")
        self.assertIn("Deferred-and-Untested", detail)
        self.assertNotIn("Empirical Completion Proof", detail)

    def test_missing_ecp_fails(self):
        report = "## Findings\n## Deferred-and-Untested\nNone.\n"
        status, detail = gate_keeper.check_ecp(report)
        self.assertEqual(status, "FAIL")
        self.assertIn("Empirical Completion Proof", detail)

    def test_substring_mention_does_not_pass(self):
        """Just mentioning 'Empirical Completion' in prose shouldn't satisfy."""
        report = "## Findings\nWe should add Empirical Completion Proof later.\n"
        status, _ = gate_keeper.check_ecp(report)
        self.assertEqual(status, "FAIL")


class TestReportStructure(unittest.TestCase):
    """Smoke test that existing checks still work."""

    def test_minimal_passes(self):
        report = (
            "# Title\n"
            "## Findings\n- one\n- two\n"
            "## Section 2\nContent."
        )
        status, _ = gate_keeper.check_report_structure(report)
        self.assertEqual(status, "PASS")

    def test_ergebnisse_alias_passes(self):
        report = "# Title\n## Ergebnisse\n- one\n- two\n## Section 2\nContent."
        status, _ = gate_keeper.check_report_structure(report)
        self.assertEqual(status, "PASS")


if __name__ == "__main__":
    unittest.main()
