#!/usr/bin/env python3
"""Assemble ordered replay segments, normalizing only when stream formats differ."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of", "json", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    if float(data.get("format", {}).get("duration") or 0) <= 0:
        raise RuntimeError(f"invalid duration for {path}")
    return data


def stream_signature(info: dict[str, Any]) -> tuple[Any, ...]:
    video = next((stream for stream in info["streams"] if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in info["streams"] if stream.get("codec_type") == "audio"), {})
    return (
        video.get("codec_name"),
        video.get("width"),
        video.get("height"),
        video.get("r_frame_rate"),
        audio.get("codec_name"),
        audio.get("sample_rate"),
        audio.get("channels"),
    )


def ffconcat_quote(path: Path) -> str:
    return "'" + str(path.resolve()).replace("'", "'\\''") + "'"


def concat_copy(segments: list[Path], output: Path, work_dir: Path) -> None:
    concat_file = work_dir / "segments.ffconcat"
    concat_file.write_text(
        "ffconcat version 1.0\n" + "".join(f"file {ffconcat_quote(path)}\n" for path in segments),
        encoding="utf-8",
    )
    temporary = output.with_name(f".{output.stem}.assembling.mp4")
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
            "-movflags", "+faststart", str(temporary),
        ],
        check=True,
    )
    os.replace(temporary, output)


def normalize_segment(path: Path, output: Path, width: int, height: int) -> None:
    info = probe(path)
    has_audio = any(stream.get("codec_type") == "audio" for stream in info["streams"])
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path)]
    if not has_audio:
        command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
    command.extend([
        "-map", "0:v:0",
        "-map", "0:a:0" if has_audio else "1:a:0",
        "-vf",
        (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
        ),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
    ])
    if not has_audio:
        command.append("-shortest")
    command.append(str(output))
    subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    segments = [path.resolve() for path in args.segments]
    if len(segments) < 2:
        raise SystemExit("at least two replay segments are required")
    infos = [probe(path) for path in segments]
    signatures = [stream_signature(info) for info in infos]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work_dir = output.with_name(f".{output.stem}.assembly")
    work_dir.mkdir(parents=True, exist_ok=True)
    mode = "stream-copy"
    assembled_inputs = segments

    try:
        if len(set(signatures)) != 1:
            mode = "normalized"
            videos = [
                next(stream for stream in info["streams"] if stream.get("codec_type") == "video")
                for info in infos
            ]
            width = max(int(video.get("width") or 0) for video in videos)
            height = max(int(video.get("height") or 0) for video in videos)
            width += width % 2
            height += height % 2
            assembled_inputs = []
            for index, segment in enumerate(segments, start=1):
                normalized = work_dir / f"{index:02d}.mp4"
                normalize_segment(segment, normalized, width, height)
                assembled_inputs.append(normalized)
        concat_copy(assembled_inputs, output, work_dir)
        output_info = probe(output)
        expected_duration = sum(float(info["format"]["duration"]) for info in infos)
        actual_duration = float(output_info["format"]["duration"])
        tolerance = max(3.0, len(segments) * 1.5)
        if abs(expected_duration - actual_duration) > tolerance:
            raise RuntimeError(
                f"assembled duration mismatch: expected {expected_duration:.3f}, got {actual_duration:.3f}"
            )
        payload = {
            "status": "complete",
            "mode": mode,
            "segment_count": len(segments),
            "segments": [
                {
                    "path": str(path),
                    "duration_seconds": round(float(info["format"]["duration"]), 3),
                    "bytes": int(info["format"]["size"]),
                }
                for path, info in zip(segments, infos)
            ],
            "output": str(output),
            "duration_seconds": round(actual_duration, 3),
            "bytes": int(output_info["format"]["size"]),
            "seconds": round(time.monotonic() - started, 3),
        }
        write_json(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
