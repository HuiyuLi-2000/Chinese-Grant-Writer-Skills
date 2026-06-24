#!/usr/bin/env python3

import csv
import os
import random
import re
import sys
import time

import requests

OPENALEX_SOURCES = "https://api.openalex.org/sources"
TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE = 3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
CONF_CSV = os.path.join(DATA_DIR, "priority_journals.csv")
BLACKLIST_CSV = os.path.join(DATA_DIR, "blacklist_journals.csv")

CONFERENCE_TIER_SCORE = 0.8

_issn_source_cache = {}
_name_source_cache = {}
_conf_lookup = None
_blacklist = None


def _request_with_retry(url, params=None, headers=None, timeout=TIMEOUT):
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        wait = int(retry_after)
                    else:
                        wait = BACKOFF_BASE ** attempt
                    wait += random.uniform(0, 1)
                    print(f"  429 rate-limited, retrying in {wait:.1f}s (attempt {attempt+1}/{MAX_RETRIES})", file=sys.stderr)
                    time.sleep(wait)
                    continue
                print(f"  429 rate-limited, max retries exceeded", file=sys.stderr)
                return None
            if resp.status_code >= 400:
                return None
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt + random.uniform(0, 1)
                time.sleep(wait)
                continue
            return None
    return None


def _load_conference_lookup():
    global _conf_lookup
    if _conf_lookup is not None:
        return _conf_lookup
    lookup = {"abbr": {}, "full": {}}
    if not os.path.exists(CONF_CSV):
        _conf_lookup = lookup
        return lookup
    try:
        with open(CONF_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                abbr = row.get("abbreviation", "").strip()
                full = row.get("full_name", "").strip()
                if abbr:
                    lookup["abbr"][_normalize(abbr)] = abbr
                if full:
                    lookup["full"][_normalize(full)] = full
    except (OSError, IOError):
        pass
    _conf_lookup = lookup
    return lookup


def _normalize(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _is_conference_in_list(venue):
    if not venue:
        return False
    lookup = _load_conference_lookup()
    norm = _normalize(venue)
    if norm in lookup["abbr"]:
        return True
    if norm in lookup["full"]:
        return True
    for full_norm in lookup["full"]:
        if full_norm in norm or norm in full_norm:
            return True
    for abbr_norm in lookup["abbr"]:
        if abbr_norm in norm or norm in abbr_norm:
            return True
    return False


def _load_blacklist():
    global _blacklist
    if _blacklist is not None:
        return _blacklist
    bl = {"issn": set(), "name": set(), "publisher": set()}
    if not os.path.exists(BLACKLIST_CSV):
        _blacklist = bl
        return bl
    try:
        with open(BLACKLIST_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                issn = row.get("issn", "").strip()
                name = row.get("name", "").strip()
                publisher = row.get("publisher", "").strip()
                if issn:
                    bl["issn"].add(issn.lower())
                if name:
                    bl["name"].add(_normalize(name))
                if publisher:
                    bl["publisher"].add(_normalize(publisher))
    except (OSError, IOError):
        pass
    _blacklist = bl
    return bl


def is_blacklisted(paper):
    bl = _load_blacklist()
    all_issns = []
    issn_l = paper.get("issn_l")
    issn_list = paper.get("issn") or []
    if issn_l:
        all_issns.append(issn_l)
    all_issns.extend(issn_list)
    for issn in all_issns:
        if issn and issn.lower() in bl["issn"]:
            return True
    venue = paper.get("venue", "")
    if venue and _normalize(venue) in bl["name"]:
        return True
    publisher = paper.get("publisher", "")
    if publisher:
        norm_pub = _normalize(publisher)
        for bl_pub in bl["publisher"]:
            if bl_pub in norm_pub:
                return True
    return False


def filter_blacklisted(papers):
    kept = []
    removed = 0
    for paper in papers:
        if is_blacklisted(paper):
            removed += 1
        else:
            kept.append(paper)
    if removed > 0:
        print(f"  Blacklist filtered: {removed} papers removed", file=sys.stderr)
    return kept


def _compute_citedness_score(openalex_source):
    if not openalex_source:
        return None
    stats = openalex_source.get("summary_stats", {})
    citedness = stats.get("2yr_mean_citedness", 0) or 0
    if citedness > 10:
        return 0.95
    if citedness > 5:
        return 0.8
    if citedness > 2:
        return 0.6
    if citedness > 0.5:
        return 0.4
    return 0.2


def lookup_openalex_source(issn, mailto=None):
    if not issn:
        return None
    if issn in _issn_source_cache:
        return _issn_source_cache[issn]
    params = {"filter": f"issn:{issn}"}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(OPENALEX_SOURCES, params=params)
    if not data:
        _issn_source_cache[issn] = None
        return None
    results = data.get("results", [])
    source = results[0] if results else None
    _issn_source_cache[issn] = source
    return source


def lookup_openalex_source_by_name(name, mailto=None):
    if not name:
        return None
    norm_name = _normalize(name)
    if norm_name in _name_source_cache:
        return _name_source_cache[norm_name]
    params = {"search": name, "per_page": 1}
    if mailto:
        params["mailto"] = mailto
    data = _request_with_retry(OPENALEX_SOURCES, params=params)
    if not data:
        _name_source_cache[norm_name] = None
        return None
    results = data.get("results", [])
    source = results[0] if results else None
    _name_source_cache[norm_name] = source
    return source


def compute_paper_tier_score(paper, mailto=None):
    venue = paper.get("venue", "")
    venue_type = paper.get("venue_type", "")

    is_conf = venue_type == "conference" or _is_conference_in_list(venue)
    if is_conf and _is_conference_in_list(venue):
        return CONFERENCE_TIER_SCORE

    issn = paper.get("issn_l") or (paper.get("issn") or [None])[0]
    oa_source = None
    if issn:
        oa_source = lookup_openalex_source(issn, mailto=mailto)
    if not oa_source and venue:
        oa_source = lookup_openalex_source_by_name(venue, mailto=mailto)
    if oa_source:
        score = _compute_citedness_score(oa_source)
        if score is not None:
            return score
    return 0.1


def compute_direct_tier_score(openalex_data=None):
    if openalex_data:
        score = _compute_citedness_score(openalex_data)
        if score is not None:
            return score
    return 0.1


def format_source_info(source):
    stats = source.get("summary_stats", {})
    return {
        "name": source.get("display_name", ""),
        "issn_l": source.get("issn_l", ""),
        "issn": source.get("issn", []),
        "type": source.get("type", ""),
        "host_organization": source.get("host_organization_name", ""),
        "2yr_mean_citedness": stats.get("2yr_mean_citedness"),
        "h_index": stats.get("h_index"),
        "i10_index": stats.get("i10_index"),
        "works_count": source.get("works_count"),
        "is_in_doaj": source.get("is_in_doaj"),
        "is_oa": source.get("is_oa"),
        "tier_score": compute_direct_tier_score(openalex_data=source),
    }
