#!/usr/bin/env python3
"""Verify a downloaded media file without exposing its contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def fail(message: str, *, details: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"status": "fail", "error": message}
    if details:
        payload.update(details)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a downloaded file is a readable video."
    )
    parser.add_argument("path", type=Path, help="Local media file to verify")
    parser.add_argument(
        "--sha256",
        action="store_true",
        help="Include a SHA-256 digest in the JSON result",
    )
    args = parser.parse_args()

    path = args.path.expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    if not path.is_file():
        return fail("file_not_found", details={"path": str(path)})

    size = path.stat().st_size
    if size <= 0:
        return fail("empty_file", details={"path": str(path), "size_bytes": size})

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return fail(
            "ffprobe_not_found",
            details={
                "path": str(path),
                "size_bytes": size,
                "hint": "Install ffmpeg/ffprobe, then rerun verification.",
            },
        )

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,format_name:stream=index,codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return fail("ffprobe_timeout", details={"path": str(path)})

    if completed.returncode != 0:
        return fail(
            "ffprobe_failed",
            details={
                "path": str(path),
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip()[:500],
            },
        )

    try:
        probe = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return fail("ffprobe_invalid_json", details={"path": str(path)})

    streams = probe.get("streams") or []
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    if not video_streams:
        return fail(
            "video_stream_missing",
            details={"path": str(path), "size_bytes": size},
        )

    raw_duration = (probe.get("format") or {}).get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        return fail(
            "invalid_duration",
            details={"path": str(path), "duration_seconds": duration},
        )

    result: dict[str, Any] = {
        "status": "pass",
        "path": str(path),
        "size_bytes": size,
        "duration_seconds": round(duration, 3),
        "format_name": (probe.get("format") or {}).get("format_name"),
        "video_streams": [
            {
                "codec": item.get("codec_name"),
                "width": item.get("width"),
                "height": item.get("height"),
            }
            for item in video_streams
        ],
    }
    if args.sha256:
        result["sha256"] = sha256_file(path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
