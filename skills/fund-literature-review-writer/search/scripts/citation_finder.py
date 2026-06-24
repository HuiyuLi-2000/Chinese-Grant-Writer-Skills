#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tier_utils import (
    compute_paper_tier_score,
    filter_blacklisted,
    _request_with_retry,
)
from dedup import deduplicate

OPENALEX_BASE = "https://api.openalex.org/works"
CROSSREF_BASE = "https://api.crossref.org/works"

TIMEOUT = 30


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


def _parse_openalex_result(item):
    doi = None
    if item.get("doi"):
        doi = item["doi"].replace("https://doi.org/", "")
    authors = []
    for a in item.get("authorships", []):
        name = a.get("author", {}).get("display_name", "")
        if name:
            parts = name.split()
            if len(parts) >= 2:
                authors.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
            else:
                authors.append(name)
    pl = item.get("primary_location") or {}
    source = pl.get("source") or {}
    venue = source.get("display_name", "")
    issn_list = source.get("issn") or []
    issn_l = source.get("issn_l")
    abstract = ""
    aii = item.get("abstract_inverted_index")
    if aii:
        word_positions = []
        for word, positions in aii.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        abstract = " ".join(w for _, w in word_positions)
    venue_type = "other"
    oa = item.get("open_access") or {}
    is_oa = oa.get("is_oa", False)
    oa_status = oa.get("oa_status") or ""
    pdf_url = None
    if oa.get("oa_url"):
        pdf_url = oa["oa_url"]
    return {
        "title": item.get("title", ""),
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": doi,
        "venue": venue,
        "venue_type": venue_type,
        "issn_l": issn_l,
        "issn": issn_list,
        "volume": None,
        "issue": None,
        "pages": None,
        "publisher": None,
        "abstract": abstract,
        "citation_count": item.get("cited_by_count", 0),
        "url": f"https://doi.org/{doi}" if doi else None,
        "open_access_pdf": pdf_url,
        "is_oa": is_oa,
        "oa_status": oa_status or None,
        "language": item.get("language"),
        "keywords": [],
        "source_layer": "api",
        "source": "openalex",
        "tier_score": 0.0,
        "recency_score": 0.0,
        "support_score": None,
        "composite_score": None,
    }


def search_openalex(query, year_from=None, limit=10, mailto=None):
    params = {
        "search": query,
        "per_page": min(limit, 50),
        "sort": "relevance_score:desc",
    }
    if mailto:
        params["mailto"] = mailto
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    filters.append("type:article|conference-paper|preprint|posted-content")
    if filters:
        params["filter"] = ",".join(filters)
    data = _request_with_retry(OPENALEX_BASE, params=params)
    if not data:
        return []
    results = []
    for item in data.get("results", []):
        r = _parse_openalex_result(item)
        type_ = item.get("type", "")
        if type_ == "article":
            r["venue_type"] = "journal"
        elif type_ == "conference-paper":
            r["venue_type"] = "conference"
        elif type_ in ("preprint", "posted-content"):
            r["venue_type"] = "preprint"
        biblio = item.get("biblio") or {}
        r["volume"] = biblio.get("volume")
        r["issue"] = biblio.get("issue")
        r["pages"] = None
        first_page = biblio.get("first_page")
        last_page = biblio.get("last_page")
        if first_page:
            r["pages"] = f"{first_page}-{last_page}" if last_page else first_page
        results.append(r)
    return results


