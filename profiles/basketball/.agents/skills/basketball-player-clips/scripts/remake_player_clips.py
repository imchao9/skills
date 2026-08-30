#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ACTION_KEYWORDS = ["2分命中", "3分命中", "助攻", "抢断", "盖帽"]
SKIP_NAME_PARTS = ["个人精彩集锦", "全场精彩集锦", "精彩回放", "纯净版"]
HASH_FPS = 2
HASH_W = 17
HASH_H = 16
PLAYER_REEL_ACTION_PRIORITY = {
    "3分命中": 100,
    "盖帽": 94,
    "抢断": 90,
    "2分命中": 86,
    "助攻": 82,
}
PERIOD_ORDER = {
    "第一节": 1,
    "第二节": 2,
    "第三节": 3,
    "第四节": 4,
}


@dataclass
class ClipItem:
    path: Path
    team: str
    number: str
    player: str
    action: str
    period: str
    clock: str


@dataclass
class MatchResult:
    item: ClipItem
    old_start: float
    event_time: float
    new_start: float
    new_end: float
    avg_hamming: float
    output: Path
    window_strategy: str = "legacy-event-offset"


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Missing required tool: {name}")
    return path


def fmt_time(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    h = whole // 3600
    m = (whole % 3600) // 60
    s = whole % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


def safe_name(value: str) -> str:
    value = value.strip() or "未识别"
    return re.sub(r"[/:]", "_", value)


def clock_seconds(value: str) -> int:
    if not value:
        return -1
    parts = value.replace("-", "_").replace(":", "_").split("_")
    if len(parts) != 2:
        return -1
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return -1


def period_rank(value: str) -> int:
    if value in PERIOD_ORDER:
        return PERIOD_ORDER[value]
    match = re.fullmatch(r"加时(\d+)", value)
    if match:
        return 4 + int(match.group(1))
    if value == "加时":
        return 5
    return 999


def game_order_key(item: "MatchResult") -> tuple[int, int, float]:
    # Basketball game clocks count down within each period.
    return (
        period_rank(item.item.period),
        -clock_seconds(item.item.clock),
        item.event_time,
    )


def personal_reel_priority(item: "MatchResult") -> tuple[int, float, float]:
    return (
        PLAYER_REEL_ACTION_PRIORITY.get(item.item.action, 0),
        -item.avg_hamming,
        item.event_time,
    )


def dedupe_player_reel_items(items: list["MatchResult"], *, min_gap: float = 2.0) -> list["MatchResult"]:
    sorted_items = sorted(items, key=game_order_key)
    groups: list[list[MatchResult]] = []
    current: list[MatchResult] = []
    current_end = -math.inf
    current_period = 999
    for item in sorted_items:
        rank = period_rank(item.item.period)
        overlaps_current = item.new_start <= current_end + min_gap
        if current and rank == current_period and overlaps_current:
            current.append(item)
            current_end = max(current_end, item.new_end)
        else:
            if current:
                groups.append(current)
            current = [item]
            current_end = item.new_end
            current_period = rank
    if current:
        groups.append(current)
    chosen = [max(group, key=personal_reel_priority) for group in groups]
    return sorted(chosen, key=game_order_key)


def probe_duration(video: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nk=1:nw=1",
            str(video),
        ],
        capture=True,
    )
    return float(result.stdout.decode().strip())


def should_skip(path: Path) -> bool:
    name = path.name
    return any(part in name for part in SKIP_NAME_PARTS)


def parse_clip_name(path: Path) -> ClipItem:
    stem = path.stem
    tokens = stem.split()
    action_idx = None
    action = ""
    for idx, token in enumerate(tokens):
        if token in ACTION_KEYWORDS:
            action_idx = idx
            action = token
            break
    if action_idx is None:
        return ClipItem(path, "", "", "未识别", "未识别", "", "")

    before = tokens[:action_idx]
    after = tokens[action_idx + 1 :]
    team = before[0] if before else ""
    number = ""
    player_parts = before[1:] if len(before) > 1 else []
    if player_parts and player_parts[0].endswith("号"):
        number = player_parts[0]
        player_parts = player_parts[1:]
    player = "".join(player_parts).strip() or "未识别"
    period = after[0] if after else ""
    clock = after[1] if len(after) > 1 else ""
    return ClipItem(path, team, number, player, action, period, clock)


