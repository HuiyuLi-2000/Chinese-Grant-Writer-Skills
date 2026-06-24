#!/usr/bin/env python3
"""
Exa Search for citation-finder.
Searches via exa-py SDK and converts results to
citation-finder unified data structure (JSON array).

Requires: pip install exa-py
Requires: EXA_API_KEY in skill directory .env file

Usage
-----
python scripts/exa_search.py search "{query}" --max 10 --category "research paper"
python scripts/exa_search.py search "{query}" --include-domains "arxiv.org,doi.org,openalex.org"
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_INSTALL_MESSAGE = "exa-py not found. Install it with: pip install exa-py"


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _get_client() -> Any:
    try:
        from exa_py import Exa
    except ImportError:
        raise RuntimeError(_INSTALL_MESSAGE)
    _load_dotenv()
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "EXA_API_KEY not found. "
            "Set it in the skill directory .env file: EXA_API_KEY=your_key\n"
            "Get your key from: https://exa.ai"
        )
    return Exa(api_key=api_key)


def _parse_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _extract_doi(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"doi\.org/(.+)", url)
    return m.group(1).strip() if m else None


def _parse_year(published_date: str | None) -> int | None:
    if not published_date:
        return None
    m = re.match(r"(\d{4})", published_date)
    return int(m.group(1)) if m else None


def _to_unified(result: Any, content_mode: str) -> dict[str, Any]:
    """Convert a single Exa result object to citation-finder unified structure."""
    title = getattr(result, "title", None) or ""
    url = getattr(result, "url", None) or ""
    published_date = getattr(result, "published_date", None)
    author_raw = getattr(result, "author", None)

    doi = _extract_doi(url)
    year = _parse_year(published_date)

    # author field from Exa is typically a single string, not a list
    authors = []
    if author_raw:
        for name in str(author_raw).split(","):
            name = name.strip()
            if name:
                parts = name.split()
                if len(parts) >= 2:
                    authors.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
                else:
                    authors.append(name)

    # build abstract from highlights or text or summary
    abstract = ""
    if content_mode == "highlights":
        highlights = getattr(result, "highlights", None)
        if highlights:
            abstract = " ... ".join(highlights)
    elif content_mode == "text":
        text = getattr(result, "text", None)
        if text:
            abstract = text[:2000]
    elif content_mode == "summary":
        summary = getattr(result, "summary", None)
        if summary:
            abstract = summary

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi,
        "venue": "",
        "venue_type": "other",
        "issn_l": None,
        "issn": [],
        "volume": None,
        "issue": None,
        "pages": None,
        "publisher": None,
        "abstract": abstract,
        "citation_count": 0,
        "url": url or None,
        "open_access_pdf": None,
        "is_oa": False,
        "oa_status": None,
        "language": None,
        "keywords": [],
        "source_layer": "web",
        "source": "exa",
        "tier_score": 0.0,
        "recency_score": 0.0,
        "support_score": None,
        "composite_score": None,
    }


def search_exa(
    query: str,
    max_results: int = 10,
    search_type: str = "auto",
    content_mode: str = "highlights",
    max_chars: int = 4000,
    category: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    client = _get_client()

    content_kwargs: dict[str, Any] = {}
    if content_mode == "highlights":
        content_kwargs = {"highlights": {"max_characters": max_chars}}
    elif content_mode == "text":
        content_kwargs = {"text": {"max_characters": max_chars}}
    elif content_mode == "summary":
        content_kwargs = {"summary": True}

    kwargs: dict[str, Any] = {
        "query": query,
        "num_results": max_results,
        "type": search_type,
        **content_kwargs,
    }
    if category:
        kwargs["category"] = category
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if start_date:
        kwargs["start_published_date"] = start_date
    if end_date:
        kwargs["end_published_date"] = end_date

    response = client.search_and_contents(**kwargs)
    return [_to_unified(r, content_mode) for r in response.results]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exa search, output citation-finder unified JSON"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp = subparsers.add_parser("search", help="Search via Exa")
    sp.add_argument("query", help="Search query")
    sp.add_argument("--max", type=int, default=10, metavar="N")
    sp.add_argument("--type", default="auto", dest="search_type",
                    choices=("auto", "neural", "fast", "instant"))
    sp.add_argument("--content", default="highlights", dest="content_mode",
                    choices=("highlights", "text", "summary", "none"))
    sp.add_argument("--max-chars", type=int, default=4000)
    sp.add_argument("--category", default=None)
    sp.add_argument("--include-domains", default=None)
    sp.add_argument("--exclude-domains", default=None)
    sp.add_argument("--start-date", default=None)
    sp.add_argument("--end-date", default=None)
    sp.add_argument("--output", "-o", default=None)

    args = parser.parse_args()

    try:
        results = search_exa(
            query=args.query,
            max_results=args.max,
            search_type=args.search_type,
            content_mode=args.content_mode,
            max_chars=args.max_chars,
            category=args.category,
            include_domains=_parse_list(args.include_domains),
            exclude_domains=_parse_list(args.exclude_domains),
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(results)} results to {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
