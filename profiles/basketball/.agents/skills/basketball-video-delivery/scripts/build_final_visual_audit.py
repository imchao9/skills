#!/usr/bin/env python3
"""Build a fingerprint-bound, risk-triggered final visual audit package."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


SEAM_OFFSETS = (-0.25, 0.25)
CONTEXT_OFFSETS = (-2.0, 2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pure", type=Path, required=True)
    parser.add_argument("--delete-csv", type=Path, required=True)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--poster", type=Path, required=True)
    parser.add_argument("--main-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--max-seams", type=int, default=18)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_fingerprint(path: Path, *, with_hash: bool = False) -> dict[str, Any]:
    stat = path.stat()
    result: dict[str, Any] = {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if with_hash:
        result["sha256"] = sha256(path)
    return result


def parse_seconds(value: str) -> float:
    """Accept raw seconds or MM:SS / HH:MM:SS timecodes."""
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) == 1:
        return float(text)
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid timecode: {value}")
    numbers = [float(part) for part in parts]
    if any(number < 0 for number in numbers):
        raise ValueError(f"invalid timecode: {value}")
    if len(numbers) == 2:
        minutes, seconds = numbers
        hours = 0.0
    else:
        hours, minutes, seconds = numbers
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"invalid timecode: {value}")
    return hours * 3600 + minutes * 60 + seconds


def read_delete_ranges(path: Path) -> list[tuple[float, float, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ranges: list[tuple[float, float, str]] = []
    for index, row in enumerate(rows, start=2):
        try:
            start = parse_seconds(row["start"])
            end = parse_seconds(row["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid delete range at row {index}") from exc
        if start < 0 or end <= start:
            raise ValueError(f"invalid delete range at row {index}: {start}-{end}")
        ranges.append((start, end, row.get("reason") or "reviewed cut"))
    ranges.sort(key=lambda item: (item[0], item[1]))
    previous_end = -1.0
    for start, end, _ in ranges:
        if start < previous_end:
            raise ValueError("delete ranges overlap")
        previous_end = end
    return ranges


def output_seams(ranges: list[tuple[float, float, str]]) -> list[dict[str, Any]]:
    deleted_before = 0.0
    seams: list[dict[str, Any]] = []
    for index, (start, end, reason) in enumerate(ranges, start=1):
        seams.append({
            "index": index,
            "source_start": round(start, 3),
            "source_end": round(end, 3),
            "deleted_seconds": round(end - start, 3),
            "output_time": round(max(0.0, start - deleted_before), 3),
            "reason": reason,
        })
        deleted_before += end - start
    return seams


def evenly_sample(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(items) <= limit:
        return items
    if limit == 1:
        return [items[len(items) // 2]]
    indices = {
        round(index * (len(items) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [items[index] for index in sorted(indices)]


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"ffprobe failed: {path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def extract_frame(video: Path, timestamp: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video),
            "-frames:v", "1", "-vf", "scale=480:-2", str(output),
        ],
        check=True,
    )


def data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def timeline_times(duration: float, count: int = 12) -> list[float]:
    if duration <= 0:
        return []
    return [duration * (index + 1) / (count + 1) for index in range(count)]


def render_seam_video(
    pure: Path,
    seams: list[dict[str, Any]],
    duration: float,
    output_dir: Path,
) -> Path | None:
    if not seams:
        return None
    clips_dir = output_dir / "seam-clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    for seam in seams:
        start = min(max(0.0, seam["output_time"] - 2.0), max(0.0, duration - 0.05))
        clip_duration = min(4.0, max(0.05, duration - start))
        clip = clips_dir / f"seam-{seam['index']:03d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{start:.3f}", "-i", str(pure), "-t", f"{clip_duration:.3f}",
                "-map", "0:v:0", "-map", "0:a?", "-vf", "scale=640:-2,fps=15",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", str(clip),
            ],
            check=True,
        )
        clips.append(clip)
    concat = output_dir / "seam-audit.concat.txt"
    concat.write_text(
        "\n".join(f"file '{str(clip.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for clip in clips)
        + "\n",
        encoding="utf-8",
    )
    output = output_dir / "pure-cut-seam-audit.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output),
        ],
        check=True,
    )
    return output


def render_evidence(
    *,
    pure: Path,
    game: Path,
    poster: Path,
    seams: list[dict[str, Any]],
    context_seams: list[dict[str, Any]],
    game_requires_review: bool,
    poster_requires_review: bool,
    output_dir: Path,
) -> tuple[Path, Path, Path | None, list[dict[str, Any]]]:
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict[str, Any]] = []

    pure_duration = media_duration(pure)
    seam_video = render_seam_video(pure, seams, pure_duration, output_dir)
    for index, timestamp in enumerate(timeline_times(pure_duration), start=1):
        frame = frames_dir / f"pure-timeline-{index:02d}.jpg"
        extract_frame(pure, timestamp, frame)
        cards.append({
            "group": "纯享版全局时间线",
            "label": f"{timestamp:.1f}s",
            "path": frame,
        })

    context_indices = {seam["index"] for seam in context_seams}
    for seam in seams:
        offsets = (
            (*CONTEXT_OFFSETS[:1], *SEAM_OFFSETS, *CONTEXT_OFFSETS[1:])
            if seam["index"] in context_indices
            else SEAM_OFFSETS
        )
        for offset in offsets:
            # Seeking only a few frames before EOF is unreliable for some H.264
            # files because the demuxer may not return a decodable frame. Keep
            # end-of-video seam evidence safely inside the final GOP.
            timestamp = min(max(0.0, seam["output_time"] + offset), max(0.0, pure_duration - 0.5))
            frame = frames_dir / f"pure-seam-{seam['index']:03d}-{offset:+.2f}.jpg"
            extract_frame(pure, timestamp, frame)
            cards.append({
                "group": f"纯享版接缝 {seam['index']} · {seam['reason']}",
                "label": f"接缝{offset:+.2f}s · 输出{timestamp:.2f}s",
                "path": frame,
            })

    if game_requires_review:
        game_duration = media_duration(game)
        for index, timestamp in enumerate(timeline_times(game_duration), start=1):
            frame = frames_dir / f"game-timeline-{index:02d}.jpg"
            extract_frame(game, timestamp, frame)
            cards.append({
                "group": "全场集锦主审核后发生变化",
                "label": f"{timestamp:.1f}s",
                "path": frame,
            })

    if poster_requires_review:
        cards.append({
            "group": "球评海报主审核后发生变化",
            "label": "最终浏览器 PNG",
            "path": poster,
        })

    groups: list[str] = []
    current = None
    for card_index, card in enumerate(cards):
        if card["group"] != current:
            if current is not None:
                groups.append("</section>")
            current = card["group"]
            groups.append(f"<section><h2>{html.escape(current)}</h2><div class='grid'>")
        groups.append(
            "<figure>"
            f"<img src='{data_url(card['path'])}' alt='{html.escape(card['label'])}'>"
            f"<figcaption>{html.escape(card['label'])}</figcaption>"
            "</figure>"
        )
        next_index = card_index + 1
        if next_index == len(cards) or cards[next_index]["group"] != current:
            groups.append("</div>")
    if current is not None:
        groups.append("</section>")

    evidence_html = output_dir / "final-visual-audit.html"
    evidence_html.write_text(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<style>
*{box-sizing:border-box}body{margin:0;background:#101318;color:#eef2f6;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
main{width:1080px;margin:0 auto;padding:42px}h1{font-size:38px;margin:0 0 12px}p{color:#aeb8c4;margin:0 0 32px}
section{margin:34px 0}h2{font-size:24px;border-left:6px solid #39d98a;padding-left:14px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}figure{margin:0;background:#1a2029;border-radius:10px;overflow:hidden}
img{display:block;width:100%;height:150px;object-fit:cover}figcaption{padding:10px 12px;font-size:14px;color:#d7dee7}
</style></head><body><main><h1>最终视觉审核证据</h1>
<p>只审核主审核后新增或可能变化的最终像素。纯享版接缝按删除时间表映射到最终输出时间。</p>"""
        + "".join(groups)
        + "</main></body></html>",
        encoding="utf-8",
    )
    evidence_png = output_dir / "final-visual-audit.png"
    montage_dir = output_dir / "montage"
    montage_dir.mkdir(parents=True, exist_ok=True)
    for index, card in enumerate(cards, start=1):
        target = montage_dir / f"{index:03d}.jpg"
        if card["path"].suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(card["path"], target)
        else:
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(card["path"]), "-frames:v", "1", str(target),
                ],
                check=True,
            )
    rows = max(1, (len(cards) + 3) // 4)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", "1", "-pattern_type", "glob", "-i", str(montage_dir / "*.jpg"),
            "-vf",
            (
                "scale=480:270:force_original_aspect_ratio=decrease,"
                "pad=480:270:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"tile=4x{rows}:padding=8:margin=8"
            ),
            "-frames:v", "1", str(evidence_png),
        ],
        check=True,
    )
    serializable_cards = [
        {**card, "path": str(card["path"].resolve())}
        for card in cards
    ]
    return evidence_html, evidence_png, seam_video, serializable_cards


