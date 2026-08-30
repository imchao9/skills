#!/usr/bin/env python3
"""Summarize delivery timing and acceptance metrics across representative matches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def stage_seconds(stages: list[dict[str, Any]], prefixes: tuple[str, ...]) -> float:
    return round(sum(
        float(stage.get("seconds") or 0)
        for stage in stages
        if str(stage.get("name") or "").startswith(prefixes)
    ), 3)


def classify(fast: dict[str, Any]) -> str:
    event_count = int(fast.get("event_metadata_count") or 0)
    segments = int(fast.get("replay_segment_count") or 0)
    source_bytes = int(fast.get("source_bytes") or 0)
    if event_count < 5 or segments > 1:
        return "sparse_or_multisegment"
    if source_bytes >= 4 * 1024 ** 3:
        return "event_rich_large_source"
    return "event_rich_single_source"


def summarize(run_dir: Path) -> dict[str, Any]:
    delivery = run_dir / "output" / "delivery"
    fast = read_json(delivery / "fast-start.json")
    standard = read_json(delivery / "standard-run.json")
    baidu = read_json(delivery / "baidu-sync-report.json")
    stages = list(fast.get("stages") or []) + list(standard.get("stages") or [])
    disk = next((stage for stage in stages if stage.get("name") == "disk_preflight"), {})
    return {
        "matchID": fast.get("matchID") or run_dir.name,
        "archetype": classify(fast),
        "status": standard.get("status") or fast.get("status") or "missing",
        "event_source": fast.get("event_source"),
        "event_metadata_count": fast.get("event_metadata_count"),
        "event_download_count": fast.get("event_download_count"),
        "replay_segment_count": fast.get("replay_segment_count"),
        "source_bytes": fast.get("source_bytes"),
        "fast_start_seconds": fast.get("seconds"),
        "replay_acquisition_seconds": stage_seconds(stages, ("download_replay", "assemble_replay")),
        "event_location_seconds": stage_seconds(stages, ("locate_event",)),
        "player_render_seconds": stage_seconds(stages, ("render_event_direct", "player_clips")),
        "pure_render_seconds": stage_seconds(stages, ("render_pure",)),
        "upload_seconds": stage_seconds(stages, ("baidu_sync",)),
        "disk_preflight": disk,
        "remote_bytes_verified": baidu.get("remote_bytes_verified"),
        "checks": {
            "event_direct_default": fast.get("event_source") == "direct",
            "no_platform_event_downloads": int(fast.get("event_download_count") or 0) == 0,
            "disk_preflight_passed": not disk or disk.get("status") == "complete",
            "recoverable_status": (standard.get("status") or fast.get("status"))
            in {"complete", "ready_to_upload", "waiting_for_ai", "waiting_for_final_visual_review", "needs_attention"},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    runs = [summarize(path.resolve()) for path in args.run_dir]
    represented = sorted({run["archetype"] for run in runs})
    required = {
        "event_rich_single_source",
        "event_rich_large_source",
        "sparse_or_multisegment",
    }
    payload = {
        "status": "complete" if required <= set(represented) else "needs_more_samples",
        "represented_archetypes": represented,
        "missing_archetypes": sorted(required - set(represented)),
        "runs": runs,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
