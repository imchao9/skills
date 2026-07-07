#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TimeRange:
    start: float
    end: float
    reason: str = ""


@dataclass
class KeepRange:
    start: float
    end: float


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


def parse_time(value: str) -> float:
    value = value.strip()
    if not value:
        raise ValueError("empty time")
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"invalid time: {value}")


def fmt_time(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def probe(input_path: Path, ffprobe: str) -> dict:
    result = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(input_path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def load_delete_ranges(csv_path: Path) -> list[TimeRange]:
    ranges: list[TimeRange] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if {"start", "end"}.issubset(fields):
            for row in reader:
                ranges.append(
                    TimeRange(
                        start=parse_time(row["start"]),
                        end=parse_time(row["end"]),
                        reason=row.get("reason", ""),
                    )
                )
        elif {"range"}.issubset(fields):
            for row in reader:
                start, end = row["range"].split("-", 1)
                ranges.append(
                    TimeRange(
                        start=parse_time(start),
                        end=parse_time(end),
                        reason=row.get("reason", ""),
                    )
                )
        else:
            raise SystemExit("删除清单 CSV 需要字段 start,end 或 range")
    return normalize_ranges(ranges)


def normalize_ranges(ranges: list[TimeRange]) -> list[TimeRange]:
    ranges = [r for r in ranges if r.end > r.start]
    ranges.sort(key=lambda r: r.start)
    merged: list[TimeRange] = []
    for item in ranges:
        if not merged or item.start > merged[-1].end:
            merged.append(item)
            continue
        merged[-1].end = max(merged[-1].end, item.end)
        if item.reason and item.reason not in merged[-1].reason:
            merged[-1].reason = (merged[-1].reason + "; " + item.reason).strip("; ")
    return merged


def invert_ranges(delete_ranges: list[TimeRange], duration: float) -> list[KeepRange]:
    keep: list[KeepRange] = []
    cursor = 0.0
    for item in delete_ranges:
        start = max(0.0, min(duration, item.start))
        end = max(0.0, min(duration, item.end))
        if start > cursor:
            keep.append(KeepRange(cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        keep.append(KeepRange(cursor, duration))
    return [item for item in keep if item.end - item.start > 0.05]


def make_proxy(input_path: Path, output_path: Path, ffmpeg: str, *, force: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-y" if force else "-n",
        "-i",
        str(input_path),
        "-vf",
        "scale=-2:480",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run(cmd)


def render_keep_ranges(
    input_path: Path,
    output_path: Path,
    keep_ranges: list[KeepRange],
    ffmpeg: str,
    *,
    force: bool,
    copy_codecs: bool,
    encoder_preset: str,
    crf: str,
) -> None:
    if output_path.exists() and not force:
        raise SystemExit(f"输出已存在：{output_path}，如需覆盖请加 --force")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pure_cut_") as tmp:
        tmp_dir = Path(tmp)
        clip_paths: list[Path] = []
        total = len(keep_ranges)
        for idx, item in enumerate(keep_ranges, 1):
            clip = tmp_dir / f"keep_{idx:03d}.mp4"
            print(
                f"渲染片段 {idx}/{total}: {fmt_time(item.start)} -> {fmt_time(item.end)} "
                f"({item.end - item.start:.1f}s)",
                flush=True,
            )
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{item.start:.3f}",
                "-i",
                str(input_path),
                "-t",
                f"{item.end - item.start:.3f}",
            ]
            if copy_codecs:
                cmd.extend(["-c", "copy"])
            else:
                cmd.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        encoder_preset,
                        "-crf",
                        crf,
                        "-c:a",
                        "aac",
                        "-avoid_negative_ts",
                        "make_zero",
                    ]
                )
            cmd.append(str(clip))
            run(cmd)
            clip_paths.append(clip)

        concat_file = tmp_dir / "concat.txt"
        concat_file.write_text(
            "\n".join(
                "file '" + str(path.resolve()).replace("'", "'\\''") + "'"
                for path in clip_paths
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"拼接 {len(clip_paths)} 个保留片段 -> {output_path}", flush=True)
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y" if force else "-n",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ]
        )


def write_report(
    report_path: Path,
    *,
    input_path: Path,
    output_path: Path | None,
    duration: float,
    delete_ranges: list[TimeRange],
    keep_ranges: list[KeepRange],
    input_probe: dict,
    output_probe: dict | None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    deleted = sum(item.end - item.start for item in delete_ranges)
    kept = sum(item.end - item.start for item in keep_ranges)
    payload = {
        "input": str(input_path),
        "output": str(output_path) if output_path else None,
        "duration": duration,
        "deleted_duration": deleted,
        "kept_duration": kept,
        "delete_ranges": [
            {**asdict(item), "start_label": fmt_time(item.start), "end_label": fmt_time(item.end)}
            for item in delete_ranges
        ],
        "keep_ranges": [
            {**asdict(item), "start_label": fmt_time(item.start), "end_label": fmt_time(item.end)}
            for item in keep_ranges
        ],
        "input_probe": input_probe,
        "output_probe": output_probe,
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按删除时间段生成纯享版视频")
    parser.add_argument("input", type=Path)
    parser.add_argument("--delete-csv", type=Path, help="删除时间段 CSV，字段 start,end,reason")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--make-proxy", action="store_true")
    parser.add_argument("--proxy-output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--copy-codecs", action="store_true", help="快速拷贝编码，切点可能不准")
    parser.add_argument("--preset", default="veryfast", help="x264 preset，默认 veryfast")
    parser.add_argument("--crf", default="23", help="x264 CRF，默认 23；数值越大越快/越小")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"输入不存在：{input_path}")
    ffmpeg = require_tool("ffmpeg")
    ffprobe = require_tool("ffprobe")

    if args.make_proxy:
        proxy_output = args.proxy_output or input_path.with_name(input_path.stem + "_480p_proxy.mp4")
        make_proxy(input_path, proxy_output, ffmpeg, force=args.force)

    input_probe = probe(input_path, ffprobe)
    duration = float(input_probe["format"]["duration"])
    delete_ranges = load_delete_ranges(args.delete_csv) if args.delete_csv else []
    keep_ranges = invert_ranges(delete_ranges, duration)

    output_path = args.output
    if output_path is None and args.delete_csv:
        output_path = input_path.with_name(input_path.stem + "_pure.mp4")

    output_probe = None
    if output_path and not args.dry_run:
        render_keep_ranges(
            input_path,
            output_path,
            keep_ranges,
            ffmpeg,
            force=args.force,
            copy_codecs=args.copy_codecs,
            encoder_preset=args.preset,
            crf=args.crf,
        )
        output_probe = probe(output_path, ffprobe)

    report_path = args.report or Path("output/pure-cut/reports") / f"{input_path.stem}_pure_cut_report.json"
    write_report(
        report_path,
        input_path=input_path,
        output_path=output_path,
        duration=duration,
        delete_ranges=delete_ranges,
        keep_ranges=keep_ranges,
        input_probe=input_probe,
        output_probe=output_probe,
    )
    print(f"报告：{report_path}")
    if output_path:
        print(f"输出：{output_path}")
    print(f"删除 {sum(r.end - r.start for r in delete_ranges):.1f}s，保留 {sum(r.end - r.start for r in keep_ranges):.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
