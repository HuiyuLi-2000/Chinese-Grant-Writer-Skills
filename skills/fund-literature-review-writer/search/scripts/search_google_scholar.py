#!/usr/bin/env python3
"""
Google Scholar search for citation-finder.
Outputs results in citation-finder unified data structure (JSON).

Requires: pip install scholarly
Optional:  --use-proxy  (free proxies, reduces ban risk)
"""

import argparse
import json
import random
import sys
import time

try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False


def _normalize_authors(raw_authors):
    """Convert scholarly author list to 'Last, First' format."""
    result = []
    for name in raw_authors:
        name = name.strip()
        if not name:
            continue
        parts = name.split()
        if len(parts) >= 2:
            result.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
        else:
            result.append(name)
    return result


def _to_unified(item):
    """Map a scholarly result dict to citation-finder unified data structure."""
    bib = item.get("bib", {})
    title = bib.get("title", "")
    raw_authors = bib.get("author", [])
    authors = _normalize_authors(raw_authors) if isinstance(raw_authors, list) else []
    year_raw = bib.get("pub_year", None)
    try:
        year = int(year_raw) if year_raw else None
    except (ValueError, TypeError):
        year = None
    venue = bib.get("venue", "") or ""
    abstract = bib.get("abstract", "") or ""
    citation_count = item.get("num_citations", 0) or 0
    url = item.get("pub_url", "") or item.get("eprint_url", "") or ""
    doi = None
    if url and "doi.org/" in url:
        doi = url.split("doi.org/")[-1].strip()

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi,
        "venue": venue,
        "venue_type": "other",
        "issn_l": None,
        "issn": [],
        "volume": None,
        "issue": None,
        "pages": None,
        "publisher": None,
        "abstract": abstract,
        "citation_count": citation_count,
        "url": url or None,
        "open_access_pdf": item.get("eprint_url") or None,
        "is_oa": bool(item.get("eprint_url")),
        "oa_status": None,
        "language": None,
        "keywords": [],
        "source_layer": "web",
        "source": "google_scholar",
        "tier_score": 0.0,
        "recency_score": 0.0,
        "support_score": None,
        "composite_score": None,
    }


def search_google_scholar(query, limit=20, year_start=None, year_end=None,
                          sort_by="relevance", use_proxy=False):
    if not SCHOLARLY_AVAILABLE:
        print("Error: scholarly not installed. Run: pip install scholarly", file=sys.stderr)
        return []

    if use_proxy:
        try:
            pg = ProxyGenerator()
            pg.FreeProxies()
            scholarly.use_proxy(pg)
            print("Using free proxy", file=sys.stderr)
        except Exception as e:
            print(f"Warning: proxy setup failed: {e}", file=sys.stderr)

    print(f"Searching Google Scholar: {query}", file=sys.stderr)
    results = []
    try:
        search_gen = scholarly.search_pubs(query)
        for i, item in enumerate(search_gen):
            if len(results) >= limit:
                break
            unified = _to_unified(item)
            # year filter
            if year_start or year_end:
                y = unified.get("year")
                if y:
                    if year_start and y < year_start:
                        continue
                    if year_end and y > year_end:
                        continue
            results.append(unified)
            print(f"  [{len(results)}/{limit}] {unified['title'][:80]}", file=sys.stderr)
            time.sleep(random.uniform(2, 5))
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)

    if sort_by == "citations":
        results.sort(key=lambda x: x.get("citation_count", 0) or 0, reverse=True)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Search Google Scholar, output citation-finder unified JSON"
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parser.add_argument("--year-start", type=int, default=None)
    parser.add_argument("--year-end", type=int, default=None)
    parser.add_argument("--sort-by", choices=["relevance", "citations"], default="relevance")
    parser.add_argument("--use-proxy", action="store_true", help="Use free proxy")
    parser.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")
    args = parser.parse_args()

    if not SCHOLARLY_AVAILABLE:
        print("scholarly not installed. Run: pip install scholarly", file=sys.stderr)
        sys.exit(1)

    results = search_google_scholar(
        query=args.query,
        limit=args.limit,
        year_start=args.year_start,
        year_end=args.year_end,
        sort_by=args.sort_by,
        use_proxy=args.use_proxy,
    )

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(results)} results to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