def collect_clips(clips_dir: Path, player_name: str | None) -> list[ClipItem]:
    items: list[ClipItem] = []
    for path in sorted(clips_dir.glob("*.mp4")):
        if should_skip(path):
            continue
        item = parse_clip_name(path)
        if item.action == "未识别" or item.player == "未识别" or not item.period or not item.clock:
            continue
        if player_name and item.player != player_name:
            continue
        items.append(item)
    return items


def dhash_frame(frame: bytes) -> int:
    bits = 0
    bit_pos = 0
    for row in range(HASH_H):
        base = row * HASH_W
        for col in range(HASH_W - 1):
            if frame[base + col] > frame[base + col + 1]:
                bits |= 1 << bit_pos
            bit_pos += 1
    return bits


def extract_hashes(video: Path) -> list[int]:
    frame_size = HASH_W * HASH_H
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-an",
        "-vf",
        f"fps={HASH_FPS},scale={HASH_W}:{HASH_H},format=gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    hashes: list[int] = []
    while True:
        frame = process.stdout.read(frame_size)
        if not frame:
            break
        if len(frame) < frame_size:
            break
        hashes.append(dhash_frame(frame))
    _, stderr = process.communicate()
    if process.returncode != 0:
        sys.stderr.write(stderr.decode("utf-8", errors="replace"))
        raise SystemExit(process.returncode)
    return hashes


def best_offset(source_hashes: list[int], clip_hashes: list[int]) -> tuple[int, float]:
    if len(clip_hashes) > len(source_hashes):
        raise ValueError("clip longer than source hash stream")
    best_idx = 0
    best_score = float("inf")
    clip_len = len(clip_hashes)
    for idx in range(0, len(source_hashes) - clip_len + 1):
        total = 0
        for a, b in zip(source_hashes[idx : idx + clip_len], clip_hashes):
            total += (a ^ b).bit_count()
            if total >= best_score * clip_len:
                break
        avg = total / clip_len
        if avg < best_score:
            best_score = avg
            best_idx = idx
    return best_idx, best_score


def render_clip(
    source: Path,
    start: float,
    end: float,
    output: Path,
    *,
    preset: str,
    crf: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{end - start:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            crf,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-avoid_negative_ts",
            "make_zero",
            str(output),
        ]
    )


def find_font() -> str:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ):
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Chinese-capable font not found")


def render_labeled_clip(source: Path, start: float, end: float, output: Path, item: ClipItem, *, preset: str, crf: str) -> None:
    from PIL import Image, ImageDraw, ImageFont
    output.parent.mkdir(parents=True, exist_ok=True)
    label = output.with_suffix(".label.png")
    image = Image.new("RGBA", (1100, 150), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 1100, 150), radius=16, fill=(8, 12, 20, 210))
    draw.rectangle((0, 0, 10, 150), fill=(255, 178, 0, 255))
    font = find_font()
    draw.text((34, 20), f"{item.team}｜{item.number or '-号'} {item.player}", font=ImageFont.truetype(font, 36), fill="white")
    draw.text((34, 82), f"本次：{item.action}｜{item.period} {item.clock}", font=ImageFont.truetype(font, 32), fill=(255, 207, 84, 255))
    image.save(label)
    try:
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}",
            "-i", str(source), "-loop", "1", "-i", str(label), "-t", f"{end-start:.3f}",
            "-filter_complex", "[0:v][1:v]overlay=32:32:format=auto:shortest=1[v]",
            "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", preset,
            "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(output),
        ])
    finally:
        label.unlink(missing_ok=True)


def is_valid_video(video: Path) -> bool:
    if not video.exists() or video.stat().st_size == 0:
        return False
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nk=1:nw=1",
            str(video),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return False
    try:
        return float(result.stdout.decode().strip()) > 0
    except ValueError:
        return False


def concat_outputs(outputs: list[Path], target: Path) -> None:
    if not outputs:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    concat_file = target.with_suffix(".concat.txt")
    concat_file.write_text(
        "\n".join("file '" + str(path.resolve()).replace("'", "'\\''") + "'" for path in outputs)
        + "\n",
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(target),
        ]
    )


