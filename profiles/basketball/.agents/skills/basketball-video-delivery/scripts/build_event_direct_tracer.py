#!/usr/bin/env python3
"""Locate one Xiaoqiumi event and cut it directly from the full replay."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
LOCATOR = SCRIPT_DIR / "locate_event_thumbnails.py"
RENDERER = SCRIPT_DIR / "render_player_reels_from_matches.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-json", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--locations-csv",
        type=Path,
        help="Reuse a reviewed locator CSV instead of running thumbnail alignment.",
    )
    parser.add_argument("--period-start", action="append", default=[])
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    parser.add_argument("--default-pre", type=float, default=15.0)
    parser.add_argument("--default-post", type=float, default=3.0)
    parser.add_argument("--assist-pre", type=float, default=15.0)
    parser.add_argument("--assist-post", type=float, default=0.0)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def run(command: list[str]) -> float:
    started = time.monotonic()
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(f"command failed with exit {result.returncode}: {command[0]}")
    return round(time.monotonic() - started, 3)


def probe_video(path: Path, *, full_decode: bool = False) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration,size",
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration") or 0)
    if duration <= 0 or not payload.get("streams"):
        raise RuntimeError(f"invalid video: {path}")
    if full_decode:
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
            text=True,
            capture_output=True,
        )
        if decoded.returncode:
            raise RuntimeError(f"full decode failed for {path}: {decoded.stderr.strip()}")
    return {
        "duration_seconds": round(duration, 3),
        "bytes": int(payload.get("format", {}).get("size") or path.stat().st_size),
    }


def read_single_event(path: Path, event_id: str) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        matches = [row for row in csv.DictReader(handle) if row.get("event_id") == event_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one location for event_id={event_id}, found {len(matches)}")
    row = matches[0]
    required = ["event_id", "title", "team", "number", "player", "action", "period", "clock", "source_seconds"]
    missing = [field for field in required if not str(row.get(field) or "").strip()]
    if missing:
        raise ValueError(f"located event is missing required fields: {', '.join(missing)}")
    return row


def write_matches_csv(path: Path, row: dict[str, str], source: Path) -> None:
    rendered = {**row, "source": str(source)}
    fields = list(rendered)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(rendered)


def read_only_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise RuntimeError(f"expected one row in {path}, found {len(rows)}")
    return rows[0]


def build_audit_contact_sheet(video: Path, duration: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
            "-vf", f"fps={4 / duration:.8f},scale=480:-1,tile=4x1:padding=4:margin=4",
            "-frames:v", "1", str(output),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode or not output.is_file():
        raise RuntimeError(f"unable to build tracer contact sheet: {result.stderr.strip()}")


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    source = args.source.resolve()
    match_json = args.match_json.resolve()
    output = args.output_dir.resolve()
    report = (args.report or output / "event-direct-report.json").resolve()
    output.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "status": "running",
        "mode": "event_direct",
        "event_id": args.event_id,
        "source": str(source),
        "match_json": str(match_json),
        "platform_event_download_count": 0,
        "stages": [],
    }
    write_report(report, payload)
    try:
        source_probe = probe_video(source)
        locations = (args.locations_csv or output / "event-locations.csv").resolve()
        if args.locations_csv:
            if not locations.is_file():
                raise FileNotFoundError(f"locations CSV does not exist: {locations}")
            payload["stages"].append({"name": "locate_event", "status": "cached", "path": str(locations)})
        else:
            command = [
                sys.executable, str(LOCATOR), "--match-json", str(match_json),
                "--source", str(source), "--output-csv", str(locations),
            ]
            for value in args.period_start:
                command.extend(["--period-start", value])
            seconds = run(command)
            payload["stages"].append({"name": "locate_event", "status": "complete", "seconds": seconds})

        event = read_single_event(locations, args.event_id)
        event_seconds = float(event["source_seconds"])
        if not 0 <= event_seconds <= source_probe["duration_seconds"]:
            raise ValueError(
                f"event source_seconds {event_seconds} is outside source duration {source_probe['duration_seconds']}"
            )

        matches = output / "matches.csv"
        write_matches_csv(matches, event, source)
        render_output = output / "rendered"
        seconds = run([
            sys.executable, str(RENDERER), "--matches-csv", str(matches),
            "--output-dir", str(render_output), "--match-json", str(match_json), "--contact-sheets",
            "--preset", args.preset, "--crf", args.crf,
            "--default-pre", str(args.default_pre), "--default-post", str(args.default_post),
            "--assist-pre", str(args.assist_pre), "--assist-post", str(args.assist_post),
        ])
        payload["stages"].append({"name": "render_event", "status": "complete", "seconds": seconds})

        rendered = read_only_row(render_output / "reports" / "rendered-matches.csv")
        player = read_only_row(render_output / "reports" / "players.csv")
        clip = Path(rendered["output"]).resolve()
        reel = Path(player["output"]).resolve()
        clip_probe = probe_video(clip, full_decode=True)
        reel_probe = probe_video(reel, full_decode=True)
        contact_sheet = output / "audit" / "event-contact-sheet.jpg"
        build_audit_contact_sheet(clip, clip_probe["duration_seconds"], contact_sheet)

        payload.update({
            "status": "complete",
            "seconds": round(time.monotonic() - started, 3),
            "locations_csv": str(locations),
            "matches_csv": str(matches),
            "event": {
                key: event[key]
                for key in ("event_id", "title", "team", "number", "player", "action", "period", "clock", "source_seconds")
            },
            "source_probe": source_probe,
            "clip": {"path": str(clip), **clip_probe},
            "player_reel": {"path": str(reel), **reel_probe},
            "audit_contact_sheet": str(contact_sheet.resolve()),
            "mechanical_checks": {
                "event_identity_unique": True,
                "source_seconds_in_bounds": True,
                "clip_full_decode": True,
                "player_reel_full_decode": True,
                "no_platform_event_downloads": True,
            },
        })
        write_report(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        payload.update({
            "status": "needs_attention",
            "seconds": round(time.monotonic() - started, 3),
            "reason": str(exc),
            "resume_command": " ".join(sys.argv),
        })
        write_report(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
