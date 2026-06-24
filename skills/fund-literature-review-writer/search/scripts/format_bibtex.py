#!/usr/bin/env python3

import argparse
import json
import re
import sys


def _generate_citation_key(paper):
    authors = paper.get("authors", [])
    year = paper.get("year")
    if authors:
        first_author = authors[0]
        parts = first_author.split(",")
        last_name = parts[0].strip() if parts else first_author
        last_name = re.sub(r"[^a-zA-Z]", "", last_name).lower()
    else:
        last_name = "unknown"
    title = paper.get("title", "")
    title_word = ""
    if title:
        for w in title.split():
            clean = re.sub(r"[^a-zA-Z]", "", w).lower()
            if clean and len(clean) > 2 and clean not in ("the", "and", "for", "with", "from", "based", "using", "towards", "novel", "new"):
                title_word = clean
                break
    key = f"{last_name}{year or 'noyear'}"
    if title_word:
        key += title_word.capitalize()
    return key


def _determine_entry_type(paper):
    venue = (paper.get("venue") or "").lower()
    venue_type = paper.get("venue_type", "")
    conf_keywords = ["conference", "proceedings", "symposium", "workshop", "neurips", "icml", "iclr", "aaai", "ijcai", "cvpr", "iccv", "eccv", "kdd", "sigmod", "vldb", "icde"]
    for kw in conf_keywords:
        if kw in venue:
            return "inproceedings"
    if venue_type == "conference":
        return "inproceedings"
    if venue_type == "journal" or venue:
        return "article"
    return "misc"


def _escape_bibtex(text):
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("#", "\\#")
    text = text.replace("~", "\\~")
    text = text.replace("^", "\\^")
    return text


def _format_authors(authors):
    if not authors:
        return ""
    return " and ".join(authors)


def paper_to_bibtex(paper, key=None):
    entry_type = _determine_entry_type(paper)
    if key is None:
        key = _generate_citation_key(paper)
    fields = []
    title = paper.get("title", "")
    if title:
        fields.append(f"  title = {{{_escape_bibtex(title)}}}")
    authors = paper.get("authors", [])
    if authors:
        fields.append(f"  author = {{{_escape_bibtex(_format_authors(authors))}}}")
    year = paper.get("year")
    if year:
        fields.append(f"  year = {{{year}}}")
    venue = paper.get("venue", "")
    if venue:
        if entry_type == "inproceedings":
            fields.append(f"  booktitle = {{{_escape_bibtex(venue)}}}")
        else:
            fields.append(f"  journal = {{{_escape_bibtex(venue)}}}")
    doi = paper.get("doi", "")
    if doi:
        fields.append(f"  doi = {{{doi}}}")
    volume = paper.get("volume", "")
    if volume:
        fields.append(f"  volume = {{{volume}}}")
    issue = paper.get("issue", "")
    if issue:
        fields.append(f"  number = {{{issue}}}")
    pages = paper.get("pages", "")
    if pages:
        fields.append(f"  pages = {{{pages}}}")
    url = paper.get("url", "")
    if url:
        fields.append(f"  url = {{{url}}}")
    abstract = paper.get("abstract", "")
    if abstract:
        escaped = _escape_bibtex(abstract)
        if len(escaped) > 500:
            escaped = escaped[:497] + "..."
        fields.append(f"  abstract = {{{escaped}}}")
    fields_str = ",\n".join(fields)
    return f"@{entry_type}{{{key},\n{fields_str}\n}}"


def batch_format(input_path, output_path=None):
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            papers = json.load(f)
    except (OSError, IOError, json.JSONDecodeError) as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(papers, list):
        papers = [papers]
    entries = []
    seen_keys = {}
    for paper in papers:
        base_key = _generate_citation_key(paper)
        if base_key in seen_keys:
            seen_keys[base_key] += 1
            key = f"{base_key}_{seen_keys[base_key]}"
        else:
            seen_keys[base_key] = 1
            key = base_key
        entry = paper_to_bibtex(paper, key=key)
        entries.append(entry)
    bib_content = "\n\n".join(entries) + "\n"
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(bib_content)
            print(f"Written {len(entries)} entries to {output_path}", file=sys.stderr)
        except (OSError, IOError) as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(bib_content)


def main():
    parser = argparse.ArgumentParser(description="Format paper metadata as BibTeX entries")
    parser.add_argument("--input", required=True, help="Input JSON file with paper metadata")
    parser.add_argument("--output", default=None, help="Output .bib file (default: stdout)")
    args = parser.parse_args()
    batch_format(args.input, args.output)


if __name__ == "__main__":
    main()
