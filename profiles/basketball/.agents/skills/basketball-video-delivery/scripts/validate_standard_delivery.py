#!/usr/bin/env python3
"""Validate the four-item default basketball delivery package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import subprocess
from pathlib import Path
from typing import Any


def media_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            "stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"ffprobe failed: {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    video = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    duration = float(data.get("format", {}).get("duration") or 0)
    size = int(data.get("format", {}).get("size") or 0)
    if not video or duration <= 0 or size <= 0:
        raise ValueError(f"invalid media: {path}")
    return {
        "path": str(path.resolve()),
        "bytes": size,
        "duration_seconds": round(duration, 3),
        "codec": video.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
    }


def full_decode(path: Path) -> None:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError(f"full decode failed: {path}: {result.stderr.strip()}")


def files(directory: Path, pattern: str) -> list[Path]:
    return sorted(
        path for path in directory.glob(pattern)
        if path.is_file() and not path.name.startswith(".")
    )


def first_existing(candidates: list[Path]) -> Path | None:
    return next((path for path in candidates if path.is_file()), None)


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--full-decode",
        action="store_true",
        help="Fully decode every required video before marking the package complete.",
    )
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    output = run_dir / "output"
    errors: list[str] = []

    pure_candidates = [
        *files(output / "pure-cut", "*纯享版_1080p.mp4"),
        *files(output / "pure-cut", "*纯享版*完整.mp4"),
        *files(output / "pure-cut", "*纯享版_720p.mp4"),
    ]
    pure = first_existing(pure_candidates)
    if not pure:
        errors.append("missing pure cut")

    player_dirs = [
        output / "player-clips-full-source" / "个人精彩集锦",
        output / "player-clips-front15" / "个人精彩集锦",
    ]
    player_reels: list[Path] = []
    player_dir: Path | None = None
    for directory in player_dirs:
        raw_reels = files(directory, "*.mp4")
        player_reels = [path for path in raw_reels if "数据标注版" in path.name]
        if raw_reels and not player_reels:
            errors.append(f"viewer-facing player reels are not data-labeled: {directory}")
        if player_reels:
            player_dir = directory
            break
    if not player_reels:
        errors.append("missing player reels")
    expected_player_count: int | None = None
    if player_dir:
        player_reports = player_dir.parent / "reports"
        players_csv = player_reports / "players.csv"
        if not players_csv.is_file():
            errors.append(f"missing players.csv: {players_csv}")
        else:
            player_rows = csv_rows(players_csv)
            expected_player_count = len(player_rows)
            if any(row.get("data_label_status") != "data_labeled" for row in player_rows):
                errors.append(f"players.csv contains non-deliverable raw outputs: {players_csv}")
            if len(player_reels) != expected_player_count:
                errors.append(
                    f"player reel count mismatch: expected {expected_player_count}, "
                    f"found {len(player_reels)}"
                )
        rendered_matches = player_reports / "rendered-matches.csv"
        location_audit = player_reports / "event-location-audit.json"
        stat_audit = player_reports / "event-stat-audit.json"
        action_evidence = player_reports / "action-evidence.json"
        for label, path in (("location", location_audit), ("statistics", stat_audit)):
            if not path.is_file():
                errors.append(f"missing player {label} audit: {path}")
                continue
            audit = json.loads(path.read_text(encoding="utf-8"))
            if audit.get("status") != "complete" or audit.get("blockers") or audit.get("errors"):
                errors.append(f"player {label} audit did not pass: {path}")
        if not action_evidence.is_file():
            errors.append(f"missing player action evidence: {action_evidence}")
        elif not rendered_matches.is_file():
            errors.append(f"missing rendered player matches: {rendered_matches}")
        else:
            evidence = json.loads(action_evidence.read_text(encoding="utf-8"))
            scoring_rows = [
                row for row in csv_rows(rendered_matches)
                if row.get("action") in {"2分命中", "3分命中"}
            ]
            expected_hash = hashlib.sha256(rendered_matches.read_bytes()).hexdigest()
            if evidence.get("status") != "complete":
                errors.append(f"player action evidence did not complete: {action_evidence}")
            if evidence.get("matches_csv_sha256") != expected_hash:
                errors.append(f"player action evidence is stale: {action_evidence}")
            if evidence.get("scoring_event_count") != len(scoring_rows):
                errors.append("player action evidence count does not match scoring rows")
            for item in evidence.get("items") or []:
                frame = Path(str(item.get("evidence_frame") or ""))
                if not frame.is_file() or frame.stat().st_size <= 0:
                    errors.append(f"missing player action evidence frame: {frame}")

    game_candidates = files(output / "game-highlight", "*数据标注版.mp4")
    game = first_existing(game_candidates)
    if not game:
        errors.append("missing viewer-facing game highlight")

    poster_dir = output / "球评海报"
    poster_html = first_existing(files(poster_dir, "*_球评海报.html"))
    poster_png = first_existing(files(poster_dir, "*_球评海报.png"))
    audit_report = first_existing(files(poster_dir, "*_球评审校.json"))
    commentary = first_existing(files(output, "球评_*.md"))
    if not commentary:
        errors.append("missing commentary Markdown")
    if not poster_html:
        errors.append("missing commentary HTML")
    if not poster_png:
        errors.append("missing commentary PNG")
    if not audit_report:
        errors.append("missing commentary fact-audit report")
    else:
        audit = json.loads(audit_report.read_text(encoding="utf-8"))
        if audit.get("status") != "passed" or audit.get("errors"):
            errors.append(f"commentary fact audit did not pass: {audit_report}")

    manifest: dict[str, Any] = {
        "status": "failed",
        "run_dir": str(run_dir),
        "default_package": {
            "pure_cut": media_probe(pure) if pure else None,
            "player_reels": [],
            "game_highlight": media_probe(game) if game else None,
            "commentary": {
                "markdown": str(commentary.resolve()) if commentary else None,
                "html": str(poster_html.resolve()) if poster_html else None,
                "png": str(poster_png.resolve()) if poster_png else None,
                "audit_report": str(audit_report.resolve()) if audit_report else None,
            },
        },
        "errors": errors,
    }

    for path in player_reels:
        try:
            manifest["default_package"]["player_reels"].append(media_probe(path))
        except ValueError as exc:
            errors.append(str(exc))

    if args.full_decode:
        decode_paths = [path for path in (pure, game) if path]
        decode_paths.extend(player_reels)
        for path in decode_paths:
            try:
                full_decode(path)
            except ValueError as exc:
                errors.append(str(exc))
        manifest["full_decode"] = {
            "required": True,
            "checked_videos": len(decode_paths),
            "status": "complete" if not any("full decode failed" in error for error in errors) else "failed",
        }
    else:
        manifest["full_decode"] = {"required": False, "checked_videos": 0, "status": "skipped"}

    pure_info = manifest["default_package"]["pure_cut"]
    if pure_info and (pure_info["width"], pure_info["height"]) != (1920, 1080):
        errors.append(
            f"pure cut must be 1920x1080, got "
            f"{pure_info['width']}x{pure_info['height']}"
        )

    game_info = manifest["default_package"]["game_highlight"]
    if game_info and (game_info["width"], game_info["height"]) != (1920, 1080):
        errors.append(
            f"game highlight must be 1920x1080, got "
            f"{game_info['width']}x{game_info['height']}"
        )

    for label, path in (
        ("commentary Markdown", commentary),
        ("commentary HTML", poster_html),
        ("commentary PNG", poster_png),
    ):
        if path and path.stat().st_size <= 0:
            errors.append(f"empty {label}: {path}")
    if poster_html and "data:image/" not in poster_html.read_text(encoding="utf-8"):
        errors.append(f"commentary HTML is not standalone: {poster_html}")
    if poster_png:
        try:
            poster_width, poster_height = png_dimensions(poster_png)
            manifest["default_package"]["commentary"]["png_width"] = poster_width
            manifest["default_package"]["commentary"]["png_height"] = poster_height
            if poster_width != 1080:
                errors.append(f"commentary PNG must be 1080px wide, got {poster_width}")
        except ValueError as exc:
            errors.append(str(exc))

    manifest["counts"] = {
        "pure_cut": int(pure is not None),
        "player_reels": len(player_reels),
        "expected_player_reels": expected_player_count,
        "game_highlight": int(game is not None),
        "commentary_markdown": int(commentary is not None),
        "commentary_html": int(poster_html is not None),
        "commentary_png": int(poster_png is not None),
    }
    manifest["status"] = "complete" if not errors else "failed"

    report = args.out or output / "delivery" / "standard-delivery-manifest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "run_dir": manifest["run_dir"],
        "counts": manifest["counts"],
        "errors": manifest["errors"],
        "report": str(report.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
