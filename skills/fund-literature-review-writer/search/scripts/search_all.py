#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from citation_finder import (
    search as api_search,
    year_normalize,
    search_openalex,
    search_crossref,
    lookup_by_doi,
    lookup_by_title,
    lookup_crossref_by_doi,
    lookup_crossref_by_title,
    batch_lookup_by_dois,
)
from dedup import deduplicate
from exa_search import search_exa
from search_google_scholar import search_google_scholar

try:
    from tier_utils import compute_paper_tier_score, filter_blacklisted
    _TIER_AVAILABLE = True
except ImportError:
    _TIER_AVAILABLE = False


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


_load_dotenv()


def _enrich_tiers(papers: list[dict], email: str | None = None) -> list[dict]:
    if not _TIER_AVAILABLE:
        return papers
    for paper in papers:
        if paper.get("tier_score", 0) > 0:
            continue
        paper["tier_score"] = round(compute_paper_tier_score(paper, mailto=email), 4)
        paper["recency_score"] = round(year_normalize(paper.get("year")), 4)

    for paper in papers:
        if paper.get("support_score") is not None and paper.get("composite_score") is None:
            tier = paper.get("tier_score", 0) or 0
            recency = paper.get("recency_score", 0) or 0
            support = paper.get("support_score", 0) or 0
            paper["composite_score"] = round(tier * 0.3 + support * 0.3 + recency * 0.4, 4)

    return papers


# ---------- P0: metadata enrichment helpers ----------

_ENRICHABLE_FIELDS = (
    "doi", "authors", "venue", "venue_type", "abstract",
    "issn_l", "issn", "volume", "issue", "pages", "publisher",
    "citation_count", "url", "open_access_pdf", "is_oa", "oa_status",
    "language", "keywords",
)


def _is_empty(val, field=None):
    """Check if a field value is considered empty/default."""
    if val is None:
        return True
    if isinstance(val, str):
        if val == "":
            return True
        if field == "venue_type" and val == "other":
            return True
        return False
    if isinstance(val, list):
        return len(val) == 0
    return False


def _fill_missing(paper, lookup_result):
    """Fill missing fields in paper from lookup_result. Only overwrites empty/default values."""
    for field in _ENRICHABLE_FIELDS:
        old_val = paper.get(field)
        new_val = lookup_result.get(field)

        if field == "citation_count":
            paper[field] = max(old_val or 0, new_val or 0)
            continue

        if _is_empty(old_val, field) and not _is_empty(new_val, field):
            paper[field] = new_val

    enriched_from = paper.get("_enriched_from", [])
    source = lookup_result.get("source", "")
    if source and source not in enriched_from:
        enriched_from.append(source)
        paper["_enriched_from"] = enriched_from


def _titles_match(title1, title2):
    """Check if two titles refer to the same paper after normalization."""
    n1 = re.sub(r"[^a-z0-9]", "", (title1 or "").lower())
    n2 = re.sub(r"[^a-z0-9]", "", (title2 or "").lower())
    return bool(n1) and bool(n2) and n1 == n2


def _still_sparse(paper):
    """Check if a paper still has too many missing key fields after enrichment."""
    key_fields = ["doi", "abstract", "venue", "authors"]
    missing = sum(1 for f in key_fields if _is_empty(paper.get(f), f))
    return missing >= 2