def _parse_crossref_result(item):
    doi = item.get("DOI", "")
    title_list = item.get("title", [])
    title = title_list[0] if title_list else ""
    authors = []
    for a in item.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        name = f"{family}, {given}".strip(", ")
        if name:
            authors.append(name)
    venue_list = item.get("container-title", [])
    venue = venue_list[0] if venue_list else ""
    issn_list = item.get("ISSN", [])
    year = None
    published = item.get("published") or item.get("published-print") or item.get("published-online")
    if published:
        parts = published.get("date-parts", [[]])
        if parts and parts[0]:
            year = parts[0][0]
    abstract = item.get("abstract", "")
    if abstract.startswith("<jats:p>"):
        abstract = re.sub(r"</?jats:[^>]*>", "", abstract).strip()
    venue_type = "other"
    cr_type = item.get("type", "")
    if cr_type == "journal-article":
        venue_type = "journal"
    elif cr_type in ("proceedings-article", "proceedings"):
        venue_type = "conference"
    elif cr_type == "book-chapter":
        venue_type = "book"
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi,
        "venue": venue,
        "venue_type": venue_type,
        "issn_l": None,
        "issn": issn_list,
        "volume": item.get("volume"),
        "issue": item.get("issue"),
        "pages": item.get("page"),
        "publisher": item.get("publisher"),
        "abstract": abstract,
        "citation_count": item.get("is-referenced-by-count", 0),
        "url": f"https://doi.org/{doi}" if doi else None,
        "open_access_pdf": None,
        "is_oa": False,
        "oa_status": None,
        "language": item.get("language"),
        "keywords": item.get("subject", []),
        "source_layer": "api",
        "source": "crossref",
        "tier_score": 0.0,
        "recency_score": 0.0,
        "support_score": None,
        "composite_score": None,
    }


def search_crossref(query, year_from=None, limit=10, mailto=None):
    params = {
        "query.bibliographic": query,
        "rows": min(limit, 50),
    }
    filters = ["type:journal-article|proceedings-article"]
    if year_from:
        filters.append(f"from-pub-date:{year_from}")
    if filters:
        params["filter"] = ",".join(filters)
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(CROSSREF_BASE, params=params)
    if not data:
        return []
    items = data.get("message", {}).get("items", [])
    results = []
    for item in items:
        results.append(_parse_crossref_result(item))
    return results


def year_normalize(year, current_year=None):
    if current_year is None:
        current_year = datetime.datetime.now().year
    if not year:
        return 0.1
    age = current_year - year
    if age < 0:
        return 1.0
    if age <= 2:
        return 1.0
    if age <= 5:
        return 0.8
    if age <= 10:
        return 0.5
    if age <= 20:
        return 0.3
    return 0.1


SEARCH_FUNCS = {
    "openalex": lambda q, y, l, m: search_openalex(q, year_from=y, limit=l, mailto=m),
    "crossref": lambda q, y, l, m: search_crossref(q, year_from=y, limit=l, mailto=m),
}


def search(query, sources=None, year_from=None, limit=10, email=None, skip_dedup=False):
    if email is None:
        email = os.getenv("OPENALEX_EMAIL")
    if sources is None:
        sources = list(SEARCH_FUNCS.keys())
    invalid = [s for s in sources if s not in SEARCH_FUNCS]
    if invalid:
        print(f"Unknown sources: {invalid}. Available: {list(SEARCH_FUNCS.keys())}", file=sys.stderr)
        sys.exit(1)

    all_results = []
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {}
        for src in sources:
            func = SEARCH_FUNCS[src]
            future = executor.submit(func, query, year_from, limit, email)
            futures[future] = src
        for future in as_completed(futures):
            src = futures[future]
            try:
                result = future.result()
                if result:
                    all_results.extend(result)
            except Exception as e:
                print(f"Error searching {src}: {e}", file=sys.stderr)

    if not skip_dedup:
        try:
            all_results = deduplicate(all_results)
        except Exception as e:
            print(f"Warning: dedup failed ({e}), using raw results", file=sys.stderr)
        try:
            all_results = filter_blacklisted(all_results)
        except Exception as e:
            print(f"Warning: blacklist filter failed ({e})", file=sys.stderr)

        for paper in all_results:
            try:
                paper["tier_score"] = round(compute_paper_tier_score(paper, mailto=email), 4)
            except Exception:
                paper["tier_score"] = 0.0
            paper["recency_score"] = round(year_normalize(paper.get("year")), 4)

    return all_results