def contact_sheet(video: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            "fps=1/18,scale=320:-1,tile=6x4",
            "-frames:v",
            "1",
            str(output),
        ]
    )


def write_reports(results: list[MatchResult], output_dir: Path, *, labeled: bool) -> None:
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    matches_path = reports_dir / "matches.csv"
    with matches_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "clip",
                "team",
                "number",
                "player",
                "action",
                "period",
                "clock",
                "old_start",
                "event_time",
                "new_start",
                "new_end",
                "new_duration",
                "avg_hamming",
                "window_strategy",
                "output",
                "data_label_status",
            ],
        )
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "clip": str(item.item.path),
                    "team": item.item.team,
                    "number": item.item.number,
                    "player": item.item.player,
                    "action": item.item.action,
                    "period": item.item.period,
                    "clock": item.item.clock,
                    "old_start": fmt_time(item.old_start),
                    "event_time": fmt_time(item.event_time),
                    "new_start": fmt_time(item.new_start),
                    "new_end": fmt_time(item.new_end),
                    "new_duration": f"{item.new_end - item.new_start:.3f}",
                    "avg_hamming": f"{item.avg_hamming:.3f}",
                    "window_strategy": item.window_strategy,
                    "output": str(item.output),
                    "data_label_status": "data_labeled" if labeled else "raw_intermediate",
                }
            )

    by_player_path = reports_dir / "players.csv"
    counts: dict[str, int] = {}
    for item in results:
        counts[item.item.player] = counts.get(item.item.player, 0) + 1
    with by_player_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["player", "clip_count"])
        writer.writeheader()
        for player, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
            writer.writerow({"player": player, "clip_count": count})


def build_reels(results: list[MatchResult], output_dir: Path, *, make_contact_sheets: bool) -> None:
    sorted_results = sorted(results, key=game_order_key)
    full_reel = output_dir / "比赛精彩集锦_比赛时间顺序.mp4"
    concat_outputs([item.output for item in sorted_results], full_reel)
    if make_contact_sheets and full_reel.exists():
        contact_sheet(full_reel, output_dir / "debug/比赛精彩集锦_比赛时间顺序_contact_sheet.jpg")

    players: dict[str, list[MatchResult]] = {}
    for item in sorted_results:
        players.setdefault(item.item.player, []).append(item)
    reels_dir = output_dir / "个人精彩集锦"
    for player, player_items in sorted(players.items()):
        target = reels_dir / f"{safe_name(player)}-个人精彩集锦.mp4"
        deduped_player_items = dedupe_player_reel_items(player_items)
        concat_outputs([item.output for item in deduped_player_items], target)
        if make_contact_sheets and target.exists():
            contact_sheet(target, output_dir / "debug/个人精彩集锦" / f"{safe_name(player)}.jpg")


