#!/usr/bin/env python3
"""
Quality Gate v2 - Premium Rubric Scorer

Computes 5 premium-quality metrics on a markdown research report:
1. Citation Density (URLs + bracket citations) - >= 1 per 200 words
2. DSV Evidence Count (Validate-by, Reasoning, Decompose/Suspend/Validate) - >= 1 per 200 words
3. Gap Disclosure Section presence (## Deferred-and-Untested / ## Gaps / etc.)
4. Empirical Completion Proof 3-leg section (header + 2 of 3 legs: Trigger/Effect/Consumption)
5. Cross-Track Convergence Count (multi-track reports only) - >= 2 convergences;
   single-track reports auto-pass this metric.

Tier Contract:
- Premium: 5/5 pass
- Standard: 3-4/5 pass
- Reject: < 3 pass

Performance: < 2s on 1000-line markdown.

Usage:
    python3 quality_gate_v2.py <report_path>
    python3 quality_gate_v2.py --json <report_path>

Exit codes:
    0 = premium
    1 = standard
    2 = reject (or error)

License: MIT (claude-adaptive-research)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


URL_PATTERN = re.compile(r"https?://[^\s\)\]]+")

CITATION_BRACKET_PATTERN = re.compile(
    r"\[\d+\]"
    r"|\(20\d\d[a-z]?\)"
    r"|et al\.,?\s*20\d\d"
    r"|\b\w+\s+(?:&|and)\s+\w+,?\s*20\d\d"
    r"|\b[A-Z][a-z]+\s+20\d\d\b"
    r"|\bp\.\s*\d+"
    r"|\bSection\s+\d+\.\d+"
    r"|§\s*\d+\.\d+"
    r"|\bDOI:\s*\S+"
    r"|\bIEC\s+\d+"
    r"|\bDNV[\s\-]\S+"
    r"|\bISO\s+\d+"
    r"|`[a-f0-9]{8}`"
    r"|\b\d{4}-\d{2}-\d{2}-\S+\.md\b",
    re.IGNORECASE,
)

DSV_EVIDENCE_PATTERN = re.compile(
    r"\bVALIDATE BY:"
    r"|\bWhy:"
    r"|\bReasoning:"
    r"|\bDSV\b"
    r"|\bD-Pulse:"
    r"|\bS-Pulse:"
    r"|\bS-Pulse\b"
    r"|\bV-Pulse:"
    r"|\bDecompose:"
    r"|\bDecompose\*\*"
    r"|\bSuspend:"
    r"|\bSuspend\*\*"
    r"|\bValidate:"
    r"|\bValidate\*\*"
    r"|\bIMPACT IF WRONG:"
    r"|\bAssumption:"
    r"|\bAssumption\b\s*-"
    r"|\bDSV check"
    r"|\bAlternative interpretation"
    r"|\bMutation interpretation"
    r"|\bSelf-falsif"
    r"|\bCounter-evidence",
    re.IGNORECASE | re.MULTILINE,
)

GAP_HEADER_PATTERN = re.compile(
    r"^#+\s*"
    r"(?:\d+(?:\.\d+)?\.?\s+)?"
    r"(Deferred[\s\-]and[\s\-]Untested"
    r"|Gaps?\b"
    r"|What\s+This(?:\s+\w+)?\s+Does\s+NOT\s+Cover"
    r"|What\s+I\s+Did\s+NOT"
    r"|Honest\s+Gaps?"
    r"|Honest\s+Weakness"
    r"|Open\s+Questions?"
    r"|Limitations?"
    r"|Caveats?"
    r"|Identified\s+Gap"
    r"|Out\s+of\s+Scope"
    r"|NOT[\s\-]Scope)\b",
    re.IGNORECASE | re.MULTILINE,
)

ECP_HEADER_PATTERN = re.compile(
    r"^#+\s*"
    r"(?:\d+(?:\.\d+)?\.?\s+)?"
    r"(Empirical\s+Completion\s+Proof"
    r"|ECP"
    r"|3-Leg\s+(?:Verification|Proof))\b",
    re.IGNORECASE | re.MULTILINE,
)

ECP_LEG_PATTERNS = {
    "trigger": re.compile(r"\bLeg\s*1[\s\(:]|\*\*Trigger\*\*|\bTrigger:", re.IGNORECASE),
    "effect": re.compile(r"\bLeg\s*2[\s\(:]|\*\*Effect\*\*|\bEffect:", re.IGNORECASE),
    "consumption": re.compile(
        r"\bLeg\s*3[\s\(:]|\*\*Consumption\*\*|\bConsumption:|\bConsumer:",
        re.IGNORECASE,
    ),
}

CONVERGENCE_HEADER_PATTERN = re.compile(
    r"^#+\s*Convergence\s*(\d+|[A-Z]):", re.IGNORECASE | re.MULTILINE
)

TRACK_KEYWORD_PATTERN = re.compile(
    r"\bTrack\s+[A-Z]\b" r"|\bmulti-track\b" r"|\b[2-9]\s*tracks?\b",
    re.IGNORECASE,
)


YAML_FRONT_MATTER_PATTERN = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
CODE_FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)


def strip_non_prose(text: str) -> str:
    """Remove YAML front matter and fenced code blocks before word counting."""
    text = YAML_FRONT_MATTER_PATTERN.sub("", text, count=1)
    text = CODE_FENCE_PATTERN.sub("", text)
    return text


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", strip_non_prose(text)))


def metric_citation_density(text: str, word_count: int) -> Dict[str, Any]:
    urls = len(URL_PATTERN.findall(text))
    citations = len(CITATION_BRACKET_PATTERN.findall(text))
    total = urls + citations
    density = total / max(word_count / 200, 1.0)
    return {
        "name": "citation_density",
        "value": round(density, 2),
        "urls": urls,
        "citations": citations,
        "threshold": 1.0,
        "pass": density >= 1.0,
    }


def metric_dsv_evidence(text: str, word_count: int) -> Dict[str, Any]:
    matches = len(DSV_EVIDENCE_PATTERN.findall(text))
    density = matches / max(word_count / 200, 1.0)
    return {
        "name": "dsv_evidence",
        "value": round(density, 2),
        "matches": matches,
        "threshold": 1.0,
        "pass": density >= 1.0,
    }


def metric_gap_disclosure(text: str) -> Dict[str, Any]:
    match = GAP_HEADER_PATTERN.search(text)
    return {
        "name": "gap_disclosure",
        "present": match is not None,
        "matched_header": match.group(0).strip() if match else None,
        "pass": match is not None,
    }


def metric_ecp_section(text: str) -> Dict[str, Any]:
    header_match = ECP_HEADER_PATTERN.search(text)
    if header_match is None:
        return {
            "name": "ecp_section",
            "header_present": False,
            "legs_found": {leg: False for leg in ECP_LEG_PATTERNS},
            "legs_count": 0,
            "threshold_legs": 2,
            "pass": False,
        }
    line_start = text.rfind("\n", 0, header_match.start()) + 1
    line_end = text.find("\n", header_match.start())
    if line_end == -1:
        line_end = len(text)
    header_line = text[line_start:line_end]
    hash_match = re.match(r"^#+", header_line)
    hash_count = len(hash_match.group(0)) if hash_match else 2
    same_or_higher_pattern = re.compile(
        r"^#{1," + str(hash_count) + r"}\s", re.MULTILINE
    )
    next_section = same_or_higher_pattern.search(text[header_match.end():])
    if next_section:
        ecp_body = text[header_match.end():header_match.end() + next_section.start()]
    else:
        ecp_body = text[header_match.end():]
    legs_found = {leg: bool(p.search(ecp_body)) for leg, p in ECP_LEG_PATTERNS.items()}
    legs_count = sum(legs_found.values())
    return {
        "name": "ecp_section",
        "header_present": True,
        "header_level": hash_count,
        "legs_found": legs_found,
        "legs_count": legs_count,
        "threshold_legs": 2,
        "pass": legs_count >= 2,
    }


def metric_cross_track_convergence(text: str) -> Dict[str, Any]:
    distinct_tracks = set(re.findall(r"\bTrack\s+([A-Z])\b", text))
    has_multitrack_keyword = bool(
        re.search(r"\bmulti-track\b|\b[2-9]\s*tracks?\b", text, re.IGNORECASE)
    )
    convergence_count = len(CONVERGENCE_HEADER_PATTERN.findall(text))
    is_multi_track = (
        len(distinct_tracks) >= 2
        or has_multitrack_keyword
        or convergence_count >= 1
    )
    if not is_multi_track:
        return {
            "name": "cross_track_convergence",
            "multi_track": False,
            "count": 0,
            "pass": True,
            "note": "N/A (single-track report)",
        }
    return {
        "name": "cross_track_convergence",
        "multi_track": True,
        "distinct_tracks": sorted(distinct_tracks),
        "count": convergence_count,
        "threshold": 2,
        "pass": convergence_count >= 2,
    }


def compute_tier(metrics: List[Dict[str, Any]]) -> str:
    total = len(metrics)
    passed = sum(1 for m in metrics if m["pass"])
    if passed == total:
        return "premium"
    if passed >= max(3, total - 2):
        return "standard"
    return "reject"


def score_report(report_path: str) -> Dict[str, Any]:
    path = Path(report_path)
    if not path.exists():
        return {"error": f"Report not found: {report_path}"}
    text = path.read_text(encoding="utf-8")
    word_count = count_words(text)
    metrics = [
        metric_citation_density(text, word_count),
        metric_dsv_evidence(text, word_count),
        metric_gap_disclosure(text),
        metric_ecp_section(text),
        metric_cross_track_convergence(text),
    ]
    passed_count = sum(1 for m in metrics if m["pass"])
    return {
        "report_path": str(path),
        "word_count": word_count,
        "metrics": metrics,
        "passed": passed_count,
        "total": 5,
        "tier": compute_tier(metrics),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-Run v2 Quality Gate")
    parser.add_argument("report_path", help="Path to markdown report")
    parser.add_argument(
        "--output-json",
        "--json",
        dest="output_json",
        action="store_true",
        help="Output JSON instead of human-readable",
    )
    args = parser.parse_args()

    result = score_report(args.report_path)
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        return 2

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Quality Gate v2 Report: {result['report_path']}")
        print(f"Word count: {result['word_count']}")
        print(
            f"Tier: {result['tier'].upper()} "
            f"({result['passed']}/{result['total']} metrics passed)"
        )
        print()
        for m in result["metrics"]:
            status = "PASS" if m["pass"] else "FAIL"
            details = ""
            if m["name"] == "citation_density":
                details = (
                    f"density={m['value']} "
                    f"(urls={m['urls']}, citations={m['citations']})"
                )
            elif m["name"] == "dsv_evidence":
                details = f"density={m['value']} (matches={m['matches']})"
            elif m["name"] == "gap_disclosure":
                details = f"header={m['matched_header']}"
            elif m["name"] == "ecp_section":
                details = (
                    f"header={m['header_present']}, legs={m['legs_count']}/3"
                )
            elif m["name"] == "cross_track_convergence":
                if not m.get("multi_track"):
                    details = m["note"]
                else:
                    details = f"count={m['count']}"
            print(f"  [{status}] {m['name']}: {details}")

    if result["tier"] == "premium":
        return 0
    if result["tier"] == "standard":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
