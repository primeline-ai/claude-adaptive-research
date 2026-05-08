#!/usr/bin/env python3
"""
Cross-Track Findings Aggregator

Reads per-track findings from {cache_root}/cross-track-{run_id}/ and detects
convergence across tracks by keyword overlap (Jaccard >= 0.5) using
Union-Find clustering. Writes a ## Cross-Track Synthesis markdown section
atomically to the specified output path.

File layout expected (one file per track):
    {cache_root}/cross-track-{run_id}/track-A.json  -> list of finding objects
    {cache_root}/cross-track-{run_id}/track-B.json  -> list of finding objects

Each finding object must conform to schemas/cross_track_findings_schema.json.

Default cache root: ./_autonomous/cross-track-cache/
Override via --cache-root CLI arg or CROSS_TRACK_CACHE_ROOT env var.

Usage (CLI):
    python3 cross_track_aggregator.py <run_id> <output_path> [--cache-root PATH]

License: MIT (claude-adaptive-research)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s [cross_track_aggregator] %(message)s",
)
logger = logging.getLogger(__name__)

def _resolve_default_cache_root() -> Path:
    env_override = os.environ.get("CROSS_TRACK_CACHE_ROOT")
    if env_override:
        return Path(env_override).expanduser()
    cwd_default = Path.cwd() / "_autonomous" / "cross-track-cache"
    return cwd_default


_DEFAULT_CACHE_ROOT = _resolve_default_cache_root()

JACCARD_THRESHOLD = 0.5
MIN_TRACKS_FOR_CONVERGENCE = 2

_STOP_WORDS: FrozenSet[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "in", "on",
    "at", "to", "for", "of", "with", "by", "from", "up", "out", "if",
    "it", "its", "this", "that", "these", "those", "and", "or", "but",
    "not", "as", "i", "my", "mine", "we", "our", "us", "they", "them",
    "their", "he", "she", "his", "her", "you", "your", "than", "into",
    "also", "which", "when", "where", "who", "what", "how", "all", "each",
    "any", "more", "most", "other", "such", "so", "about", "after",
    "before", "between", "through", "both", "then", "now", "just", "via",
    "per", "new", "use", "used", "using", "see", "get", "set", "run",
    "runs", "add", "adds", "one", "two", "three", "four", "five",
    "across", "within", "without", "only", "same", "different",
})

_MIN_WORD_LEN = 3


@dataclass
class Convergence:
    convergence_id: int
    tracks: List[str]
    anchor_finding_id: str
    anchor_content: str
    member_finding_ids: List[str]
    concept_keywords: List[str]
    member_count: int


def _tokenize(text: str) -> FrozenSet[str]:
    words = re.findall(r"\b[a-z]{%d,}\b" % _MIN_WORD_LEN, text.lower())
    return frozenset(w for w in words if w not in _STOP_WORDS)


def _jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    if not a and not b:
        return 1.0
    union_size = len(a | b)
    if union_size == 0:
        return 0.0
    return len(a & b) / union_size


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        px, py = self.find(x), self.find(y)
        if px != py:
            self._parent[px] = py


def _finding_dir(run_id: str, cache_root: Path) -> Path:
    return cache_root / f"cross-track-{run_id}"


def read_track_findings(
    run_id: str,
    cache_root: Optional[Path] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    root = cache_root if cache_root is not None else _DEFAULT_CACHE_ROOT
    findings_dir = _finding_dir(run_id, root)

    if not findings_dir.exists():
        return {}

    result: Dict[str, List[Dict[str, Any]]] = {}

    for track_file in sorted(findings_dir.glob("track-*.json")):
        stem = track_file.stem
        parts = stem.split("-", 1)
        if len(parts) != 2 or not parts[1]:
            continue
        track_id = parts[1]
        if not re.match(r"^[A-Z]$", track_id):
            continue

        raw = track_file.read_text(encoding="utf-8").strip()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            warnings.warn(
                f"Malformed JSON in {track_file} (skipping): {exc}",
                stacklevel=2,
            )
            continue

        if not isinstance(data, list):
            warnings.warn(
                f"Expected JSON array in {track_file}, got {type(data).__name__} (skipping)",
                stacklevel=2,
            )
            continue

        valid_findings: List[Dict[str, Any]] = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            if "content" not in item:
                continue
            valid_findings.append(item)

        if valid_findings:
            result[track_id] = valid_findings

    return result


def detect_convergence(
    findings_by_track: Dict[str, List[Dict[str, Any]]],
) -> List[Convergence]:
    if len(findings_by_track) < MIN_TRACKS_FOR_CONVERGENCE:
        return []

    items: List[Tuple[str, Dict[str, Any]]] = []
    for track_id in sorted(findings_by_track):
        for finding in findings_by_track[track_id]:
            items.append((track_id, finding))

    n = len(items)
    if n == 0:
        return []

    tokens: List[FrozenSet[str]] = [
        _tokenize(item[1].get("content", "")) for item in items
    ]

    uf = _UnionFind(n)
    for i in range(n):
        for j in range(i + 1, n):
            track_i, _ = items[i]
            track_j, _ = items[j]
            if track_i == track_j:
                continue
            if _jaccard(tokens[i], tokens[j]) >= JACCARD_THRESHOLD:
                uf.union(i, j)

    clusters: Dict[int, List[int]] = defaultdict(list)
    for idx in range(n):
        clusters[uf.find(idx)].append(idx)

    convergences: List[Convergence] = []
    conv_id = 1

    for root, members in sorted(clusters.items()):
        track_ids_in_cluster = {items[idx][0] for idx in members}
        if len(track_ids_in_cluster) < MIN_TRACKS_FOR_CONVERGENCE:
            continue

        union_of_all = frozenset().union(*[tokens[idx] for idx in members])
        best_idx = max(members, key=lambda idx: len(tokens[idx] & union_of_all))
        anchor_finding = items[best_idx][1]
        anchor_content = anchor_finding.get("content", "")

        keyword_track_presence: Dict[str, set] = {}
        for idx in members:
            t_id = items[idx][0]
            for kw in tokens[idx]:
                if kw not in keyword_track_presence:
                    keyword_track_presence[kw] = set()
                keyword_track_presence[kw].add(t_id)

        concept_keywords = [
            kw
            for kw, tracks_set in keyword_track_presence.items()
            if len(tracks_set) >= 2
        ]
        concept_keywords.sort(key=lambda kw: (-len(keyword_track_presence[kw]), kw))
        concept_keywords = concept_keywords[:10]

        member_finding_ids = [
            items[idx][1].get("finding_id", f"idx-{idx}") for idx in members
        ]

        convergences.append(
            Convergence(
                convergence_id=conv_id,
                tracks=sorted(track_ids_in_cluster),
                anchor_finding_id=anchor_finding.get("finding_id", f"idx-{best_idx}"),
                anchor_content=anchor_content,
                member_finding_ids=sorted(set(member_finding_ids)),
                concept_keywords=concept_keywords,
                member_count=len(members),
            )
        )
        conv_id += 1

    return convergences


def write_aggregate_synthesis(
    run_id: str,
    output_path,
    cache_root: Optional[Path] = None,
) -> Dict[str, Any]:
    root = cache_root if cache_root is not None else _DEFAULT_CACHE_ROOT
    findings_by_track = read_track_findings(run_id, root)

    tracks_read = sorted(findings_by_track.keys())
    findings_total = sum(len(v) for v in findings_by_track.values())

    convergences = detect_convergence(findings_by_track)

    lines: List[str] = [
        "## Cross-Track Synthesis",
        "",
        f"**Run**: {run_id}  ",
        f"**Tracks analysed**: {', '.join(tracks_read) if tracks_read else 'none'}  ",
        f"**Total findings**: {findings_total}  ",
        f"**Convergences detected**: {len(convergences)}",
        "",
    ]

    if not convergences:
        if len(findings_by_track) < MIN_TRACKS_FOR_CONVERGENCE:
            lines.append(
                f"_No cross-track convergence analysis: fewer than "
                f"{MIN_TRACKS_FOR_CONVERGENCE} tracks present._"
            )
        else:
            lines.append(
                f"_No convergence detected: no two findings from different tracks "
                f"share Jaccard keyword overlap >= {JACCARD_THRESHOLD}._"
            )
    else:
        for conv in convergences:
            lines.extend([
                f"### Convergence {conv.convergence_id}: "
                + (", ".join(conv.concept_keywords[:5]) if conv.concept_keywords else "cross-track concept"),
                "",
                f"**Tracks**: {', '.join(conv.tracks)}  ",
                f"**Findings in cluster**: {conv.member_count}  ",
                f"**Shared keywords**: {', '.join(conv.concept_keywords) if conv.concept_keywords else 'n/a'}",
                "",
                f"> {conv.anchor_content}",
                "",
                f"_Anchor finding ID_: `{conv.anchor_finding_id}`  ",
                f"_All finding IDs_: {', '.join(f'`{fid}`' for fid in conv.member_finding_ids)}",
                "",
            ])

    output = "\n".join(lines) + "\n"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        tmp_path.write_text(output, encoding="utf-8")
        os.replace(str(tmp_path), str(output_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return {
        "run_id": run_id,
        "tracks_read": tracks_read,
        "findings_total": findings_total,
        "convergences_found": len(convergences),
        "output_path": str(output_path),
    }


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross-track findings aggregator for Auto-Run v2."
    )
    parser.add_argument("run_id", help="Auto-run identifier")
    parser.add_argument("output_path", help="Path to write synthesis markdown")
    parser.add_argument("--cache-root", default=None, help="Override cache root")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    cache_root = Path(args.cache_root) if args.cache_root else None
    summary = write_aggregate_synthesis(args.run_id, args.output_path, cache_root)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Run: {summary['run_id']}")
        print(f"Tracks read: {', '.join(summary['tracks_read']) or 'none'}")
        print(f"Findings total: {summary['findings_total']}")
        print(f"Convergences found: {summary['convergences_found']}")
        print(f"Output: {summary['output_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(_main())
