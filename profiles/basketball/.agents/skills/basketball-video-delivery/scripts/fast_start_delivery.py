#!/usr/bin/env python3
"""Refresh, download, and deterministically prepare a basketball delivery before AI review."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
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
from urllib.parse import urlsplit


SKILL_DIR = Path(__file__).parents[1]
SKILLS_DIR = SKILL_DIR.parent
FETCH_MATCH = SKILLS_DIR / "xiaoqiumi-match-review" / "scripts" / "fetch_xiaoqiumi_match.py"
DOWNLOAD_REPLAY = SKILL_DIR / "scripts" / "xiaoqiumi_download.py"
ASSEMBLE_REPLAYS = SKILL_DIR / "scripts" / "assemble_replay_segments.py"
DOWNLOAD_EVENTS = SKILL_DIR / "scripts" / "download_event_clips.py"
LOCATE_EVENTS = SKILL_DIR / "scripts" / "locate_event_thumbnails.py"
RENDER_DIRECT_EVENTS = SKILL_DIR / "scripts" / "render_player_reels_from_matches.py"
PURE_SKILL = SKILLS_DIR / "basketball-pure-cut"
PLAYER_SKILL = SKILLS_DIR / "basketball-player-clips"
ACTION_KEYWORDS = {"2分命中", "3分命中", "助攻", "抢断", "盖帽"}


class ReplayUnavailableError(ValueError):
    """Raised when refreshed public match data does not contain a replay yet."""


class ReplayDownloadNeedsAttention(RuntimeError):
    """Raised when replay chunks are preserved but automatic recovery is exhausted."""

    def __init__(self, report: Path, payload: dict[str, Any]) -> None:
        super().__init__(str(payload.get("reason") or payload.get("error") or "download needs attention"))
        self.report = report
        self.payload = payload


class EventDirectNeedsAttention(RuntimeError):
    """Raised when metadata cannot support trustworthy direct event rendering."""


class DiskPreflightNeedsAttention(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(str(payload["reason"]))
        self.payload = payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", help="Xiaoqiumi match URL or numeric match ID.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--event-workers", type=int, default=2)
    parser.add_argument("--replay-connections", type=int, default=8)
    parser.add_argument("--replay-download-attempts", type=int, default=3)
    parser.add_argument("--replay-stall-seconds", type=float, default=90)
    parser.add_argument("--replay-slow-window-seconds", type=float, default=300)
    parser.add_argument("--replay-min-speed-mib", type=float, default=1.0)
    parser.add_argument("--replay-health-grace-seconds", type=float, default=120)
    parser.add_argument("--replay-max-eta-seconds", type=float, default=3600)
    parser.add_argument("--replay-eta-grace-seconds", type=float, default=600)
    parser.add_argument("--download-only", action="store_true", help="Stop before deterministic editing preflight.")
    parser.add_argument(
        "--event-source",
        choices=("direct", "platform"),
        default="direct",
        help="Locate events in the full replay by default; use platform only as an explicit fallback.",
    )
    parser.add_argument(
        "--skip-event-clips",
        action="store_true",
        help="Deprecated compatibility alias for --event-source direct.",
    )
    parser.add_argument("--skip-pure-preflight", action="store_true")
    parser.add_argument("--skip-player-clips", action="store_true")
    parser.add_argument("--skip-disk-preflight", action="store_true")
    parser.add_argument("--disk-reserve-gib", type=float, default=0.5)
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


def direct_event_count(data: dict[str, Any]) -> int:
    return sum(
        1
        for item in video_container(data).get("collectVideos") or []
        if (
            item.get("subName") in ACTION_KEYWORDS
            and str(item.get("reletedPlayerName") or "").strip()
            and str(item.get("urlThumbnail") or "").strip()
        )
    )


def event_direct_fingerprint(match_json: Path, source: Path) -> str:
    data = json.loads(match_json.read_text(encoding="utf-8"))
    events = []
    for item in video_container(data).get("collectVideos") or []:
        if item.get("subName") not in ACTION_KEYWORDS:
            continue
        thumbnail = str(item.get("urlThumbnail") or "")
        events.append({
            key: item.get(key)
            for key in ("id", "title", "teamName", "shirtNo", "reletedPlayerName", "subName")
        } | {"thumbnail_path": urlsplit(thumbnail).path})
    digest = hashlib.sha256(
        json.dumps(sorted(events, key=lambda item: str(item.get("id"))), ensure_ascii=False, sort_keys=True).encode()
    )
    size = source.stat().st_size
    digest.update(str(size).encode("ascii"))
    with source.open("rb") as handle:
        for offset in (0, max(0, size // 2 - 512 * 1024), max(0, size - 1024 * 1024)):
            handle.seek(offset)
            digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_local_name(value: str) -> str:
    return value.replace("/", "-").replace("\0", "").strip()


def require_tools(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if shutil.which("ffprobe") is None:
        missing.append("ffprobe")
    if missing:
        raise FileNotFoundError(f"missing required tools: {missing}")


def disk_preflight(run_dir: Path, source_bytes: int, reserve_gib: float) -> dict[str, Any]:
    usage = shutil.disk_usage(run_dir)
    reserve = max(0, int(reserve_gib * 1024 ** 3))
    estimated_outputs = int(source_bytes * 1.6)
    required_free = estimated_outputs + reserve
    payload = {
        "name": "disk_preflight",
        "status": "complete" if usage.free >= required_free else "needs_attention",
        "available_bytes": usage.free,
        "source_bytes": source_bytes,
        "estimated_final_and_peak_temporary_bytes": estimated_outputs,
        "reserve_bytes": reserve,
        "required_free_bytes": required_free,
        "shortfall_bytes": max(0, required_free - usage.free),
    }
    if payload["status"] != "complete":
        payload["reason"] = (
            f"insufficient disk space: need {required_free} free bytes, have {usage.free}"
        )
        raise DiskPreflightNeedsAttention(payload)
    return payload


def acquire_replays(
    replays: list[dict[str, Any]],
    source: Path,
    run_dir: Path,
    connections: int,
    download_options: list[str] | None = None,
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
        report = delivery / f"xiaoqiumi-download-{index:02d}.json"
        health_report = delivery / f"xiaoqiumi-download-{index:02d}-health.json"
        command = [
            sys.executable,
            str(DOWNLOAD_REPLAY),
            "--output",
            str(segment),
            "--url-stdin",
            "--report",
            str(report),
            "--health-report",
            str(health_report),
            "--connections",
            str(connections),
        ]
        command.extend(download_options or [])
        try:
            stages.append(run_logged(
                f"download_replay_segment_{index:02d}",
                command,
                delivery / "logs" / f"download-replay-{index:02d}.log",
                stdin_text=str(replay["url"]) + "\n",
            ))
        except RuntimeError:
            if report.is_file():
                download_payload = json.loads(report.read_text(encoding="utf-8"))
                if download_payload.get("status") == "needs_attention":
                    raise ReplayDownloadNeedsAttention(report, download_payload)
            raise

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


def event_direct_player_clips(
    source: Path,
    match_json: Path,
    run_dir: Path,
    expected_events: int,
    event_workers: int,
) -> list[dict[str, Any]]:
    if expected_events <= 0:
        raise EventDirectNeedsAttention(
            "no player-labeled event thumbnails are available for event-direct rendering; "
            "use --event-source platform or --skip-player-clips"
        )
    output = run_dir / "output" / "player-clips-front15"
    reports = output / "reports"
    locations = reports / "event-locations.csv"
    location_audit = reports / "event-location-audit.json"
    stat_audit = reports / "event-stat-audit.json"
    action_evidence = reports / "action-evidence.json"
    matches = reports / "matches.csv"
    players = reports / "players.csv"
    cache = reports / "event-direct-cache.json"
    stages: list[dict[str, Any]] = []
    fingerprint = event_direct_fingerprint(match_json, source)
    cached_payload = {}
    if cache.is_file():
        try:
            cached_payload = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached_payload = {}
    cached_reels = sorted((output / "个人精彩集锦").glob("*.mp4"))
    if (
        locations.is_file()
        and
        matches.is_file()
        and players.is_file()
        and cached_payload.get("fingerprint") == fingerprint
        and location_audit.is_file()
        and json.loads(location_audit.read_text(encoding="utf-8")).get("status") == "complete"
        and stat_audit.is_file()
        and json.loads(stat_audit.read_text(encoding="utf-8")).get("status") == "complete"
        and action_evidence.is_file()
        and json.loads(action_evidence.read_text(encoding="utf-8")).get("status") == "complete"
        and cached_payload.get("locations_sha256") == file_sha256(locations)
        and cached_payload.get("matches_sha256") == file_sha256(matches)
        and cached_reels
        and all(probe(path) is not None for path in cached_reels)
    ):
        return [{"name": "event_direct_player_clips", "status": "cached", "path": str(output)}]

    if not locations.is_file() or cached_payload.get("fingerprint") != fingerprint:
        try:
            stages.append(run_logged(
                "locate_event_thumbnails",
                [
                    sys.executable, str(LOCATE_EVENTS), "--match-json", str(match_json),
                    "--source", str(source), "--output-csv", str(locations),
                    "--audit-report", str(location_audit), "--workers", str(event_workers),
                ],
                run_dir / "output" / "delivery" / "logs" / "locate-event-thumbnails.log",
            ))
        except RuntimeError as exc:
            if location_audit.is_file():
                audit = json.loads(location_audit.read_text(encoding="utf-8"))
                if audit.get("status") == "needs_attention":
                    raise EventDirectNeedsAttention(
                        f"event locator blocked {audit.get('blocked_events')} anomalous row(s); "
                        f"review {location_audit} or use --event-source platform"
                    ) from exc
            raise
    else:
        stages.append({"name": "locate_event_thumbnails", "status": "cached", "path": str(locations)})

    with locations.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not location_audit.is_file():
        raise EventDirectNeedsAttention(f"missing fail-closed location audit: {location_audit}")
    audit = json.loads(location_audit.read_text(encoding="utf-8"))
    if audit.get("status") != "complete" or audit.get("blockers"):
        raise EventDirectNeedsAttention(f"event location audit did not pass: {location_audit}")
    if len(rows) != expected_events:
        raise RuntimeError(
            f"event-direct location count mismatch: expected {expected_events}, found {len(rows)}"
        )
    seen_titles: dict[str, int] = {}
    for row in rows:
        if row.get("location_status") != "accepted":
            raise EventDirectNeedsAttention(
                f"event location is not accepted: {row.get('event_id')} {row.get('title')}"
            )
        title = row["title"]
        seen_titles[title] = seen_titles.get(title, 0) + 1
        if seen_titles[title] > 1:
            row["title"] = f"{title}_{row['event_id'][:8]}"
        row["source"] = str(source.resolve())
    matches.parent.mkdir(parents=True, exist_ok=True)
    with matches.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    command = [
        sys.executable, str(RENDER_DIRECT_EVENTS), "--matches-csv", str(matches),
        "--output-dir", str(output), "--match-json", str(match_json),
        "--contact-sheets", "--low-peak",
    ]
    stages.append(run_logged(
        "render_event_direct_player_clips",
        command,
        run_dir / "output" / "delivery" / "logs" / "render-event-direct-player-clips.log",
    ))
    write_json(cache, {
        "version": 2,
        "fingerprint": fingerprint,
        "locations_sha256": file_sha256(locations),
        "matches_sha256": file_sha256(matches),
        "location_audit": str(location_audit.resolve()),
    })
    return stages


def run_parallel(tasks: dict[str, Callable[[], list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {pool.submit(task): name for name, task in tasks.items()}
        for future in as_completed(futures):
            stages.extend(future.result())
    return stages


def main() -> int:
    args = parse_args()
    if args.skip_event_clips and args.event_source == "platform":
        raise SystemExit("--skip-event-clips conflicts with --event-source platform")
    event_source = "direct" if args.skip_event_clips else args.event_source
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
        "event_source": event_source,
        "stages": stages,
    }
    write_json(report, payload)

    try:
        required = [FETCH_MATCH, DOWNLOAD_REPLAY, ASSEMBLE_REPLAYS]
        required.append(DOWNLOAD_EVENTS if event_source == "platform" else LOCATE_EVENTS)
        require_tools(required)
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
        metadata_events = direct_event_count(data)
        expected_downloaded_events = event_count(data) if event_source == "platform" else 0
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

        replay_download_options = [
            "--max-attempts", str(args.replay_download_attempts),
            "--stall-seconds", str(args.replay_stall_seconds),
            "--slow-window-seconds", str(args.replay_slow_window_seconds),
            "--min-speed-mib", str(args.replay_min_speed_mib),
            "--health-grace-seconds", str(args.replay_health_grace_seconds),
            "--max-eta-seconds", str(args.replay_max_eta_seconds),
            "--eta-grace-seconds", str(args.replay_eta_grace_seconds),
        ]
        download_tasks: dict[str, Callable[[], list[dict[str, Any]]]] = {}
        if probe(source) is None:
            download_tasks["replay"] = lambda: acquire_replays(
                replays,
                source,
                run_dir,
                args.replay_connections,
                replay_download_options,
            )
        else:
            stages.append({"name": "download_replays", "status": "cached", "path": str(source)})
        if event_source == "platform":
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
        if event_source == "platform" and downloaded_events != expected_downloaded_events:
            raise RuntimeError(
                f"event count mismatch: expected {expected_downloaded_events}, found {downloaded_events}"
            )
        if active_parts:
            raise RuntimeError(f"active partial downloads remain: {active_parts}")
        if not args.download_only and not args.skip_disk_preflight:
            stages.append(disk_preflight(
                run_dir,
                int(source_probe["format"]["size"]),
                args.disk_reserve_gib,
            ))

        if not args.download_only:
            processing: dict[str, Callable[[], list[dict[str, Any]]]] = {}
            if not args.skip_pure_preflight:
                processing["pure"] = lambda: pure_preflight(source, run_dir)
            if not args.skip_player_clips:
                if event_source == "direct":
                    require_tools([RENDER_DIRECT_EVENTS])
                    processing["players"] = lambda: event_direct_player_clips(
                        source, match_json, run_dir, metadata_events, args.event_workers
                    )
                else:
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
            "event_source": event_source,
            "event_metadata_count": metadata_events,
            "event_download_count": downloaded_events if event_source == "platform" else 0,
            "event_count": metadata_events if event_source == "direct" else downloaded_events,
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
    except ReplayDownloadNeedsAttention as exc:
        download = exc.payload
        partial_files = sorted(str(path) for path in (run_dir / "source").rglob("*.part"))
        payload.update({
            "status": "needs_attention",
            "phase": "replay_download",
            "seconds": round(time.monotonic() - started, 3),
            "reason": str(exc),
            "download_report": str(exc.report),
            "health_report": download.get("health_report"),
            "download": {
                key: download.get(key)
                for key in (
                    "downloaded_bytes", "total_bytes", "progress_percent",
                    "speed_mib_per_second", "eta_seconds", "attempt",
                    "max_attempts", "chunks_preserved", "failures",
                )
            },
            "partial_files": partial_files,
            "stages": stages,
            "action_required": (
                "Inspect network/CDN health. Resume with the command below; retained chunks "
                "will be reused when the remote object and range layout are unchanged."
            ),
            "auto_shutdown_allowed": False,
            "resume_command": shlex.join([sys.executable, str(Path(__file__).resolve()), str(match_id),
                                            "--workspace", str(workspace)]),
        })
        write_json(report, payload)
        print(json.dumps({
            "status": payload["status"],
            "matchID": match_id,
            "phase": payload["phase"],
            "reason": payload["reason"],
            "download": payload["download"],
            "resume_command": payload["resume_command"],
        }, ensure_ascii=False, indent=2))
        return 3
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
    except EventDirectNeedsAttention as exc:
        platform_reference_command = shlex.join([
            sys.executable, str(Path(__file__).resolve()), str(match_id),
            "--workspace", str(workspace), "--event-source", "platform",
        ])
        pure_only_command = shlex.join([
            sys.executable, str(Path(__file__).resolve()), str(match_id),
            "--workspace", str(workspace), "--skip-player-clips",
        ])
        payload.update({
            "status": "needs_attention",
            "phase": "event_location",
            "seconds": round(time.monotonic() - started, 3),
            "reason": str(exc),
            "event_source": event_source,
            "event_metadata_count": metadata_events,
            "event_download_count": 0,
            "replay_segment_count": len(replays),
            "replay_selection": str((delivery / "replay-selection.json").resolve()),
            "assembled_source": str(source.resolve()),
            "standard_package_blocked": True,
            "sparse_event_policy": "do_not_create_or_claim player reels without player identity",
            "fallback_options": {
                "platform_reference_command": platform_reference_command,
                "pure_only_command": pure_only_command,
                "warning": "platform references do not satisfy personal-reel delivery when player identity is absent",
            },
            "stages": stages,
            "action_required": (
                "Review or assign missing player identities. Platform clips may be fetched only as references; "
                "do not mark the standard package complete without trustworthy player reels."
            ),
            "resume_command": shlex.join([
                sys.executable, str(Path(__file__).resolve()), str(match_id),
                "--workspace", str(workspace),
            ]),
            "auto_shutdown_allowed": False,
        })
        write_json(report, payload)
        print(json.dumps({
            "status": payload["status"],
            "matchID": match_id,
            "phase": payload["phase"],
            "reason": payload["reason"],
            "resume_command": payload["resume_command"],
        }, ensure_ascii=False, indent=2))
        return 2
    except DiskPreflightNeedsAttention as exc:
        payload.update({
            "status": "needs_attention",
            "phase": "disk_preflight",
            "seconds": round(time.monotonic() - started, 3),
            "reason": str(exc),
            "disk": exc.payload,
            "stages": stages,
            "action_required": "Free disk space, then run the resume command; the downloaded replay is retained.",
            "resume_command": shlex.join([
                sys.executable, str(Path(__file__).resolve()), str(match_id),
                "--workspace", str(workspace),
            ]),
            "auto_shutdown_allowed": False,
        })
        write_json(report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
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