def lookup_by_doi(doi, mailto=None):
    """Look up a paper by DOI on OpenAlex, return unified dict or None."""
    if not doi:
        return None
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    doi_clean = doi.strip()
    if doi_clean.startswith("https://doi.org/"):
        doi_clean = doi_clean.replace("https://doi.org/", "")
    elif doi_clean.startswith("http://doi.org/"):
        doi_clean = doi_clean.replace("http://doi.org/", "")
    params = {"filter": f"doi:{doi_clean}"}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(OPENALEX_BASE, params=params)
    if data and data.get("results"):
        return _parse_openalex_result(data["results"][0])
    return None


def lookup_by_title(title, mailto=None):
    """Look up a paper by title on OpenAlex, return unified dict or None."""
    if not title:
        return None
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    params = {"search": title, "per_page": 1}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(OPENALEX_BASE, params=params)
    if data and data.get("results"):
        return _parse_openalex_result(data["results"][0])
    return None


def lookup_crossref_by_doi(doi, mailto=None):
    """Look up a paper by DOI on Crossref, return unified dict or None."""
    if not doi:
        return None
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    doi_clean = doi.strip()
    if doi_clean.startswith("https://doi.org/"):
        doi_clean = doi_clean.replace("https://doi.org/", "")
    elif doi_clean.startswith("http://doi.org/"):
        doi_clean = doi_clean.replace("http://doi.org/", "")
    url = f"{CROSSREF_BASE}/{doi_clean}"
    params = {}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(url, params=params)
    if data and data.get("message"):
        return _parse_crossref_result(data["message"])
    return None


def lookup_crossref_by_title(title, mailto=None):
    """Look up a paper by title on Crossref, return unified dict or None."""
    if not title:
        return None
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    params = {"query.bibliographic": title, "rows": 1}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(CROSSREF_BASE, params=params)
    if data:
        items = data.get("message", {}).get("items", [])
        if items:
            return _parse_crossref_result(items[0])
    return None


def batch_lookup_by_dois(dois, mailto=None, batch_size=50):
    """Batch look up papers by DOIs on OpenAlex, return dict of doi -> unified dict."""
    if not dois:
        return {}
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    normalized = []
    for doi in dois:
        d = doi.strip()
        if d.startswith("https://doi.org/"):
            d = d.replace("https://doi.org/", "")
        elif d.startswith("http://doi.org/"):
            d = d.replace("http://doi.org/", "")
        if d:
            normalized.append(d)
    results = {}
    for i in range(0, len(normalized), batch_size):
        batch = normalized[i:i + batch_size]
        filter_str = "|".join(f"doi:{doi}" for doi in batch)
        params = {
            "filter": filter_str,
            "per_page": min(len(batch), 50),
        }
        if mailto:
            params["mailto"] = mailto
        data = _request_with_retry(OPENALEX_BASE, params=params)
        if data:
            for item in data.get("results", []):
                doi = item.get("doi", "").replace("https://doi.org/", "")
                if doi:
                    results[doi] = _parse_openalex_result(item)
    return results


