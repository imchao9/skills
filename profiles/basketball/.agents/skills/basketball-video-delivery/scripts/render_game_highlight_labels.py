#!/usr/bin/env python3
"""Render per-segment player stats and event descriptions onto a game reel."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


MEMBER_RE = re.compile(
    r"^(?P<team>.+?)\s+(?P<number>\d+号)\s+(?P<player>.+?)\s+"
    r"(?P<action>2分命中|3分命中|助攻|抢断|盖帽)\s+"
    r"(?P<period>第[一二三四]节|加时\d*)\s+(?P<clock>\d{2}_\d{2})$"
)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def player_stats(rows: list[dict[str, str]]) -> dict[tuple[str, str], Counter[str]]:
    result: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        result[(row["team"], row["player"])][row["action"]] += 1
    return result


def stats_text(counter: Counter[str]) -> str:
    points = counter["2分命中"] * 2 + counter["3分命中"] * 3
    parts = [f"{points}分"]
    for action, suffix in (("助攻", "助攻"), ("抢断", "抢断"), ("盖帽", "盖帽")):
        if counter[action]:
            parts.append(f"{counter[action]}{suffix}")
    return "  ".join(parts)


def parse_members(value: str) -> list[dict[str, str]]:
    members = []
    for raw in value.split(" | "):
        match = MEMBER_RE.match(raw.strip())
        if match:
            members.append(match.groupdict())
    return members


def event_text(row: dict[str, str]) -> str:
    chosen = {
        "team": row["team"], "number": row["number"],
        "player": row["player"], "action": row["action"],
    }
    members = parse_members(row.get("members", ""))
    if chosen["action"] == "助攻":
        scores = [
            item for item in members
            if item["team"] == chosen["team"] and item["action"] in {"2分命中", "3分命中"}
        ]
        if scores:
            scorer = scores[0]
            return f'{chosen["player"]} 助攻 {scorer["player"]} {scorer["action"]}'
    return f'{chosen["player"]} {chosen["action"]}'


def font_path() -> str:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ):
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Chinese-capable font not found")


def write_label(path: Path, title: str, description: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (920, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 920, 150), radius=16, fill=(8, 12, 20, 205))
    draw.rectangle((0, 0, 10, 150), fill=(255, 178, 0, 255))
    title_font = ImageFont.truetype(font_path(), 38)
    event_font = ImageFont.truetype(font_path(), 34)
    draw.text((34, 22), title, font=title_font, fill=(255, 255, 255, 255))
    draw.text((34, 84), f"本次：{description}", font=event_font, fill=(255, 207, 84, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def escape_concat(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches-csv", type=Path, required=True)
    parser.add_argument("--selection-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()

    matches = read_csv(args.matches_csv)
    selection = read_csv(args.selection_csv)
    stats = player_stats(matches)
    work = args.work_dir or args.output.with_name(args.output.stem + "_labeled_work")
    labels = work / "labels"
    segments = work / "segments"
    segments.mkdir(parents=True, exist_ok=True)

    rendered: list[Path] = []
    for index, row in enumerate(selection, 1):
        source = Path(row["output"])
        if not source.is_file():
            raise FileNotFoundError(source)
        label = labels / f"label_{index:03d}.png"
        segment = segments / f"segment_{index:03d}.mp4"
        title = f'{row["number"]} {row["player"]}｜本场 {stats_text(stats[(row["team"], row["player"])])}'
        write_label(label, title, event_text(row))
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-loop", "1", "-i", str(label),
            "-filter_complex", "[0:v][1:v]overlay=32:32:format=auto:shortest=1[v]",
            "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-shortest", str(segment),
        ])
        rendered.append(segment)

    concat = work / "concat.txt"
    concat.write_text("\n".join(f"file '{escape_concat(path)}'" for path in rendered) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-c", "copy", str(args.output),
    ])
    print(f"segments: {len(rendered)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
