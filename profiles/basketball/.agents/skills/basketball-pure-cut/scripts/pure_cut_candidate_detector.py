#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Sample:
    time: float
    luminance: float
    motion: float
    audio: float


@dataclass
class Candidate:
    start: float
    end: float
    reason: str
    score: float


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"缺少依赖 `{name}`")
    return path


def fmt_time(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    if millis:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_time(value: str) -> float:
    value = value.strip()
    if not value:
        return 0.0
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"invalid time: {value}")


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round((len(values) - 1) * q))))
    return values[idx]


def probe_duration(video: Path, ffprobe: str) -> float:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        capture=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def extract_audio(video: Path, ffmpeg: str, *, sample_rate: int, window_sec: float) -> list[float]:
    chunk_samples = max(1, int(sample_rate * window_sec))
    chunk_bytes = chunk_samples * 2
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "pipe:1",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    values: list[float] = []
    while True:
        raw = process.stdout.read(chunk_bytes)
        if not raw:
            break
        sample_count = len(raw) // 2
        if sample_count == 0:
            continue
        total = 0.0
        for off in range(0, sample_count * 2, 2):
            sample = int.from_bytes(raw[off : off + 2], "little", signed=True)
            total += sample * sample
        values.append(math.sqrt(total / sample_count) / 32768.0)
    _, stderr = process.communicate()
    if process.returncode != 0 and not values:
        sys.stderr.write(stderr.decode("utf-8", errors="replace"))
    return values


def extract_samples(
    video: Path,
    ffmpeg: str,
    *,
    fps: float,
    width: int,
    height: int,
    audio: list[float],
) -> list[Sample]:
    frame_size = width * height
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-an",
        "-vf",
        f"fps={fps},scale={width}:{height},format=gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None

    samples: list[Sample] = []
    prev: bytes | None = None
    frame_idx = 0
    while True:
        frame = process.stdout.read(frame_size)
        if not frame:
            break
        if len(frame) < frame_size:
            break
        luminance = sum(frame) / (frame_size * 255)
        if prev is None:
            motion = 1.0
        else:
            motion = sum(abs(a - b) for a, b in zip(frame, prev)) / (frame_size * 255)
        time = frame_idx / fps
        audio_idx = int(round(time))
        audio_value = audio[audio_idx] if 0 <= audio_idx < len(audio) else 0.0
        samples.append(Sample(time=time, luminance=luminance, motion=motion, audio=audio_value))
        prev = frame
        frame_idx += 1

    _, stderr = process.communicate()
    if process.returncode != 0 and not samples:
        sys.stderr.write(stderr.decode("utf-8", errors="replace"))
    return samples