def build_selected_reels(
    results: list[MatchResult],
    output_dir: Path,
    *,
    make_contact_sheets: bool,
    build_full_reel: bool,
    build_player_reels: bool,
    labeled: bool,
) -> None:
    sorted_results = sorted(results, key=game_order_key)
    if build_full_reel:
        full_reel = output_dir / ("比赛精彩集锦_比赛时间顺序_数据标注版.mp4" if labeled else "比赛精彩集锦_比赛时间顺序_原始中间版.mp4")
        concat_outputs([item.output for item in sorted_results], full_reel)
        if make_contact_sheets and full_reel.exists():
            contact_sheet(full_reel, output_dir / "debug/比赛精彩集锦_比赛时间顺序_contact_sheet.jpg")

    if build_player_reels:
        players: dict[str, list[MatchResult]] = {}
        for item in sorted_results:
            players.setdefault(item.item.player, []).append(item)
        reels_dir = output_dir / "个人精彩集锦"
        for player, player_items in sorted(players.items()):
            target = reels_dir / f"{safe_name(player)}-个人精彩集锦_{'数据标注版' if labeled else '原始中间版'}.mp4"
            deduped_player_items = dedupe_player_reel_items(player_items)
            concat_outputs([item.output for item in deduped_player_items], target)
            if make_contact_sheets and target.exists():
                contact_sheet(target, output_dir / "debug/个人精彩集锦" / f"{safe_name(player)}.jpg")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remake basketball player clips from existing event clips")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--clips-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--old-event-offset", type=float, default=7.0)
    parser.add_argument(
        "--window-strategy", choices=("reference-clip", "event-offset"),
        default="reference-clip",
        help="Default covers the matched reference clip; event-offset is legacy and requires review.",
    )
    parser.add_argument("--reference-lead-in", type=float, default=5.0)
    parser.add_argument("--default-pre", type=float, default=15.0)
    parser.add_argument("--default-post", type=float, default=8.0)
    parser.add_argument("--assist-pre", type=float, default=15.0)
    parser.add_argument("--assist-post", type=float, default=8.0)
    parser.add_argument("--player-name")
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    parser.add_argument("--contact-sheets", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip rendering existing valid clip outputs")
    parser.add_argument("--skip-full-reel", action="store_true", help="Do not build the all-event full-game reel")
    parser.add_argument("--skip-player-reels", action="store_true", help="Do not build per-player reels")
    parser.add_argument("--raw-no-overlay", action="store_true", help="Create unlabeled intermediates only.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    require_tool("ffmpeg")
    require_tool("ffprobe")
    source = args.source.expanduser().resolve()
    clips_dir = args.clips_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")
    if not clips_dir.exists():
        raise SystemExit(f"Clips dir not found: {clips_dir}")

    items = collect_clips(clips_dir, args.player_name)
    if not items:
        raise SystemExit("No event clips found")

    source_duration = probe_duration(source)
    print(f"Extract source hashes: {source}", flush=True)
    source_hashes = extract_hashes(source)
    print(f"Source samples: {len(source_hashes)}; event clips: {len(items)}", flush=True)

    results: list[MatchResult] = []
    clips_output_dir = output_dir / "个人精彩片段"
    for idx, item in enumerate(items, 1):
        print(f"[{idx}/{len(items)}] {item.path.name}", flush=True)
        clip_hashes = extract_hashes(item.path)
        offset_idx, score = best_offset(source_hashes, clip_hashes)
        old_start = offset_idx / HASH_FPS
        reference_duration = probe_duration(item.path)
        event_time = old_start + min(args.old_event_offset, reference_duration)
        if item.action == "助攻":
            pre, post = args.assist_pre, args.assist_post
        else:
            pre, post = args.default_pre, args.default_post
        if args.window_strategy == "reference-clip":
            new_start = max(0.0, old_start - args.reference_lead_in)
            new_end = min(source_duration, old_start + reference_duration)
        else:
            new_start = max(0.0, event_time - pre)
            new_end = min(source_duration, event_time + post)
        labeled = not args.raw_no_overlay
        output = clips_output_dir / f"{item.path.stem}_{'数据标注版' if labeled else '原始中间版'}.mp4"
        print(
            f"  event={fmt_time(event_time)} window={fmt_time(new_start)}-{fmt_time(new_end)} "
            f"action={item.action} score={score:.2f}",
            flush=True,
        )
        if args.resume and is_valid_video(output):
            print(f"  skip existing valid output: {output}", flush=True)
        else:
            if labeled:
                render_labeled_clip(source, new_start, new_end, output, item, preset=args.preset, crf=args.crf)
            else:
                render_clip(source, new_start, new_end, output, preset=args.preset, crf=args.crf)
        results.append(
            MatchResult(
                item=item,
                old_start=old_start,
                event_time=event_time,
                new_start=new_start,
                new_end=new_end,
                avg_hamming=score,
                output=output,
                window_strategy=args.window_strategy,
            )
        )

    write_reports(results, output_dir, labeled=not args.raw_no_overlay)
    build_selected_reels(
        results,
        output_dir,
        make_contact_sheets=args.contact_sheets,
        build_full_reel=not args.skip_full_reel,
        build_player_reels=not args.skip_player_reels,
        labeled=not args.raw_no_overlay,
    )
    print(f"Output dir: {output_dir}")
    print(f"Matches report: {output_dir / 'reports/matches.csv'}")
    print(f"Full highlight reel: {output_dir / '比赛精彩集锦_比赛时间顺序.mp4'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
