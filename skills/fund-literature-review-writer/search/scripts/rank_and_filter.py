#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


MAX_PAPERS = 10
MAX_UNVERIFIED = 3
MIN_STRONG_PARTIAL = 5
STRONG_PARTIAL_THRESHOLD = 0.6
UNVERIFIED_THRESHOLD = 0.3


def rank_and_filter(papers: list[dict]) -> list[dict]:
    papers.sort(key=lambda p: p.get("composite_score") or 0, reverse=True)

    strong_partial = []
    background = []
    unverified = []

    for p in papers:
        score = p.get("support_score") or 0
        if score >= STRONG_PARTIAL_THRESHOLD:
            strong_partial.append(p)
        elif score >= UNVERIFIED_THRESHOLD:
            background.append(p)
        else:
            unverified.append(p)

    result = strong_partial[:MAX_PAPERS]
    remaining = MAX_PAPERS - len(result)
    if remaining > 0:
        result.extend(background[:remaining])
        remaining = MAX_PAPERS - len(result)
    if remaining > 0 and len(strong_partial) < MIN_STRONG_PARTIAL:
        result.extend(unverified[:min(remaining, MAX_UNVERIFIED)])

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank papers by composite_score and filter to top candidates"
    )
    parser.add_argument("--input", required=True, help="Path to claim JSON file")
    parser.add_argument("--output", default=None, help="Output file (default: overwrite --input in-place)")

    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            papers = json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1

    if not isinstance(papers, list):
        papers = [papers]

    before = len(papers)
    filtered = rank_and_filter(papers)
    after = len(filtered)

    unverified_count = sum(1 for p in filtered if (p.get("support_score") or 0) < UNVERIFIED_THRESHOLD)

    target = args.output or args.input
    with open(target, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"Filtered: {before} → {after} papers (unverified: {unverified_count})", file=sys.stderr)
    print(f"Written to {target}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
