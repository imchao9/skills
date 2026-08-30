#!/usr/bin/env python3
"""Validate relative Markdown links without opening network resources."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_part = unquote(target.split("#", 1)[0])
            resolved = (markdown.parent / path_part).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                failures.append(f"{markdown.relative_to(root)}: link escapes skill root")
                continue
            if not resolved.exists():
                failures.append(f"{markdown.relative_to(root)}: missing relative target {path_part}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Relative Markdown links passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
