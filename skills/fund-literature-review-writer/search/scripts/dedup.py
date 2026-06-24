#!/usr/bin/env python3

import re


def _normalize_title(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def _source_priority(paper):
    layer = paper.get("source_layer", "")
    source = paper.get("source", "")
    if layer == "api":
        if source == "crossref":
            return 0
        if source == "openalex":
            return 1
        return 2
    if layer == "local":
        return 3
    if layer == "web":
        return 4
    return 9


_PRIO_FIELDS = frozenset({
    "doi", "title", "authors", "venue", "abstract", "issn_l", "issn",
})

_MERGE_FIELDS = (
    "doi", "title", "authors", "venue", "abstract", "citation_count",
    "issn_l", "issn", "volume", "issue", "pages", "publisher",
    "url", "open_access_pdf", "is_oa", "oa_status", "language", "keywords",
)


def _field_value_quality(val, field):
    if val is None:
        return -1
    if isinstance(val, list):
        return len(val)
    if isinstance(val, str):
        return len(val)
    if isinstance(val, (int, float)):
        return 0 if val == 0 else 1
    if isinstance(val, bool):
        return 1 if val else -1
    return 0


def _merge_group(group):
    group = sorted(group, key=lambda r: _source_priority(r))

    best = dict(group[0])

    for other in group[1:]:
        for field in _MERGE_FIELDS:
            best_val = best.get(field)
            other_val = other.get(field)

            if field == "citation_count":
                best[field] = max(best.get(field, 0) or 0, other.get(field, 0) or 0)
                continue

            best_q = _field_value_quality(best_val, field)
            other_q = _field_value_quality(other_val, field)

            if other_q < 0:
                continue

            if best_q < 0:
                best[field] = other_val
                continue

            if field in _PRIO_FIELDS:
                if _source_priority(other) < _source_priority(best):
                    best[field] = other_val
            else:
                if other_q > best_q:
                    best[field] = other_val

    sources = list(dict.fromkeys(
        [best.get("source", "")] + [r.get("source", "") for r in group if r.get("source")]
    ))
    if len(sources) > 1:
        best["source"] = "+".join(s for s in sources if s)

    return best


def deduplicate(results):
    doi_groups = {}
    no_doi = []
    for r in results:
        doi = (r.get("doi") or "").strip().lower()
        if doi:
            doi_groups.setdefault(doi, []).append(r)
        else:
            no_doi.append(r)

    merged = []
    for doi, group in doi_groups.items():
        merged.append(_merge_group(group))

    title_groups = {}
    for r in no_doi:
        norm = _normalize_title(r.get("title", ""))
        if not norm:
            merged.append(r)
            continue
        title_groups.setdefault(norm, []).append(r)

    for norm_title, group in title_groups.items():
        merged.append(_merge_group(group))

    return merged
