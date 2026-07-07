#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DeleteRow:
    index: str
    start: str
    end: str
    reason: str


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, text=True)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"缺少依赖 `{name}`")
    return path


def parse_time(value: str) -> float:
    parts = value.strip().split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"invalid time: {value}")


def fmt_time(seconds: float) -> str:
    whole = int(seconds)
    hours = whole // 3600
    minutes = (whole % 3600) // 60
    secs = whole % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def load_rows(csv_path: Path) -> list[DeleteRow]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if not {"start", "end"}.issubset(fields):
            raise SystemExit("删除清单 CSV 需要字段 start,end")
        rows: list[DeleteRow] = []
        for row_num, row in enumerate(reader, 1):
            rows.append(
                DeleteRow(
                    index=row.get("index") or f"{row_num:02d}",
                    start=row["start"],
                    end=row["end"],
                    reason=row.get("reason", ""),
                )
            )
        return rows


def tile_shape(count: int, columns: int | None) -> tuple[int, int]:
    cols = columns or min(6, max(1, count))
    rows = max(1, math.ceil(count / cols))
    return cols, rows


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="从删除候选 CSV 抽帧并生成审阅 contact sheet")
    parser.add_argument("video", type=Path)
    parser.add_argument("--delete-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames-dir", type=Path)
    parser.add_argument("--index-csv", type=Path)
    parser.add_argument("--position", choices=["start", "mid"], default="mid")
    parser.add_argument("--scale-width", type=int, default=320)
    parser.add_argument("--columns", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    video = args.video.expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"输入不存在：{video}")
    rows = load_rows(args.delete_csv)
    if not rows:
        raise SystemExit("删除清单为空")

    ffmpeg = require_tool("ffmpeg")
    output = args.output
    frames_dir = args.frames_dir or output.with_suffix("").with_name(output.stem + "_frames")
    index_csv = args.index_csv or output.with_suffix(".index.csv")
    frames_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    index_csv.parent.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    index_rows: list[dict[str, str]] = []
    for tile_num, row in enumerate(rows, 1):
        start = parse_time(row.start)
        end = parse_time(row.end)
        timestamp = start if args.position == "start" else (start + end) / 2
        frame_path = frames_dir / f"candidate_{tile_num:03d}_{row.index}.jpg"
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y" if args.force else "-n",
                "-ss",
                fmt_time(timestamp),
                "-i",
                str(video),
                "-vf",
                f"scale={args.scale_width}:-1",
                "-frames:v",
                "1",
                str(frame_path),
            ]
        )
        frame_paths.append(frame_path)
        index_rows.append(
            {
                "tile": str(tile_num),
                "index": row.index,
                "sample": fmt_time(timestamp),
                "start": row.start,
                "end": row.end,
                "reason": row.reason,
                "frame": str(frame_path),
            }
        )

    concat_file = frames_dir / "frames.txt"
    concat_file.write_text(
        "\n".join("file '" + str(path.resolve()).replace("'", "'\\''") + "'" for path in frame_paths)
        + "\n",
        encoding="utf-8",
    )
    cols, rows_count = tile_shape(len(frame_paths), args.columns)
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if args.force else "-n",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-vf",
            f"tile={cols}x{rows_count}",
            "-frames:v",
            "1",
            str(output),
        ]
    )

    with index_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["tile", "index", "sample", "start", "end", "reason", "frame"],
        )
        writer.writeheader()
        writer.writerows(index_rows)

    print(f"候选审阅图：{output}")
    print(f"审阅索引：{index_csv}")
    print(f"候选帧目录：{frames_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
