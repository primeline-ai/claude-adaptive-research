#!/usr/bin/env python3
"""
Auto-Run Gate Keeper

Advisory gate enforcement for /auto-run research cycles.
Inspects reports and state files before allowing <promise>DONE</promise>.

Usage:
    python3 gate-keeper.py --report-path PATH [--state-path PATH] [--mode MODE] [--json]

Exit codes:
    0 = PASS (all gates satisfied)
    1 = FAIL (missing mandatory gates)
    2 = WARN (non-critical gaps)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# CONFIGURATION
# =============================================================================

GATES = [
    "report-structure",
    "qcr-lite",
    "synthesis",
    "ecp",
    "kairn",
    "quality",
]

REQUIRED_SECTIONS = {
    "report-structure": [r"^#\s+\S+", r"^##\s+\S+.*\n^##\s+\S+"],
    "qcr-lite": [
        r"<!--\s*QCR-LITE:\s*(COMPACTION|ANNIHILATION|ICE-9)",
        r"##\s*Darwinist Compaction",
        r"##\s*Annihilation Pass",
        r"##\s*Ice-9 Coherence Sweep",
    ],
    "synthesis": [r"##\s*Synthesis\b", r"##\s*Gamma Photons\b"],
    "ecp": [r"##\s*Empirical Completion Proof\b", r"##\s*Deferred-and-Untested\b"],
}


# =============================================================================
# GATE FUNCTIONS
# =============================================================================

def check_report_structure(report_text: str) -> tuple[str, str]:
    """Check minimum report structure."""
    has_h1 = bool(re.search(r"^#\s+\S+", report_text, re.MULTILINE))
    h2_count = len(re.findall(r"^##\s+\S+", report_text, re.MULTILINE))
    has_list = bool(re.search(r"^\s*-\s+\S+", report_text, re.MULTILINE))
    has_table = bool(re.search(r"^\s*\|[^|]+\|", report_text, re.MULTILINE))
    has_findings = bool(
        re.search(
            r"^##\s*(Findings|Ergebnisse|Techniques|Patterns|Gaps|Topics|Results)\b",
            report_text,
            re.MULTILINE | re.IGNORECASE,
        )
    )

    missing = []
    if not has_h1:
        missing.append("H1 title")
    if h2_count < 2:
        missing.append(f"H2 sections ({h2_count}/2)")
    if not (has_list or has_table):
        missing.append("list or table")
    if not has_findings:
        missing.append("Findings section")

    if missing:
        return "FAIL", f"Missing: {', '.join(missing)}"
    return "PASS", f"H1={has_h1}, H2={h2_count}, list/table={has_list or has_table}, findings={has_findings}"


def check_qcr_lite(report_text: str) -> tuple[str, str]:
    """Check QCR-lite markers or sections."""
    markers = [
        r"<!--\s*QCR-LITE:\s*COMPACTION\s*-->",
        r"<!--\s*QCR-LITE:\s*ANNIHILATION\s*-->",
        r"<!--\s*QCR-LITE:\s*ICE-9\s*-->",
        r"##\s*Darwinist Compaction\b",
        r"##\s*Annihilation Pass\b",
        r"##\s*Ice-9 Coherence Sweep\b",
    ]
    found = sum(1 for pattern in markers if re.search(pattern, report_text, re.MULTILINE | re.IGNORECASE))

    if found >= 2:
        return "PASS", f"Found {found} QCR-lite indicators"
    if found >= 1:
        return "WARN", f"Only {found} QCR-lite indicator (expected >= 2)"
    return "FAIL", "No QCR-lite markers or sections detected"


def check_synthesis(report_text: str) -> tuple[str, str]:
    """Check for Synthesis or Gamma Photons section with content."""
    match = re.search(
        r"^(##\s*(?:Synthesis|Gamma Photons)\b.*?)\n^(#{1,2}\s|\Z)",
        report_text,
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return "FAIL", "No ## Synthesis or ## Gamma Photons section found"

    section_text = match.group(1)
    line_count = len([l for l in section_text.split("\n") if l.strip()])
    if line_count < 3:
        return "FAIL", f"Synthesis section too short ({line_count} lines, min 3)"

    return "PASS", f"Synthesis section: {line_count} lines"


def check_ecp(report_text: str) -> tuple[str, str]:
    """Check Empirical Completion Proof + Deferred-and-Untested sections."""
    has_ecp = bool(re.search(r"^##\s*Empirical Completion Proof\b", report_text, re.MULTILINE | re.IGNORECASE))
    has_deferred = bool(re.search(r"^##\s*Deferred-and-Untested\b", report_text, re.MULTILINE | re.IGNORECASE))

    missing = []
    if not has_ecp:
        missing.append("Empirical Completion Proof")
    if not has_deferred:
        missing.append("Deferred-and-Untested")

    if missing:
        return "FAIL", f"Missing sections: {', '.join(missing)}"

    # Count how many legs are present
    legs = ["Trigger", "Effect", "Consumption"]
    leg_count = sum(
        1
        for leg in legs
        if re.search(rf"^\*\*Leg \d?\s*\(?{leg}\)?\*\*|^\*\*{leg}\*\*", report_text, re.MULTILINE | re.IGNORECASE)
    )

    if leg_count < 2:
        return "WARN", f"ECP present but only {leg_count}/3 legs detected"

    return "PASS", f"ECP + Deferred present, {leg_count}/3 legs"


def check_kairn(state_path: str | None, report_text: str) -> tuple[str, str]:
    """Check if Kairn learnings were persisted or engaged.

    Detection hierarchy (PASS > WARN > FAIL):
      PASS: state file shows kn_learn/kn_recall/kn_memories calls (best evidence)
      PASS: report text contains explicit Kairn tool calls (kn_* or mcp__kairn__*)
      PASS: loop-errors.log has a kairn-fail fallback entry (accepted fallback)
      WARN: report references Kairn node IDs (8-char hex codes) - engagement
            evidence but writes not directly verified
      FAIL: no Kairn evidence at all
    """
    # Tool-call regex: matches kn_learn, kn_recall, kn_memories, kn_context,
    # kn_query, kn_save, kn_idea, kn_log, kn_status, mcp__kairn__*, etc.
    tool_call_re = re.compile(r"\bkn_(?:learn|recall|memories|context|query|save|idea|log|status|connect|crossref|ideas|projects|project|prune|add|remove|related|promote_pending)\b|mcp__kairn__\w+", re.IGNORECASE)

    # 1. State file with actual tool calls (best evidence)
    if state_path and Path(state_path).exists():
        state_text = Path(state_path).read_text(encoding="utf-8")
        kn_calls = len(tool_call_re.findall(state_text))
        if kn_calls > 0:
            return "PASS", f"Found {kn_calls} Kairn call(s) in state file"

    # Strip fenced code blocks before scanning report text so example/template
    # snippets like ```kn_learn(...)``` do not falsely pass the gate.
    report_no_code = re.sub(r"```[\s\S]*?```", "", report_text)

    # 2. Report contains explicit tool calls (outside code blocks)
    kn_in_report = len(tool_call_re.findall(report_no_code))
    if kn_in_report > 0:
        return "PASS", f"Report shows {kn_in_report} explicit Kairn tool call(s)"

    # 3. Fallback log entry counts as accepted (kairn was unreachable but logged).
    # Use script-relative path so working directory does not affect detection.
    errors_path = Path(__file__).resolve().parent.parent / "loop-errors.log"
    if errors_path.exists():
        errors_text = errors_path.read_text(encoding="utf-8")
        if "kairn-fail" in errors_text[-5000:]:  # Last 5KB
            return "PASS", "Kairn fallback logged (accepted)"

    # 4. Node-ID references suggest engagement without verifiable writes (WARN).
    # Pattern: 8-char hex code preceded by backtick or whitespace. Require BOTH
    # >=2 node IDs AND >=2 'Kairn' word mentions to avoid commit-SHA false
    # positives. Strip code blocks so commit-SHA listings do not count.
    node_id_re = re.compile(r"[`\s]([0-9a-f]{8})\b")
    node_ids = node_id_re.findall(report_no_code)
    kairn_word_count = len(re.findall(r"\bKairn\b", report_no_code))
    if len(node_ids) >= 2 and kairn_word_count >= 2:
        return "WARN", f"Kairn referenced ({kairn_word_count}x word, {len(node_ids)} node IDs) but writes not directly verified"

    return "FAIL", "No Kairn calls detected and no fallback log entry"


def check_quality(report_path: str, mode: str) -> tuple[str, str]:
    """Invoke quality_gate_v2.py if available."""
    qg_script = Path("_autonomous/scripts/quality_gate_v2.py")
    if not qg_script.exists():
        return "WARN", "quality_gate_v2.py not found - skipping quality gate"

    # This is a placeholder - actual invocation would use subprocess
    # For now, we check if the report has quality markers
    report_text = Path(report_path).read_text(encoding="utf-8")

    has_citations = len(re.findall(r"https?://|@\w+|\[\w+\]", report_text)) >= 2
    has_gap_disclosure = bool(
        re.search(
            r"^##\s*(Deferred-and-Untested|Gaps|Open Questions|What This Does NOT Cover)\b",
            report_text,
            re.MULTILINE | re.IGNORECASE,
        )
    )

    if has_citations and has_gap_disclosure:
        return "PASS", "Quality markers present (citations + gap disclosure)"
    return "FAIL", f"Quality markers missing: citations={has_citations}, gap_disclosure={has_gap_disclosure}"


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-Run Gate Keeper")
    parser.add_argument("--report-path", required=True, help="Path to the report markdown file")
    parser.add_argument("--state-path", default=None, help="Path to the loop state file")
    parser.add_argument("--mode", default="premium", choices=["premium", "standard"], help="Quality tier")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be checked without enforcing")
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        result = {
            "run_id": report_path.stem,
            "overall": "FAIL",
            "gates": {"report-structure": {"status": "FAIL", "detail": f"Report not found: {args.report_path}"}},
            "missing_actions": ["report-structure"],
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        print(json.dumps(result, indent=2) if args.json else "FAIL: Report not found")
        return 1

    report_text = report_path.read_text(encoding="utf-8")

    results = {}

    # Run gates
    results["report-structure"] = check_report_structure(report_text)
    results["qcr-lite"] = check_qcr_lite(report_text)
    results["synthesis"] = check_synthesis(report_text)
    results["ecp"] = check_ecp(report_text)
    results["kairn"] = check_kairn(args.state_path, report_text)
    results["quality"] = check_quality(args.report_path, args.mode)

    # Determine overall status
    statuses = [r[0] for r in results.values()]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    missing_actions = [gate for gate, (status, _) in results.items() if status == "FAIL"]

    output = {
        "run_id": report_path.stem,
        "overall": overall,
        "gates": {gate: {"status": status, "detail": detail} for gate, (status, detail) in results.items()},
        "missing_actions": missing_actions,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Overall: {overall}")
        for gate, (status, detail) in results.items():
            icon = "PASS" if status == "PASS" else "WARN" if status == "WARN" else "FAIL"
            print(f"  [{icon}] {gate}: {detail}")
        if missing_actions:
            print(f"\nMissing actions: {', '.join(missing_actions)}")

    if args.dry_run:
        return 0

    return 0 if overall == "PASS" else 1 if overall == "FAIL" else 2


if __name__ == "__main__":
    sys.exit(main())