def segment_flags(
    samples: list[Sample],
    flags: list[bool],
    *,
    min_duration: float,
    reason: str,
    score: float,
    pad_before: float = 0.0,
    pad_after: float = 0.0,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    start: float | None = None
    last_time = 0.0
    for sample, flagged in zip(samples, flags):
        last_time = sample.time
        if flagged and start is None:
            start = sample.time
        elif not flagged and start is not None:
            end = sample.time
            if end - start >= min_duration:
                candidates.append(
                    Candidate(
                        start=max(0.0, start - pad_before),
                        end=end + pad_after,
                        reason=reason,
                        score=score,
                    )
                )
            start = None
    if start is not None and last_time + 1 - start >= min_duration:
        candidates.append(
            Candidate(
                start=max(0.0, start - pad_before),
                end=last_time + 1 + pad_after,
                reason=reason,
                score=score,
            )
        )
    return candidates


def merge_candidates(candidates: list[Candidate], *, gap: float) -> list[Candidate]:
    candidates = [c for c in candidates if c.end > c.start]
    candidates.sort(key=lambda c: c.start)
    merged: list[Candidate] = []
    for item in candidates:
        if not merged or item.start > merged[-1].end + gap:
            merged.append(item)
            continue
        merged[-1].end = max(merged[-1].end, item.end)
        merged[-1].score = max(merged[-1].score, item.score)
        if item.reason not in merged[-1].reason:
            merged[-1].reason += "; " + item.reason
    return merged


def detect_candidates(samples: list[Sample], args: argparse.Namespace) -> tuple[list[Candidate], dict]:
    motions = [s.motion for s in samples[1:]]
    audios = [s.audio for s in samples]
    motion_p20 = percentile(motions, 0.20)
    motion_p35 = percentile(motions, 0.35)
    audio_p35 = percentile(audios, 0.35)

    black_flags = [s.luminance <= args.black_luminance for s in samples]
    freeze_flags = [s.motion <= max(args.freeze_motion, motion_p20 * 0.35) for s in samples]
    wait_motion_threshold = max(args.wait_motion, motion_p35)
    wait_audio_threshold = max(args.wait_audio, audio_p35)
    wait_flags = [
        s.motion <= wait_motion_threshold and s.audio <= wait_audio_threshold
        for s in samples
    ]

    candidates: list[Candidate] = []
    opening_cutoff = parse_time(args.drop_opening_until)
    if opening_cutoff > 0:
        candidates.append(
            Candidate(
                start=0.0,
                end=opening_cutoff,
                reason="开头热身/练球/赛前准备",
                score=0.95,
            )
        )
    candidates.extend(
        segment_flags(
            samples,
            black_flags,
            min_duration=args.min_black,
            reason="黑屏/暗场",
            score=1.0,
        )
    )
    candidates.extend(
        segment_flags(
            samples,
            freeze_flags,
            min_duration=args.min_freeze,
            reason="画面冻结/低变化",
            score=0.75,
        )
    )
    candidates.extend(
        segment_flags(
            samples,
            wait_flags,
            min_duration=args.min_wait,
            reason="低运动低音量候选等待段",
            score=0.55,
            pad_before=args.wait_pad_before,
            pad_after=args.wait_pad_after,
        )
    )
    stats = {
        "motion_p20": motion_p20,
        "motion_p35": motion_p35,
        "audio_p35": audio_p35,
        "wait_motion_threshold": wait_motion_threshold,
        "wait_audio_threshold": wait_audio_threshold,
    }
    return merge_candidates(candidates, gap=args.merge_gap), stats


def write_csv(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["index", "start", "end", "reason", "score"])
        writer.writeheader()
        for idx, item in enumerate(candidates, 1):
            writer.writerow(
                {
                    "index": f"{idx:02d}",
                    "start": fmt_time(item.start),
                    "end": fmt_time(item.end),
                    "reason": item.reason,
                    "score": f"{item.score:.2f}",
                }
            )


def write_report(path: Path, *, video: Path, duration: float, candidates: list[Candidate], stats: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input": str(video),
        "duration": duration,
        "stats": stats,
        "candidate_count": len(candidates),
        "candidate_deleted_duration": sum(c.end - c.start for c in candidates),
        "candidates": [
            {
                **asdict(item),
                "start_label": fmt_time(item.start),
                "end_label": fmt_time(item.end),
                "duration": item.end - item.start,
            }
            for item in candidates
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="识别纯享版候选删除段")
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-csv", type=Path, default=Path("output/pure-cut/reports/candidate_delete_list.csv"))
    parser.add_argument("--report", type=Path, default=Path("output/pure-cut/reports/candidate_delete_report.json"))
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=90)
    parser.add_argument("--black-luminance", type=float, default=0.06)
    parser.add_argument("--freeze-motion", type=float, default=0.002)
    parser.add_argument("--wait-motion", type=float, default=0.012)
    parser.add_argument("--wait-audio", type=float, default=0.012)
    parser.add_argument("--min-black", type=float, default=0.5)
    parser.add_argument("--min-freeze", type=float, default=4.0)
    parser.add_argument("--min-wait", type=float, default=10.0)
    parser.add_argument("--wait-pad-before", type=float, default=0.0)
    parser.add_argument("--wait-pad-after", type=float, default=0.0)
    parser.add_argument("--merge-gap", type=float, default=2.0)
    parser.add_argument(
        "--drop-opening-until",
        default="0",
        help="删除开头热身/练球到指定时间，例如 00:04:00；默认不启用",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    video = args.video.expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"视频不存在：{video}")
    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")
    duration = probe_duration(video, ffprobe)
    print("分析音频...")
    audio = extract_audio(video, ffmpeg, sample_rate=16000, window_sec=1.0)
    print(f"音频采样点：{len(audio)}")
    print("分析画面...")
    samples = extract_samples(
        video,
        ffmpeg,
        fps=args.fps,
        width=args.width,
        height=args.height,
        audio=audio,
    )
    print(f"画面采样点：{len(samples)}")
    candidates, stats = detect_candidates(samples, args)
    write_csv(args.output_csv, candidates)
    write_report(args.report, video=video, duration=duration, candidates=candidates, stats=stats)
    print(f"候选段：{len(candidates)}，候选删除时长：{sum(c.end - c.start for c in candidates):.1f}s")
    print(f"CSV：{args.output_csv}")
    print(f"报告：{args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
