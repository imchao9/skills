#!/usr/bin/env python3
"""Stream a Xiaoqiumi media URL without persisting its query or credentials."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url-env", default="XQM_DOWNLOAD_URL")
    parser.add_argument("--url-stdin", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--user-agent", default="Mozilla/5.0")
    return parser.parse_args()


def sanitized(url: str) -> str:
    value = urlsplit(url)
    return urlunsplit((value.scheme, value.netloc, value.path, "", ""))


def write_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    url = sys.stdin.readline().strip() if args.url_stdin else os.environ.get(args.url_env, "").strip()
    if not url:
        raise SystemExit(f"download URL missing; set {args.url_env} or use --url-stdin")

    output = args.output.resolve()
    part = output.with_name(output.name + ".part")
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": args.user_agent}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    payload = {
        "status": "running",
        "source": sanitized(url),
        "output": str(output),
        "part": str(part),
        "resumed_from": existing,
    }
    write_report(args.report, payload)

    try:
        response = urllib.request.urlopen(request, timeout=60)
        status = getattr(response, "status", response.getcode())
        append = existing > 0 and status == 206
        if existing and not append:
            existing = 0
        content_length = int(response.headers.get("Content-Length", "0") or 0)
        expected = existing + content_length if content_length else None
        mode = "ab" if append else "wb"
        with response, part.open(mode) as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        actual = part.stat().st_size
        if expected is not None and actual != expected:
            raise RuntimeError(f"size mismatch: expected {expected}, got {actual}")
        os.replace(part, output)
        payload.update({
            "status": "complete",
            "bytes": actual,
            "etag": response.headers.get("ETag"),
            "range_supported": status == 206,
        })
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        payload.update({"status": "failed", "error": str(exc)})
        write_report(args.report, payload)
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    sys.exit(main())