def merge_zotero(claim_path, zotero_path, output_path=None, mailto=None):
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    try:
        with open(claim_path, "r", encoding="utf-8") as f:
            claim_papers = json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        print(f"Error reading claim file: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(zotero_path, "r", encoding="utf-8") as f:
            zotero_papers = json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        print(f"Error reading Zotero file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(claim_papers, list):
        claim_papers = [claim_papers]
    if not isinstance(zotero_papers, list):
        zotero_papers = [zotero_papers]

    for zp in zotero_papers:
        zp.setdefault("source_layer", "local")
        zp.setdefault("source", "zotero")
        zp.setdefault("tier_score", 0.0)
        zp.setdefault("recency_score", 0.0)
        zp.setdefault("support_score", None)
        zp.setdefault("composite_score", None)

    combined = claim_papers + zotero_papers
    merged = deduplicate(combined)
    merged = filter_blacklisted(merged)

    need_enrich = [p for p in merged if not p.get("tier_score") or p.get("tier_score", 0) <= 0]
    print(f"Merged: {len(claim_papers)} claim + {len(zotero_papers)} zotero → {len(merged)} unique ({len(need_enrich)} need tier enrichment)", file=sys.stderr)

    for paper in need_enrich:
        paper["tier_score"] = round(compute_paper_tier_score(paper, mailto=mailto), 4)
        paper["recency_score"] = round(year_normalize(paper.get("year")), 4)

    target = output_path or claim_path
    with open(target, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"Written to {target}", file=sys.stderr)

    return merged


def enrich_tiers(input_path, output_path=None, mailto=None):
    if mailto is None:
        mailto = os.getenv("OPENALEX_EMAIL")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            papers = json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(papers, list):
        papers = [papers]

    need_tier = [p for p in papers if not p.get("tier_score") or p.get("tier_score", 0) <= 0]
    print(f"Enriching tier+recency for {len(need_tier)}/{len(papers)} papers", file=sys.stderr)

    for paper in need_tier:
        paper["tier_score"] = round(compute_paper_tier_score(paper, mailto=mailto), 4)
        paper["recency_score"] = round(year_normalize(paper.get("year")), 4)

    need_composite = [
        p for p in papers
        if p.get("support_score") is not None and p.get("composite_score") is None
    ]
    for paper in need_composite:
        tier = paper.get("tier_score", 0) or 0
        recency = paper.get("recency_score", 0) or 0
        support = paper.get("support_score", 0) or 0
        paper["composite_score"] = round(tier * 0.3 + support * 0.3 + recency * 0.4, 4)

    if need_composite:
        print(f"Computed composite_score for {len(need_composite)} papers", file=sys.stderr)

    target = output_path or input_path
    with open(target, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    print(f"Written to {target}", file=sys.stderr)

    return papers


def main():
    parser = argparse.ArgumentParser(description="Search academic papers across OpenAlex and Crossref")
    subparsers = parser.add_subparsers(dest="command")

    search_parser = subparsers.add_parser("search", help="Search academic papers")
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument("--sources", nargs="+", default=None,
                               choices=["openalex", "crossref"],
                               help="Search sources (default: all)")
    search_parser.add_argument("--year-from", type=int, default=None, help="Filter by publication year")
    search_parser.add_argument("--limit", type=int, default=10, help="Results per source (default: 10)")
    search_parser.add_argument("--email", default=None,
                               help="Email for Crossref polite pool and OpenAlex fast pool")

    merge_parser = subparsers.add_parser("merge", help="Merge Zotero results into claim file (in-place by default)")
    merge_parser.add_argument("--claim", required=True, help="Path to claim JSON file (search results)")
    merge_parser.add_argument("--zotero", required=True, help="Path to Zotero results JSON file")
    merge_parser.add_argument("--output", default=None, help="Output file (default: overwrite --claim in-place)")
    merge_parser.add_argument("--email", default=None, help="Email for OpenAlex fast pool")

    enrich_parser = subparsers.add_parser("enrich-tiers", help="Enrich tier+recency scores (in-place by default)")
    enrich_parser.add_argument("--input", required=True, help="Path to JSON file with paper list")
    enrich_parser.add_argument("--output", default=None, help="Output JSON file (default: overwrite --input in-place)")
    enrich_parser.add_argument("--email", default=None, help="Email for OpenAlex fast pool")

    args = parser.parse_args()

    if args.command == "merge":
        merge_zotero(args.claim, args.zotero, output_path=args.output, mailto=args.email)
    elif args.command == "enrich-tiers":
        enrich_tiers(args.input, output_path=args.output, mailto=args.email)
    else:
        if not args.command:
            search_parser.parse_args(["--query", ""])
        results = search(
            query=args.query,
            sources=args.sources,
            year_from=args.year_from,
            limit=args.limit,
            email=args.email,
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
