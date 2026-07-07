#!/usr/bin/env python3
"""Static checks for local HTML presentation decks."""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


PLACEHOLDERS = re.compile(r"TODO|FIXME|\[TODO|lorem ipsum|待补充|占位", re.I)


class DeckParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.slides = 0
        self.local_refs: list[tuple[str, str]] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k.lower(): v or "" for k, v in attrs}
        classes = data.get("class", "")
        if tag.lower() in {"section", "article", "div"} and re.search(r"\bslide\b", classes):
            self.slides += 1

        for attr in ("src", "href"):
            value = data.get(attr)
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https", "mailto", "tel", "data"}:
                continue
            if value.startswith("#") or value.startswith("javascript:"):
                continue
            self.local_refs.append((tag, value.split("#", 1)[0]))

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a local HTML deck for basic readiness.")
    parser.add_argument("deck", type=Path)
    parser.add_argument("--min-slides", type=int, default=3)
    args = parser.parse_args()

    deck = args.deck.expanduser().resolve()
    if not deck.exists():
        print(f"FAIL deck not found: {deck}")
        return 2

    html = deck.read_text(encoding="utf-8", errors="replace")
    parsed = DeckParser()
    parsed.feed(html)

    failures: list[str] = []
    warnings: list[str] = []

    if parsed.slides < args.min_slides:
        failures.append(f"slide count {parsed.slides} < {args.min_slides}")

    for tag, ref in parsed.local_refs:
        ref_path = (deck.parent / ref).resolve()
        try:
            ref_path.relative_to(deck.parent)
        except ValueError:
            warnings.append(f"{tag} references outside deck folder: {ref}")
            continue
        if not ref_path.exists():
            failures.append(f"missing local {tag} reference: {ref}")

    text = "\n".join(parsed.text_parts)
    if PLACEHOLDERS.search(text):
        failures.append("placeholder text found")

    if re.search(r"[\u4e00-\u9fff]", text) and re.search(r"\b(overview|agenda|roadmap|solution|problem)\b", text, re.I):
        warnings.append("mixed Chinese/English presentation terms detected")

    print(f"deck: {deck}")
    print(f"slides: {parsed.slides}")
    print(f"local refs: {len(parsed.local_refs)}")

    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")

    if failures:
        return 1
    print("PASS basic static checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