def _enrich_metadata(papers, email=None):
    """Enrich web-layer papers with metadata from OpenAlex/Crossref."""
    if email is None:
        email = os.getenv("OPENALEX_EMAIL")

    web_papers = [p for p in papers if p.get("source_layer") in ("web", "local")]
    if not web_papers:
        return papers

    print(f"  Enriching metadata for {len(web_papers)} web/local-layer papers", file=sys.stderr)

    # Round 1: Papers with DOI → batch OpenAlex lookup
    doi_map = {}
    for p in web_papers:
        doi = (p.get("doi") or "").strip()
        if doi:
            doi_map[doi] = p

    # Track papers that still need enrichment after DOI-based lookup
    needs_title_search = []

    if doi_map:
        oa_batch = batch_lookup_by_dois(list(doi_map.keys()), mailto=email)
        enriched_dois = set()
        for doi, oa_result in oa_batch.items():
            if doi in doi_map:
                _fill_missing(doi_map[doi], oa_result)
                enriched_dois.add(doi)

        # Fallback: Crossref DOI lookup for papers not enriched by OpenAlex
        for doi, paper in doi_map.items():
            if doi not in enriched_dois or _still_sparse(paper):
                try:
                    cr_result = lookup_crossref_by_doi(doi, mailto=email)
                    if cr_result:
                        _fill_missing(paper, cr_result)
                except Exception:
                    pass

        # Papers with DOI that are still sparse → try title search
        for doi, paper in doi_map.items():
            if _still_sparse(paper) and paper.get("title"):
                needs_title_search.append(paper)

    # Round 2: Papers without DOI (or DOI lookup failed) → OpenAlex title search
    no_doi = [p for p in web_papers if not (p.get("doi") or "").strip() and p.get("title")]
    title_search_candidates = no_doi + needs_title_search
    still_missing = []
    for paper in title_search_candidates:
        oa_result = lookup_by_title(paper["title"], mailto=email)
        if oa_result and _titles_match(paper["title"], oa_result.get("title", "")):
            _fill_missing(paper, oa_result)
        else:
            still_missing.append(paper)

    # Fallback: Crossref title search
    for paper in still_missing:
        try:
            cr_result = lookup_crossref_by_title(paper["title"], mailto=email)
            if cr_result and _titles_match(paper["title"], cr_result.get("title", "")):
                _fill_missing(paper, cr_result)
        except Exception:
            pass

    enriched_count = sum(1 for p in web_papers if p.get("_enriched_from"))
    print(f"  Enriched {enriched_count}/{len(web_papers)} web/local-layer papers", file=sys.stderr)

    return papers


# ---------- main search pipeline ----------

def search_all(
    query: str,
    limit: int = 10,
    year_from: int | None = None,
    email: str | None = None,
    use_proxy: bool = False,
) -> list[dict]:
    if email is None:
        email = os.getenv("OPENALEX_EMAIL")
    all_results: list[dict] = []
    errors: list[str] = []

    def _run_openalex():
        try:
            return search_openalex(query, year_from=year_from, limit=limit, mailto=email)
        except Exception as e:
            errors.append(f"OpenAlex: {e}")
            return []

    def _run_crossref():
        try:
            return search_crossref(query, year_from=year_from, limit=limit, mailto=email)
        except Exception as e:
            errors.append(f"Crossref: {e}")
            return []

    def _run_exa():
        try:
            return search_exa(query=query, max_results=limit, category="research paper")
        except Exception as e:
            errors.append(f"Exa: {e}")
            return []

    def _run_scholar():
        try:
            return search_google_scholar(
                query=query, limit=limit, year_start=year_from,
                sort_by="relevance", use_proxy=use_proxy,
            )
        except Exception as e:
            errors.append(f"GoogleScholar: {e}")
            return []

    tasks = {
        "openalex": _run_openalex,
        "crossref": _run_crossref,
        "exa": _run_exa,
        "scholar": _run_scholar,
    }

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                count = len(result) if result else 0
                print(f"  [{name}] {count} results", file=sys.stderr)
                if result:
                    all_results.extend(result)
            except Exception as e:
                errors.append(f"{name}: {e}")

    if errors:
        for err in errors:
            print(f"  Warning: {err}", file=sys.stderr)

    print(f"  Total before dedup: {len(all_results)}", file=sys.stderr)
    all_results = deduplicate(all_results)
    all_results = filter_blacklisted(all_results)
    print(f"  Total after dedup:  {len(all_results)}", file=sys.stderr)

    all_results = _enrich_metadata(all_results, email=email)
    all_results = _enrich_tiers(all_results, email=email)

    return all_results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified parallel search across all citation-finder sources"
    )
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Results per source (default: 10)")
    parser.add_argument("--year-from", type=int, default=None, help="Filter by publication year")
    parser.add_argument("--email", default=None, help="Email for API polite/fast pools")
    parser.add_argument("--use-proxy", action="store_true", help="Use proxy for Google Scholar")
    parser.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")

    args = parser.parse_args()

    print(f"Searching: {args.query}", file=sys.stderr)
    results = search_all(
        query=args.query,
        limit=args.limit,
        year_from=args.year_from,
        email=args.email,
        use_proxy=args.use_proxy,
    )
    print(f"Final: {len(results)} unique papers", file=sys.stderr)

    output = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
