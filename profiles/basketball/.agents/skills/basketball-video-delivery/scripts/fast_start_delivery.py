#!/usr/bin/env python3
"""Refresh, download, and deterministically prepare a basketball delivery before AI review."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable


SKILL_DIR = Path(__file__).parents[1]
SKILLS_DIR = SKILL_DIR.parent
FETCH_MATCH = SKILLS_DIR / "xiaoqiumi-match-review" / "scripts" / "fetch_xiaoqiumi_match.py"
DOWNLOAD_REPLAY = SKILL_DIR / "scripts" / "xiaoqiumi_download.py"
ASSEMBLE_REPLAYS = SKILL_DIR / "scripts" / "assemble_replay_segments.py"
DOWNLOAD_EVENTS = SKILL_DIR / "scripts" / "download_event_clips.py"
PURE_SKILL = SKILLS_DIR / "basketball-pure-cut"
PLAYER_SKILL = Path.home() / ".codex" / "skills" / "basketball-player-clips"


class ReplayUnavailableError(ValueError):
    """Raised when refreshed public match data does not contain a replay yet."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", help="Xiaoqiumi match URL or numeric match ID.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--event-workers", type=int, default=8)
    parser.add_argument("--replay-connections", type=int, default=8)
    parser.add_argument("--download-only", action="store_true", help="Stop before deterministic editing preflight.")
    parser.add_argument("--skip-event-clips", action="store_true", help="Download only the full replay, not platform event videos.")
    parser.add_argument("--skip-pure-preflight", action="store_true")
    parser.add_argument("--skip-player-clips", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def match_id_from_ref(ref: str) -> int:
    if ref.isdigit():
        return int(ref)
    match = re.search(r"matchid=(\d+)", ref, re.I)
    if not match:
        raise ValueError("could not find matchID in input")
    return int(match.group(1))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_logged(
    name: str,
    command: list[str],
    log: Path,
    *,
    stdin_text: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            input=stdin_text,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode:
        raise RuntimeError(f"{name} failed with exit {result.returncode}; see {log}")
    return {"name": name, "status": "complete", "seconds": elapsed, "log": str(log)}


def probe(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_entries",
            "stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        return None
    data = json.loads(result.stdout)
    if not data.get("streams") or float(data.get("format", {}).get("duration", 0)) <= 0:
        return None
    return data


def video_container(data: dict[str, Any]) -> dict[str, Any]:
    detail = data.get("raw", {}).get("details", {}).get("集锦", {})
    for section in detail.get("modeData") or []:
        videos = section.get("videos")
        if isinstance(videos, dict):
            return videos
    return {}


def replay_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in video_container(data).get("playBacks") or []
        if (
            item.get("url")
            and str(item.get("time") or "0").isdigit()
            and str(item.get("subName") or "") != "全场集锦"
            and (
                "回放" in str(item.get("title") or "")
                or "录像" in str(item.get("title") or "")
                or replay_time(item) >= 20 * 60
            )
        )
    ]


def replay_time(item: dict[str, Any]) -> int:
    return int(item.get("time") or 0)


def replay_created_at(item: dict[str, Any]) -> datetime:
    try:
        return datetime.strptime(str(item.get("addDate") or ""), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.min


def likely_duplicate_replay(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_time = replay_time(left)
    right_time = replay_time(right)
    if not left_time or not right_time:
        return False
    same_author = str(left.get("authorUserID") or "") == str(right.get("authorUserID") or "")
    close_duration = min(left_time, right_time) / max(left_time, right_time) >= 0.9
    close_creation = abs((replay_created_at(left) - replay_created_at(right)).total_seconds()) <= 5 * 60
    return same_author and close_duration and close_creation


def select_replays(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = replay_candidates(data)
    if not candidates:
        raise ReplayUnavailableError("public match data contains no replay URL")

    long_candidates = [item for item in candidates if replay_time(item) >= 20 * 60]
    if not long_candidates:
        raise ValueError("longest replay is under 20 minutes; authenticated fallback needs review")

    duplicate_groups: list[list[dict[str, Any]]] = []
    for item in sorted(long_candidates, key=replay_created_at):
        group = next(
            (current for current in duplicate_groups if any(likely_duplicate_replay(item, other) for other in current)),
            None,
        )
        if group is None:
            duplicate_groups.append([item])
        else:
            group.append(item)

    selected_long = [max(group, key=replay_time) for group in duplicate_groups]
    selected_authors = {str(item.get("authorUserID") or "") for item in selected_long}
    latest_long_creation = max(replay_created_at(item) for item in selected_long)
    supplemental = [
        item
        for item in candidates
        if (
            replay_time(item) < 20 * 60
            and replay_time(item) >= 30
            and (
                str(item.get("authorUserID") or "") in selected_authors
                or replay_created_at(item) > latest_long_creation
            )
        )
    ]
    selected = selected_long + supplemental
    return sorted(
        {str(item.get("id") or item.get("url")): item for item in selected}.values(),
        key=lambda item: (replay_created_at(item), replay_time(item)),
    )


def select_replay(data: dict[str, Any]) -> dict[str, Any]:
    """Compatibility helper for callers that still expect one primary replay."""
    return max(select_replays(data), key=replay_time)


def replay_selection_reason(
    item: dict[str, Any],
    *,
    selected: bool,
    eligible_ids: set[str],
    selected_authors: set[str],
    latest_long_creation: datetime,
) -> str:
    identity = str(item.get("id") or item.get("url"))
    if selected:
        if replay_time(item) >= 20 * 60:
            return "selected_long_segment"
        if str(item.get("authorUserID") or "") in selected_authors:
            return "selected_same_author_continuation"
        return "selected_later_cross_device_continuation"
    if str(item.get("subName") or "") == "全场集锦":
        return "excluded_official_highlight"
    if identity not in eligible_ids:
        return "excluded_non_replay_or_unplayable"
    if replay_time(item) >= 20 * 60:
        return "excluded_likely_duplicate_long_variant"
    if replay_created_at(item) <= latest_long_creation:
        return "excluded_earlier_short_test_or_pregame"
    return "excluded_short_non_continuation"


def replay_summary(item: dict[str, Any], *, selected: bool, reason: str) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "duration_seconds": replay_time(item),
        "addDate": item.get("addDate"),
        "authorUserID": item.get("authorUserID"),
        "width": item.get("videoWidth") or item.get("width"),
        "height": item.get("videoHeight") or item.get("height"),
        "selected": selected,
        "reason": reason,
    }


def event_count(data: dict[str, Any]) -> int:
    return sum(
        1
        for item in video_container(data).get("collectVideos") or []
        if item.get("subName") != "个人集锦" and item.get("title") and item.get("url")
    )


def safe_local_name(value: str) -> str:
    return value.replace("/", "-").replace("\0", "").strip()


def require_tools(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if shutil.which("ffprobe") is None:
        missing.append("ffprobe")
    if missing:
        raise FileNotFoundError(f"missing required tools: {missing}")


def acquire_replays(
    replays: list[dict[str, Any]],
    source: Path,
    run_dir: Path,
    connections: int,
) -> list[dict[str, Any]]:
    delivery = run_dir / "output" / "delivery"
    stages: list[dict[str, Any]] = []
    if len(replays) == 1:
        segment_paths = [source]
    else:
        segment_dir = run_dir / "source" / "replay-segments"
        segment_paths = [
            segment_dir / f"{index:02d}_{str(item.get('id') or 'replay')[:12]}.mp4"
            for index, item in enumerate(replays, start=1)
        ]

    for index, (replay, segment) in enumerate(zip(replays, segment_paths), start=1):
        if probe(segment) is not None:
            stages.append({
                "name": f"download_replay_segment_{index:02d}",
                "status": "cached",
                "path": str(segment),
            })
            continue
        stages.append(run_logged(
            f"download_replay_segment_{index:02d}",
            [
                sys.executable,
                str(DOWNLOAD_REPLAY),
                "--output",
                str(segment),
                "--url-stdin",
                "--report",
                str(delivery / f"xiaoqiumi-download-{index:02d}.json"),
                "--connections",
                str(connections),
            ],
            delivery / "logs" / f"download-replay-{index:02d}.log",
            stdin_text=str(replay["url"]) + "\n",
        ))

    if len(segment_paths) > 1:
        if probe(source) is None:
            stages.append(run_logged(
                "assemble_replay_segments",
                [
                    sys.executable,
                    str(ASSEMBLE_REPLAYS),
                    *[str(path) for path in segment_paths],
                    "--output",
                    str(source),
                    "--report",
                    str(delivery / "replay-assembly.json"),
                ],
                delivery / "logs" / "assemble-replay-segments.log",
            ))
        else:
            stages.append({"name": "assemble_replay_segments", "status": "cached", "path": str(source)})
    return stages


def pure_preflight(source: Path, run_dir: Path) -> list[dict[str, Any]]:
    output = run_dir / "output" / "pure-cut"
    proxy = output / "proxy" / "input_480p_proxy.mp4"
    delete_csv = output / "reports" / "auto_delete_list.csv"
    detector_report = output / "reports" / "auto_delete_report.json"
    sheet = output / "debug" / "auto_delete_mid_sheet.jpg"
    index_csv = output / "debug" / "auto_delete_mid_sheet.index.csv"
    logs = run_dir / "output" / "delivery" / "logs"
    stages: list[dict[str, Any]] = []
    if probe(proxy) is None:
        stages.append(run_logged(
            "pure_proxy",
            [sys.executable, str(PURE_SKILL / "scripts" / "pure_cut_editor.py"), str(source),
             "--make-proxy", "--proxy-output", str(proxy), "--force"],
            logs / "pure-proxy.log",
        ))
    else:
        stages.append({"name": "pure_proxy", "status": "cached", "path": str(proxy)})
    if not delete_csv.is_file() or not detector_report.is_file():
        stages.append(run_logged(
            "pure_candidates",
            [sys.executable, str(PURE_SKILL / "scripts" / "pure_cut_candidate_detector.py"), str(proxy),
             "--output-csv", str(delete_csv), "--report", str(detector_report)],
            logs / "pure-candidates.log",
        ))
    else:
        stages.append({"name": "pure_candidates", "status": "cached", "path": str(delete_csv)})
    if not sheet.is_file() or not index_csv.is_file():
        stages.append(run_logged(
            "pure_review_sheet",
            [sys.executable, str(PURE_SKILL / "scripts" / "pure_cut_review_sheet.py"), str(proxy),
             "--delete-csv", str(delete_csv), "--output", str(sheet), "--index-csv", str(index_csv),
             "--position", "mid", "--force"],
            logs / "pure-review-sheet.log",
        ))
    else:
        stages.append({"name": "pure_review_sheet", "status": "cached", "path": str(sheet)})
    return stages


def player_clips(source: Path, events: Path, run_dir: Path) -> list[dict[str, Any]]:
    output = run_dir / "output" / "player-clips-front15"
    matches = output / "reports" / "matches.csv"
    players = output / "reports" / "players.csv"
    if matches.is_file() and players.is_file() and any((output / "个人精彩集锦").glob("*.mp4")):
        return [{"name": "player_clips", "status": "cached", "path": str(output)}]
    stage = run_logged(
        "player_clips",
        [
            sys.executable,
            str(PLAYER_SKILL / "scripts" / "remake_player_clips.py"),
            "--source",
            str(source),
            "--clips-dir",
            str(events),
            "--output-dir",
            str(output),
            "--contact-sheets",
            "--resume",
        ],
        run_dir / "output" / "delivery" / "logs" / "player-clips.log",
    )
    return [stage]


def run_parallel(tasks: dict[str, Callable[[], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(task): name for name, task in tasks.items()}
        for future in as_completed(futures):
            stages.extend(future.result())
    return stages


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    workspace = args.workspace.resolve()
    match_id = match_id_from_ref(args.match)
    run_dir = workspace / "runs" / str(match_id)
    output = run_dir / "output"
    delivery = output / "delivery"
    report = args.report.resolve() if args.report else delivery / "fast-start.json"
    match_json = output / "match.json"
    facts_md = output / "match-facts.md"
    stages: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "status": "running",
        "matchID": match_id,
        "run_dir": str(run_dir),
        "mode": "download-only" if args.download_only else "fast-start",
        "stages": stages,
    }
    write_json(report, payload)

    try:
        require_tools([FETCH_MATCH, DOWNLOAD_REPLAY, ASSEMBLE_REPLAYS, DOWNLOAD_EVENTS])
        stages.append(run_logged(
            "refresh_match_data",
            [sys.executable, str(FETCH_MATCH), str(match_id), "--out", str(match_json), "--facts-md", str(facts_md)],
            delivery / "logs" / "refresh-match-data.log",
        ))
        data = json.loads(match_json.read_text(encoding="utf-8"))
        all_playbacks = list(video_container(data).get("playBacks") or [])
        all_replays = replay_candidates(data)
        replays = select_replays(data)
        replay_ids = "-".join(str(item.get("id") or "replay")[:8] for item in replays)
        source_title = safe_local_name(str(max(replays, key=replay_time).get("title") or "full-replay"))
        source_suffix = "" if len(replays) == 1 else f"_完整回放_{len(replays)}段_{replay_ids}"
        source = run_dir / "source" / f"{source_title}{source_suffix}.mp4"
        events = run_dir / "source" / "labeled-events"
        expected_events = 0 if args.skip_event_clips else event_count(data)
        selected_ids = {str(item.get("id") or item.get("url")) for item in replays}
        eligible_ids = {str(item.get("id") or item.get("url")) for item in all_replays}
        selected_long = [item for item in replays if replay_time(item) >= 20 * 60]
        selected_authors = {str(item.get("authorUserID") or "") for item in selected_long}
        latest_long_creation = max(replay_created_at(item) for item in selected_long)
        replay_selection = {
            "status": "selected",
            "playback_count": len(all_playbacks),
            "candidate_count": len(all_replays),
            "selected_count": len(replays),
            "selected_duration_seconds": sum(replay_time(item) for item in replays),
            "candidates": [
                replay_summary(
                    item,
                    selected=str(item.get("id") or item.get("url")) in selected_ids,
                    reason=replay_selection_reason(
                        item,
                        selected=str(item.get("id") or item.get("url")) in selected_ids,
                        eligible_ids=eligible_ids,
                        selected_authors=selected_authors,
                        latest_long_creation=latest_long_creation,
                    ),
                )
                for item in all_playbacks
            ],
        }
        write_json(delivery / "replay-selection.json", replay_selection)

        download_tasks: dict[str, Callable[[], list[dict[str, Any]]]] = {}
        if probe(source) is None:
            download_tasks["replay"] = lambda: acquire_replays(
                replays,
                source,
                run_dir,
                args.replay_connections,
            )
        else:
            stages.append({"name": "download_replays", "status": "cached", "path": str(source)})
        if not args.skip_event_clips:
            download_tasks["events"] = lambda: [run_logged(
                "download_events",
                [sys.executable, str(DOWNLOAD_EVENTS), str(match_json), "--output-dir", str(events),
                 "--report", str(delivery / "event-download.json"), "--workers", str(args.event_workers)],
                delivery / "logs" / "download-events.log",
            )]
        if download_tasks:
            stages.extend(run_parallel(download_tasks))

        source_probe = probe(source)
        downloaded_events = len(list(events.glob("*.mp4")))
        active_parts = sorted(str(path) for path in (run_dir / "source").rglob("*.part"))
        if source_probe is None:
            raise RuntimeError(f"replay validation failed: {source}")
        if downloaded_events != expected_events:
            raise RuntimeError(f"event count mismatch: expected {expected_events}, found {downloaded_events}")
        if active_parts:
            raise RuntimeError(f"active partial downloads remain: {active_parts}")

        if not args.download_only:
            processing: dict[str, Callable[[], list[dict[str, Any]]]] = {}
            if not args.skip_pure_preflight:
                processing["pure"] = lambda: pure_preflight(source, run_dir)
            if not args.skip_player_clips:
                if args.skip_event_clips:
                    raise ValueError("--skip-event-clips requires --skip-player-clips outside download-only mode")
                require_tools([PLAYER_SKILL / "scripts" / "remake_player_clips.py"])
                processing["players"] = lambda: player_clips(source, events, run_dir)
            if processing:
                stages.extend(run_parallel(processing))

        payload.update({
            "status": "ready_for_ai",
            "seconds": round(time.monotonic() - started, 3),
            "source": str(source),
            "source_duration_seconds": round(float(source_probe["format"]["duration"]), 3),
            "source_bytes": int(source_probe["format"]["size"]),
            "replay_candidate_count": len(all_replays),
            "replay_segment_count": len(replays),
            "replay_selection": str(delivery / "replay-selection.json"),
            "events_dir": str(events),
            "event_count": downloaded_events,
            "stages": stages,
            "ai_review": [
                "review pure-cut candidate contact sheet and approve deletion boundaries",
                "review highest-distance or overlapping player clip matches",
                "select and visually accept team and match-wide highlight plans",
            ],
            "resume_command": shlex.join([sys.executable, str(Path(__file__).resolve()), str(match_id),
                                            "--workspace", str(workspace)]),
        })
        write_json(report, payload)
        print(json.dumps({key: payload[key] for key in (
            "status", "matchID", "seconds", "source", "event_count", "ai_review"
        )}, ensure_ascii=False, indent=2))
        return 0
    except ReplayUnavailableError as exc:
        match = data.get("match", {})
        payload.update({
            "status": "waiting_for_replay",
            "seconds": round(time.monotonic() - started, 3),
            "reason": str(exc),
            "match": {
                "matchID": match.get("matchID"),
                "date": match.get("date"),
                "status": match.get("status"),
                "homeTeam": (match.get("homeTeam") or {}).get("name"),
                "awayTeam": (match.get("awayTeam") or {}).get("name"),
            },
            "stages": stages,
            "resume_command": shlex.join([sys.executable, str(Path(__file__).resolve()), str(match_id),
                                            "--workspace", str(workspace)]),
        })
        write_json(report, payload)
        print(json.dumps({
            "status": payload["status"],
            "matchID": match_id,
            "reason": payload["reason"],
            "match": payload["match"],
            "resume_command": payload["resume_command"],
        }, ensure_ascii=False, indent=2))
        return 2
    except Exception as exc:
        payload.update({
            "status": "failed",
            "seconds": round(time.monotonic() - started, 3),
            "error": str(exc),
            "stages": stages,
            "resume_command": shlex.join([sys.executable, str(Path(__file__).resolve()), str(match_id),
                                            "--workspace", str(workspace)]),
        })
        write_json(report, payload)
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
