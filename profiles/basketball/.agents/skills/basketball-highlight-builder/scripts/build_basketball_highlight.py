#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


EVENT_PATTERN = re.compile(
    r"^(?P<team>.+?)\s+"
    r"(?P<number>\d+)号\s+"
    r"(?P<player>.+?)\s+"
    r"(?P<event>2分命中|3分命中|助攻|抢断|盖帽)\s+"
    r"(?P<period>第一节|第二节|第三节|第四节|加时\d+)\s+"
    r"(?P<minute>\d{2})[_:](?P<second>\d{2})\.mp4$"
)

EVENT_WEIGHTS = {"3分命中": 7, "2分命中": 6, "盖帽": 5, "抢断": 5, "助攻": 4}
DEDUP_WEIGHTS = {"3分命中": 50, "2分命中": 40, "盖帽": 35, "抢断": 30, "助攻": 20}
EVENT_POINTS = {"3分命中": 3, "2分命中": 2}
PERIOD_ORDER = {"第一节": 1, "第二节": 2, "第三节": 3, "第四节": 4}


@dataclass(frozen=True)
class Clip:
    team: str
    number: int
    player: str
    event: str
    period: str
    period_index: int
    clock: str
    clock_seconds: int
    points: int
    score: int
    duration_seconds: float
    source_path: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Build basketball highlight videos from event clips.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--clip-dir", action="append", default=[])
    parser.add_argument("--team")
    parser.add_argument("--target-seconds", type=float, default=0, help="0 means keep all clips.")
    parser.add_argument("--trim-tail-seconds", type=float, default=8)
    parser.add_argument("--dedupe-window-seconds", type=int, default=0)
    parser.add_argument("--priority-player")
    parser.add_argument("--clock-order", choices=("asc", "desc"), default="desc")
    parser.add_argument("--exclude-file")
    parser.add_argument("--plan-json", default="data/highlight_plan.json")
    parser.add_argument("--concat-file", default="data/highlight_concat.txt")
    parser.add_argument("--output", default="output/highlight.mp4")
    parser.add_argument("--overlay-labels", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    clips = discover(root, args.clip_dir or ["个人集锦"])
    if not clips:
        raise SystemExit(
            "no event clips matched the filename contract; expected a name ending in "
            "'<节次> MM:SS.mp4' or '<节次> MM_SS.mp4'"
        )
    if args.team:
        clips = [clip for clip in clips if clip.team == args.team]
        if not clips:
            raise SystemExit(f"no parsed clips found for team: {args.team}")
    if args.exclude_file:
        clips = exclude(clips, root / args.exclude_file)
    clips = dedupe(clips, args.dedupe_window_seconds, args.priority_player)
    clips = select(clips, args.target_seconds, args.trim_tail_seconds)
    clips = sort_clips(clips, args.clock_order)

    plan_path = root / args.plan_json
    concat_path = root / args.concat_file
    output_path = root / args.output
    write_plan(clips, plan_path, args)
    write_concat(clips, root, concat_path)

    if not args.plan_only:
        build_video(
            clips,
            root,
            concat_path,
            output_path,
            trim_tail_seconds=args.trim_tail_seconds,
            overlay_labels=args.overlay_labels,
        )

    print(
        json.dumps(
            {
                "clips": len(clips),
                "duration_seconds": round(sum(effective_duration(c, args.trim_tail_seconds) for c in clips), 3),
                "plan_json": str(plan_path),
                "output": str(output_path) if not args.plan_only else None,
            },
            ensure_ascii=False,
        )
    )


def discover(root: Path, clip_dirs: Iterable[str]) -> list[Clip]:
    clips: list[Clip] = []
    for clip_dir in clip_dirs:
        for path in sorted((root / clip_dir).rglob("*.mp4")):
            clip = parse_clip(root, path)
            if clip:
                clips.append(clip)
    return sort_clips(clips, "asc")


def parse_clip(root: Path, path: Path) -> Clip | None:
    match = EVENT_PATTERN.match(path.name)
    if not match:
        return None
    data = match.groupdict()
    minute = int(data["minute"])
    second = int(data["second"])
    event = data["event"]
    return Clip(
        team=data["team"],
        number=int(data["number"]),
        player=data["player"],
        event=event,
        period=data["period"],
        period_index=period_index(data["period"]),
        clock=f"{minute:02d}:{second:02d}",
        clock_seconds=minute * 60 + second,
        points=EVENT_POINTS.get(event, 0),
        score=EVENT_WEIGHTS[event],
        duration_seconds=round(probe_duration(path), 3),
        source_path=path.relative_to(root).as_posix(),
    )


def exclude(clips: list[Clip], path: Path) -> list[Clip]:
    if not path.exists():
        return clips
    excluded = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    return [clip for clip in clips if clip.source_path not in excluded]


def dedupe(clips: list[Clip], window_seconds: int, priority_player: str | None) -> list[Clip]:
    if window_seconds <= 0:
        return clips
    selected: list[Clip] = []
    by_period: dict[int, list[Clip]] = {}
    for clip in clips:
        by_period.setdefault(clip.period_index, []).append(clip)
    for period_clips in by_period.values():
        cluster: list[Clip] = []
        for clip in sorted(period_clips, key=lambda item: item.clock_seconds):
            if not cluster or clip.clock_seconds - cluster[-1].clock_seconds <= window_seconds:
                cluster.append(clip)
                continue
            selected.append(best_duplicate(cluster, priority_player))
            cluster = [clip]
        if cluster:
            selected.append(best_duplicate(cluster, priority_player))
    return selected


def best_duplicate(clips: list[Clip], priority_player: str | None) -> Clip:
    def key(clip: Clip) -> tuple[int, int, int, int]:
        player_bonus = 25 if priority_player and clip.player == priority_player else 0
        return (DEDUP_WEIGHTS[clip.event] + player_bonus, clip.score, clip.points, -clip.clock_seconds)

    return max(clips, key=key)


def select(clips: list[Clip], target_seconds: float, trim_tail_seconds: float) -> list[Clip]:
    if target_seconds <= 0:
        return clips
    ranked = sorted(clips, key=lambda item: (item.score, item.points, -item.period_index, item.clock_seconds), reverse=True)
    chosen: list[Clip] = []
    total = 0.0
    for clip in ranked:
        duration = effective_duration(clip, trim_tail_seconds)
        if chosen and total + duration > target_seconds * 1.08:
            continue
        chosen.append(clip)
        total += duration
        if total >= target_seconds:
            break
    return chosen


def sort_clips(clips: list[Clip], clock_order: str) -> list[Clip]:
    multiplier = 1 if clock_order == "asc" else -1
    return sorted(clips, key=lambda item: (item.period_index, item.clock_seconds * multiplier, item.team, item.player))


def write_plan(clips: list[Clip], path: Path, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trim_tail_seconds": args.trim_tail_seconds,
        "dedupe_window_seconds": args.dedupe_window_seconds,
        "priority_player": args.priority_player,
        "clock_order": args.clock_order,
        "clips": [asdict(clip) | {"label": format_label(clip)} for clip in clips],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_concat(clips: list[Clip], root: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{escape_concat_path((root / clip.source_path).resolve())}'" for clip in clips]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_video(
    clips: list[Clip],
    root: Path,
    concat_file: Path,
    output_path: Path,
    trim_tail_seconds: float,
    overlay_labels: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paths = read_concat_paths(concat_file)
    label_paths = []
    if overlay_labels:
        label_paths = write_label_images([format_label(clip) for clip in clips], output_path.parent / f"{output_path.stem}_labels")

    inputs = [arg for path in paths for arg in ("-i", str(path))]
    for label_path in label_paths:
        inputs.extend(("-loop", "1", "-framerate", "24", "-i", str(label_path)))

    streams = "".join(
        trim_filter(index, path, trim_tail_seconds, len(paths) + index if label_paths else None)
        for index, path in enumerate(paths)
    )
    concat_inputs = "".join(f"[v{index}][a{index}]" for index in range(len(paths)))
    command = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        f"{streams}{concat_inputs}concat=n={len(paths)}:v=1:a=1[outv][outa]",
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        str(output_path),
    ]
    subprocess.run(command, cwd=root, check=True)


def trim_filter(index: int, path: Path, trim_tail_seconds: float, label_index: int | None) -> str:
    duration = max(probe_duration(path) - trim_tail_seconds, 0.1)
    if label_index is None:
        video = f"[{index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,fps=24[v{index}];"
    else:
        video = (
            f"[{index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,fps=24[base{index}];"
            f"[{label_index}:v]format=rgba[label{index}];"
            f"[base{index}][label{index}]overlay=32:32:format=auto:shortest=1[v{index}];"
        )
    return video + f"[{index}:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a{index}];"


def write_label_images(labels: list[str], output_dir: Path) -> list[Path]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError("Install Pillow or run with `uv run --with Pillow`.") from error
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(find_font(), 38)
    paths: list[Path] = []
    for index, label in enumerate(labels):
        image = Image.new("RGBA", (640, 92), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 640, 92), radius=10, fill=(0, 0, 0, 178))
        draw.text((24, 23), label, font=font, fill=(255, 255, 255, 255))
        path = output_dir / f"label_{index + 1:03d}.png"
        image.save(path)
        paths.append(path)
    return paths


def format_label(clip: Clip) -> str:
    return f"{clip.number}号 {clip.player} {clip.event}"


def read_concat_paths(path: Path) -> list[Path]:
    paths: list[Path] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("file "):
            parsed = shlex.split(stripped.removeprefix("file ").strip())
            if parsed:
                paths.append(Path(parsed[0]))
    return paths


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip() or 0)


def find_font() -> str:
    for candidate in (
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ):
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("No Chinese-capable font found.")


def period_index(period: str) -> int:
    if period in PERIOD_ORDER:
        return PERIOD_ORDER[period]
    if period.startswith("加时"):
        return 4 + int(period.removeprefix("加时"))
    return 99


def effective_duration(clip: Clip, trim_tail_seconds: float) -> float:
    return max(clip.duration_seconds - trim_tail_seconds, 0.1)


def escape_concat_path(path: Path) -> str:
    return str(path).replace("'", r"'\''")


if __name__ == "__main__":
    main()
