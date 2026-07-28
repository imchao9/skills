#!/usr/bin/env python3
"""Download labeled Xiaoqiumi event clips from a normalized match JSON."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("match_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def event_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    details = data.get("raw", {}).get("details", {}).get("集锦", {})
    rows: list[dict[str, Any]] = []
    for section in details.get("modeData") or []:
        videos = section.get("videos") or {}
        for item in videos.get("collectVideos") or []:
            if item.get("subName") == "个人集锦":
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if title and url:
                rows.append({"title": title, "url": url})
    return rows


def safe_name(title: str) -> str:
    return title.replace("/", "-").replace("\0", "").strip() + ".mp4"


def download(item: dict[str, str], output_dir: Path) -> dict[str, Any]:
    output = output_dir / safe_name(item["title"])
    part = output.with_name(output.name + ".part")
    if output.is_file() and output.stat().st_size > 0:
        return {"title": item["title"], "path": str(output), "bytes": output.stat().st_size, "status": "existing"}

    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "Mozilla/5.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(item["url"], headers=headers)
    response = urllib.request.urlopen(request, timeout=60)
    status = getattr(response, "status", response.getcode())
    append = existing > 0 and status == 206
    mode = "ab" if append else "wb"
    if existing and not append:
        existing = 0
    with response, part.open(mode) as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, output)
    return {"title": item["title"], "path": str(output), "bytes": output.stat().st_size, "status": "complete"}


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    data = json.loads(args.match_json.read_text(encoding="utf-8"))
    rows = event_rows(data)
    plan = {
        "status": "planned" if args.dry_run else "running",
        "match_json": str(args.match_json),
        "output_dir": str(args.output_dir),
        "count": len(rows),
        "items": [{"title": row["title"], "status": "planned"} for row in rows],
    }
    write_report(args.report, plan)
    if args.dry_run:
        print(json.dumps({"status": "planned", "count": len(rows)}, ensure_ascii=False))
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(download, row, args.output_dir): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                failures.append({"title": row["title"], "error": str(exc)})
    plan.update({
        "status": "complete" if not failures else "failed",
        "completed": len(results),
        "failed": len(failures),
        "bytes": sum(int(item["bytes"]) for item in results),
        "items": sorted(results, key=lambda item: item["title"]),
        "failures": failures,
    })
    write_report(args.report, plan)
    print(json.dumps({key: plan[key] for key in ("status", "count", "completed", "failed", "bytes")}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
