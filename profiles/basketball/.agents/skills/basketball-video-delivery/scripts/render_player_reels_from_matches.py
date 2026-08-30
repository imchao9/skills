#!/usr/bin/env python3
"""Render event clips and per-player reels from a reviewed full-source matches CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


PLAYER_SCRIPT = Path(__file__).parents[1].parent / "basketball-player-clips" / "scripts" / "remake_player_clips.py"
SPEC = importlib.util.spec_from_file_location("basketball_player_reels_runtime", PLAYER_SCRIPT)
if not SPEC or not SPEC.loader:
    raise SystemExit(f"Unable to load player clip runtime: {PLAYER_SCRIPT}")
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        help="Use one reviewed full-game source for every row when the CSV has no source column.",
    )
    parser.add_argument("--match-json", type=Path, help="Use official player totals in labels.")
    parser.add_argument("--default-pre", type=float, default=15.0)
    parser.add_argument("--default-post", type=float, default=8.0)
    parser.add_argument("--assist-pre", type=float, default=15.0)
    parser.add_argument("--assist-post", type=float, default=8.0)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--contact-sheets", action="store_true")
    parser.add_argument(
        "--events-only",
        action="store_true",
        help="Render the remade event clips and report without building per-player reels.",
    )
    parser.add_argument(
        "--low-peak",
        action="store_true",
        help="Build one player at a time and leave event clips for the game builder to materialize on demand.",
    )
    parser.add_argument("--raw-no-overlay", action="store_true", help="Create unlabeled intermediates only.")
    return parser.parse_args()


def official_player_stats(path: Path | None) -> dict[tuple[str, str], str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], str] = {}
    for players in data.get("players", {}).values():
        for player in players:
            parts = [f"{int(player.get('score') or 0)}分"]
            for field, suffix in (("totalBoards", "板"), ("assists", "助"), ("steals", "断"), ("blocks", "帽")):
                value = int(player.get(field) or 0)
                if value:
                    parts.append(f"{value}{suffix}")
            result[(str(player.get("playerNo") or ""), str(player.get("playerName") or ""))] = " · ".join(parts)
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_event_stat_audit(rows: list[dict[str, str]], match_json: Path | None) -> dict:
    """Reconcile labeled event counts with official per-player totals."""
    if match_json is None:
        return {"status": "needs_attention", "errors": ["match_json is required"]}
    data = json.loads(match_json.read_text(encoding="utf-8"))
    field_map = {
        "2分命中": "twoShotNum", "3分命中": "threeShotNum", "助攻": "assists",
        "抢断": "steals", "盖帽": "blocks",
    }
    official: dict[tuple[str, str], dict[str, int]] = {}
    for players in (data.get("players") or {}).values():
        for player in players:
            key = (str(player.get("playerNo") or ""), str(player.get("playerName") or ""))
            official[key] = {action: int(player.get(field) or 0) for action, field in field_map.items()}
    observed: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    errors: list[str] = []
    for row in rows:
        key = (str(row.get("number") or ""), str(row.get("player") or ""))
        action = str(row.get("action") or "")
        if key not in official:
            errors.append(f"unknown player in event metadata: {key[0]}号 {key[1]}")
        elif action not in field_map:
            errors.append(f"unsupported action in event metadata: {action}")
        else:
            observed[key][action] += 1
    comparisons: list[dict[str, object]] = []
    for key, expected_actions in sorted(official.items()):
        for action, expected in expected_actions.items():
            actual = observed[key].get(action, 0)
            comparisons.append({
                "number": key[0], "player": key[1], "action": action,
                "expected": expected, "actual": actual, "matches": expected == actual,
            })
            if expected != actual:
                errors.append(f"{key[0]}号 {key[1]} {action}: official={expected}, events={actual}")
    return {
        "status": "complete" if official and not errors else "needs_attention",
        "event_rows": len(rows), "official_players": len(official),
        "comparisons": comparisons, "errors": errors or ([] if official else ["official players missing"]),
    }


def write_action_evidence(
    rows: list[dict[str, str]], rendered_csv: Path, output_dir: Path, durations: dict[Path, float]
) -> dict:
    evidence_dir = output_dir / "debug" / "action-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    scoring_rows = [row for row in rows if row.get("action") in {"2分命中", "3分命中"}]
    items: list[dict[str, object]] = []
    for index, row in enumerate(scoring_rows, 1):
        source = Path(row["source"]).resolve()
        seconds = min(max(0.0, durations[source] - 0.1), float(row["source_seconds"]) + 6.0)
        target = evidence_dir / f"{index:03d}_{runtime.safe_name(row['player'])}_{row['event_id']}.jpg"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seconds:.3f}",
            "-i", str(source), "-frames:v", "1", "-q:v", "2", str(target),
        ], check=True)
        items.append({
            "event_id": row["event_id"], "player": row["player"], "action": row["action"],
            "period": row["period"], "clock": row["clock"], "source_seconds": round(seconds, 3),
            "evidence_frame": str(target.resolve()),
        })
    return {
        "status": "complete" if len(items) == len(scoring_rows) else "needs_attention",
        "matches_csv": str(rendered_csv.resolve()),
        "matches_csv_sha256": sha256_file(rendered_csv),
        "scoring_event_count": len(scoring_rows), "evidence_frame_count": len(items),
        "review_instruction": "逐帧确认完成进球的球员与标注球员一致；不确定时不得批准。",
        "items": items,
    }


def label_copy(row: dict[str, str], stats: dict[tuple[str, str], str]) -> tuple[str, str]:
    number = str(row.get("number") or "-")
    player = str(row.get("player") or "未识别")
    title = f"{row.get('team') or '未识别球队'}｜{number}号 {player}"
    if stats.get((number, player)):
        title += f"｜本场 {stats[(number, player)]}"
    detail = f"{row.get('action') or '未识别事件'}｜{row.get('period') or '未知节次'} {row.get('clock') or '--:--'}"
    return title, detail


def event_output_name(row: dict[str, str], labeled: bool = True) -> str:
    suffix = "_数据标注版.mp4" if labeled else "_原始中间片段.mp4"
    return runtime.safe_name(str(row["title"]) + suffix)


def player_reel_name(player: str, labeled: bool = True) -> str:
    suffix = "-个人精彩集锦_数据标注版.mp4" if labeled else "-个人精彩集锦_原始中间版.mp4"
    return runtime.safe_name(player) + suffix


def render_event(source: Path, start: float, end: float, output: Path, row: dict[str, str], stats: dict[tuple[str, str], str], *, preset: str, crf: str, labeled: bool) -> None:
    if not labeled:
        runtime.render_clip(source, start, end, output, preset=preset, crf=crf)
        return
    from PIL import Image, ImageDraw, ImageFont
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="basketball-label-") as temporary:
        label = Path(temporary) / "label.png"
        title, detail = label_copy(row, stats)
        image = Image.new("RGBA", (1100, 150), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 1100, 150), radius=16, fill=(8, 12, 20, 210))
        draw.rectangle((0, 0, 10, 150), fill=(255, 178, 0, 255))
        font = runtime.find_font()
        draw.text((34, 20), title, font=ImageFont.truetype(font, 36), fill="white")
        draw.text((34, 82), f"本次：{detail}", font=ImageFont.truetype(font, 32), fill=(255, 207, 84, 255))
        image.save(label)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", str(source), "-loop", "1", "-i", str(label), "-t", f"{end-start:.3f}", "-filter_complex", "[0:v][1:v]overlay=32:32:format=auto:shortest=1[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(output)], check=True)


def main() -> int:
    args = parse_args()
    rows = list(csv.DictReader(args.matches_csv.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("matches CSV is empty")
    output_dir = args.output_dir.resolve()
    labeled = not args.raw_no_overlay
    official_stats = official_player_stats(args.match_json)
    reports = output_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stat_audit = build_event_stat_audit(rows, args.match_json)
    (reports / "event-stat-audit.json").write_text(
        json.dumps(stat_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if stat_audit["status"] != "complete":
        raise SystemExit(
            f"event statistics did not reconcile; review {reports / 'event-stat-audit.json'}"
        )
    event_dir = output_dir / "个人精彩片段"
    results: list = []
    durations: dict[Path, float] = {}
    rendered_rows: list[dict[str, str]] = []
    render_specs: dict[Path, tuple[Path, float, float, dict[str, str]]] = {}
    for index, row in enumerate(rows, 1):
        source_value = str(row.get("source") or "").strip()
        if args.source:
            source = args.source.resolve()
        elif source_value:
            source = Path(source_value).resolve()
        else:
            raise SystemExit("matches CSV has no source column; pass --source")
        row["source"] = str(source)
        if source not in durations:
            durations[source] = runtime.probe_duration(source)
        event_time = float(row["source_seconds"])
        if row["action"] == "助攻":
            pre, post = args.assist_pre, args.assist_post
        else:
            pre, post = args.default_pre, args.default_post
        start = max(0.0, event_time - pre)
        end = min(durations[source], event_time + post)
        output = event_dir / event_output_name(row, labeled)
        print(f"[{index}/{len(rows)}] {row['title']} {runtime.fmt_time(start)}-{runtime.fmt_time(end)}", flush=True)
        render_specs[output] = (source, start, end, row)
        if not args.low_peak and not (args.resume and runtime.is_valid_video(output)):
            render_event(source, start, end, output, row, official_stats, preset=args.preset, crf=args.crf, labeled=labeled)
        item = runtime.ClipItem(
            output,
            row["team"],
            row["number"] + "号" if row["number"] else "",
            row["player"],
            row["action"],
            row["period"],
            row["clock"],
        )
        result = runtime.MatchResult(
            item=item,
            old_start=event_time,
            event_time=event_time,
            new_start=start,
            new_end=end,
            avg_hamming=0.0,
            output=output,
        )
        results.append(result)
        rendered_rows.append({
            **row,
            "new_start": runtime.fmt_time(start),
            "new_end": runtime.fmt_time(end),
            "output": str(output),
            "data_label_status": "data_labeled" if labeled else "raw_intermediate",
            "label_text": "｜".join(label_copy(row, official_stats)),
            "location_semantics": "reference_frame",
            "window_strategy": f"reference-frame-front{pre:g}-back{post:g}",
        })

    rendered_csv = reports / "rendered-matches.csv"
    with rendered_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rendered_rows[0]))
        writer.writeheader()
        writer.writerows(rendered_rows)
    action_evidence = write_action_evidence(rows, rendered_csv, output_dir, durations)
    (reports / "action-evidence.json").write_text(
        json.dumps(action_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if args.events_only:
        print(f"events={len(results)} players=0 output={output_dir}")
        return 0

    by_player: dict[str, list] = defaultdict(list)
    for result in results:
        by_player[result.item.player].append(result)
    reels_dir = output_dir / "个人精彩集锦"
    player_rows: list[dict[str, str | int]] = []
    for player, player_results in sorted(by_player.items()):
        selected = runtime.dedupe_player_reel_items(player_results)
        target = reels_dir / player_reel_name(player, labeled)
        peak_temporary_bytes = 0
        if not (args.resume and runtime.is_valid_video(target)):
            if args.low_peak:
                work_parent = output_dir / ".render-work"
                work_parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="player-", dir=work_parent) as temporary:
                    temporary_dir = Path(temporary)
                    temporary_outputs: list[Path] = []
                    for index, item in enumerate(selected, 1):
                        source, start, end, row = render_specs[item.output]
                        temporary_output = temporary_dir / f"event-{index:03d}.mp4"
                        render_event(source, start, end, temporary_output, row, official_stats, preset=args.preset, crf=args.crf, labeled=labeled)
                        temporary_outputs.append(temporary_output)
                    peak_temporary_bytes = sum(path.stat().st_size for path in temporary_outputs)
                    runtime.concat_outputs(temporary_outputs, target)
                    target.with_suffix(".concat.txt").unlink(missing_ok=True)
                if work_parent.is_dir() and not any(work_parent.iterdir()):
                    work_parent.rmdir()
            else:
                runtime.concat_outputs([item.output for item in selected], target)
        if args.contact_sheets:
            runtime.contact_sheet(target, output_dir / "debug" / "个人精彩集锦" / f"{runtime.safe_name(player)}.jpg")
        player_rows.append({
            "player": player,
            "event_count": len(player_results),
            "selected_count": len(selected),
            "output": str(target),
            "render_strategy": "per_player_temporary" if args.low_peak else "persistent_events",
            "peak_temporary_event_bytes": peak_temporary_bytes,
            "data_label_status": "data_labeled" if labeled else "raw_intermediate",
        })
    with (reports / "players.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "player", "event_count", "selected_count", "output",
            "render_strategy", "peak_temporary_event_bytes", "data_label_status",
        ])
        writer.writeheader()
        writer.writerows(player_rows)
    print(f"events={len(results)} players={len(player_rows)} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
