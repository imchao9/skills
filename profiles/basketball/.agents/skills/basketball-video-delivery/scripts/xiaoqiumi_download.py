#!/usr/bin/env python3
"""Stream a Xiaoqiumi media URL without persisting its query or credentials."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url-env", default="XQM_DOWNLOAD_URL")
    parser.add_argument("--url-stdin", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--user-agent", default="Mozilla/5.0")
    parser.add_argument("--probe-only", action="store_true", help="Report remote size without downloading media.")
    parser.add_argument("--connections", type=int, default=1, help="Parallel byte-range connections.")
    return parser.parse_args()


def sanitized(url: str) -> str:
    value = urlsplit(url)
    return urlunsplit((value.scheme, value.netloc, value.path, "", ""))


def write_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probe_remote(url: str, user_agent: str) -> dict:
    headers = {"User-Agent": user_agent}
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 405):
            raise
        headers["Range"] = "bytes=0-0"
        request = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(request, timeout=60)
    with response:
        content_range = response.headers.get("Content-Range", "")
        total = content_range.rsplit("/", 1)[-1] if "/" in content_range else ""
        size = int(total) if total.isdigit() else int(response.headers.get("Content-Length", "0") or 0)
        if size <= 0:
            raise RuntimeError("remote media size is unavailable")
        return {
            "status": "probed",
            "source": sanitized(url),
            "bytes": size,
            "etag": response.headers.get("ETag"),
            "accept_ranges": response.headers.get("Accept-Ranges"),
        }


def split_ranges(size: int, count: int) -> list[tuple[int, int]]:
    count = max(1, min(count, size))
    chunk_size = (size + count - 1) // count
    return [
        (start, min(size - 1, start + chunk_size - 1))
        for start in range(0, size, chunk_size)
    ]


def download_range(url: str, user_agent: str, path: Path, start: int, end: int) -> int:
    expected = end - start + 1
    if path.is_file() and path.stat().st_size == expected:
        return expected
    temporary = path.with_name(path.name + ".part")
    existing = temporary.stat().st_size if temporary.exists() else 0
    if existing > expected:
        temporary.unlink()
        existing = 0
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Range": f"bytes={start + existing}-{end}",
        },
    )
    response = urllib.request.urlopen(request, timeout=60)
    status = getattr(response, "status", response.getcode())
    if status != 206:
        response.close()
        raise RuntimeError(f"range request returned HTTP {status}, expected 206")
    mode = "ab" if existing else "wb"
    with response, temporary.open(mode) as handle:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)
        handle.flush()
        os.fsync(handle.fileno())
    actual = temporary.stat().st_size
    if actual != expected:
        raise RuntimeError(f"range size mismatch: expected {expected}, got {actual}")
    os.replace(temporary, path)
    return actual


def download_parallel(
    url: str,
    user_agent: str,
    output: Path,
    part: Path,
    connections: int,
) -> dict:
    remote = probe_remote(url, user_agent)
    size = int(remote["bytes"])
    ranges = split_ranges(size, connections)
    chunk_dir = output.with_name(output.name + ".chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths = [chunk_dir / f"{index:04d}.part" for index in range(len(ranges))]
    with ThreadPoolExecutor(max_workers=len(ranges)) as pool:
        futures = {
            pool.submit(download_range, url, user_agent, path, start, end): index
            for index, (path, (start, end)) in enumerate(zip(chunk_paths, ranges))
        }
        for future in as_completed(futures):
            future.result()
    with part.open("wb") as destination:
        for path in chunk_paths:
            with path.open("rb") as source:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    destination.write(block)
        destination.flush()
        os.fsync(destination.fileno())
    actual = part.stat().st_size
    if actual != size:
        raise RuntimeError(f"assembled size mismatch: expected {size}, got {actual}")
    os.replace(part, output)
    for path in chunk_paths:
        path.unlink()
    chunk_dir.rmdir()
    return {
        "status": "complete",
        "source": sanitized(url),
        "output": str(output),
        "bytes": actual,
        "etag": remote.get("etag"),
        "range_supported": True,
        "connections": len(ranges),
    }


def main() -> int:
    args = parse_args()
    url = sys.stdin.readline().strip() if args.url_stdin else os.environ.get(args.url_env, "").strip()
    if not url:
        raise SystemExit(f"download URL missing; set {args.url_env} or use --url-stdin")

    if args.probe_only:
        try:
            payload = probe_remote(url, args.user_agent)
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            payload = {"status": "failed", "source": sanitized(url), "error": str(exc)}
            write_report(args.report, payload)
            raise SystemExit(str(exc)) from exc

    output = args.output.resolve()
    part = output.with_name(output.name + ".part")
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.connections > 1:
        try:
            payload = download_parallel(url, args.user_agent, output, part, args.connections)
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            message = str(exc).replace(url, sanitized(url))
            payload = {"status": "failed", "source": sanitized(url), "error": message}
            write_report(args.report, payload)
            raise SystemExit(message) from exc

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
