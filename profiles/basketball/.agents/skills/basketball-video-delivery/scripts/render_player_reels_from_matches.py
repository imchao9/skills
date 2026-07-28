#!/usr/bin/env python3
"""Render event clips and per-player reels from a reviewed full-source matches CSV."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path


PLAYER_SCRIPT = Path.home() / ".codex" / "skills" / "basketball-player-clips" / "scripts" / "remake_player_clips.py"
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
    parser.add_argument("--default-pre", type=float, default=15.0)
    parser.add_argument("--default-post", type=float, default=3.0)
    parser.add_argument("--assist-pre", type=float, default=15.0)
    parser.add_argument("--assist-post", type=float, default=0.0)
    parser.add_argument("--preset", default="veryfast")
    parser.add_argument("--crf", default="20")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--contact-sheets", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = list(csv.DictReader(args.matches_csv.open(encoding="utf-8")))
    if not rows:
        raise SystemExit("matches CSV is empty")
    output_dir = args.output_dir.resolve()
    event_dir = output_dir / "个人精彩片段"
    results: list = []
    durations: dict[Path, float] = {}
    rendered_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, 1):
        source = Path(row["source"]).resolve()
        if source not in durations:
            durations[source] = runtime.probe_duration(source)
        event_time = float(row["source_seconds"])
        if row["action"] == "助攻":
            pre, post = args.assist_pre, args.assist_post
        else:
            pre, post = args.default_pre, args.default_post
        start = max(0.0, event_time - pre)
        end = min(durations[source], event_time + post)
        title = row["title"] + ".mp4"
        output = event_dir / runtime.safe_name(title)
        print(f"[{index}/{len(rows)}] {row['title']} {runtime.fmt_time(start)}-{runtime.fmt_time(end)}", flush=True)
        if not (args.resume and runtime.is_valid_video(output)):
            runtime.render_clip(source, start, end, output, preset=args.preset, crf=args.crf)
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
        })

    reports = output_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    with (reports / "rendered-matches.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rendered_rows[0]))
        writer.writeheader()
        writer.writerows(rendered_rows)

    by_player: dict[str, list] = defaultdict(list)
    for result in results:
        by_player[result.item.player].append(result)
    reels_dir = output_dir / "个人精彩集锦"
    player_rows: list[dict[str, str | int]] = []
    for player, player_results in sorted(by_player.items()):
        selected = runtime.dedupe_player_reel_items(player_results)
        target = reels_dir / f"{runtime.safe_name(player)}-个人精彩集锦.mp4"
        runtime.concat_outputs([item.output for item in selected], target)
        if args.contact_sheets:
            runtime.contact_sheet(target, output_dir / "debug" / "个人精彩集锦" / f"{runtime.safe_name(player)}.jpg")
        player_rows.append({
            "player": player,
            "event_count": len(player_results),
            "selected_count": len(selected),
            "output": str(target),
        })
    with (reports / "players.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["player", "event_count", "selected_count", "output"])
        writer.writeheader()
        writer.writerows(player_rows)
    print(f"events={len(results)} players={len(player_rows)} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