def current_contract(contract: dict[str, Any], fingerprints: dict[str, Any]) -> bool:
    seam_video = contract.get("evidence", {}).get("seam_video")
    return (
        contract.get("fingerprints") == fingerprints
        and Path(contract.get("evidence", {}).get("html") or "").is_file()
        and Path(contract.get("evidence", {}).get("png") or "").is_file()
        and (not seam_video or Path(seam_video).is_file())
    )


def main() -> int:
    args = parse_args()
    for command in ("ffmpeg", "ffprobe"):
        if shutil.which(command) is None:
            raise SystemExit(f"missing tool: {command}")
    paths = (args.pure, args.delete_csv, args.game, args.poster, args.main_review)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"missing audit input: {missing}")

    review = json.loads(args.main_review.read_text(encoding="utf-8"))
    if review.get("status") != "approved":
        raise SystemExit("main AI review is not approved")
    fingerprints = {
        "pure": file_fingerprint(args.pure),
        "delete_csv": file_fingerprint(args.delete_csv, with_hash=True),
        "game": file_fingerprint(args.game),
        "poster": file_fingerprint(args.poster),
        "main_review": file_fingerprint(args.main_review, with_hash=True),
    }
    if args.contract.is_file():
        existing = json.loads(args.contract.read_text(encoding="utf-8"))
        if current_contract(existing, fingerprints):
            print(json.dumps(existing, ensure_ascii=False, indent=2))
            return 0

    seams = output_seams(read_delete_ranges(args.delete_csv))
    sampled_seams = evenly_sample(seams, args.max_seams)
    review_mtime_ns = args.main_review.stat().st_mtime_ns
    reviewed_game = Path(review.get("game_highlight", {}).get("draft_video") or "")
    reviewed_poster = Path(review.get("commentary", {}).get("png") or "")
    game_requires_review = (
        reviewed_game.resolve() != args.game.resolve()
        or args.game.stat().st_mtime_ns > review_mtime_ns
    )
    poster_requires_review = (
        reviewed_poster.resolve() != args.poster.resolve()
        or args.poster.stat().st_mtime_ns > review_mtime_ns
    )
    pure_requires_review = bool(seams)
    required = {
        "pure_seams": pure_requires_review,
        "game_visual": game_requires_review,
        "poster_visual": poster_requires_review,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence_html, evidence_png, seam_video, cards = render_evidence(
        pure=args.pure,
        game=args.game,
        poster=args.poster,
        seams=seams,
        context_seams=sampled_seams,
        game_requires_review=game_requires_review,
        poster_requires_review=poster_requires_review,
        output_dir=args.output_dir,
    )
    needs_ai = any(required.values())
    payload = {
        "status": "needs_ai" if needs_ai else "auto_approved",
        "audit_version": 1,
        "instructions": (
            "Inspect the evidence HTML or PNG and play the seam audit video when present. "
            "For every required check, set approved=true. "
            "Then set status=approved. Do not approve visible cut jumps, duplicated/blank frames, "
            "covered scoreboards, unreadable labels, poster overflow, or incorrect imagery."
        ),
        "fingerprints": fingerprints,
        "risk_reasons": {
            "pure_seams": f"{len(seams)} reviewed cuts create final-resolution seams",
            "game_visual": "final game reel differs from the main-review artifact" if game_requires_review else "reused main-review artifact",
            "poster_visual": "final poster differs from the main-review artifact" if poster_requires_review else "reused main-review artifact",
        },
        "checks": {
            name: {"required": is_required, "approved": not is_required, "notes": ""}
            for name, is_required in required.items()
        },
        "pure_seams": {
            "count": len(seams),
            "all_seams_have_before_after_frames": True,
            "context_sampled_count": len(sampled_seams),
            "context_sampled": sampled_seams,
        },
        "evidence": {
            "html": str(evidence_html.resolve()),
            "png": str(evidence_png.resolve()),
            "seam_video": str(seam_video.resolve()) if seam_video else None,
            "cards": cards,
        },
        "reviewer_notes": [],
    }
    args.contract.parent.mkdir(parents=True, exist_ok=True)
    args.contract.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
