#!/usr/bin/env python3
"""Locate labeled Xiaoqiumi event thumbnails inside one full-game replay."""

from __future__ import annotations

import argparse
import csv
import http.client
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


PLAYER_SCRIPT = Path(__file__).parents[1].parent / "basketball-player-clips" / "scripts" / "remake_player_clips.py"
SPEC = importlib.util.spec_from_file_location("basketball_player_clips_runtime", PLAYER_SCRIPT)
if not SPEC or not SPEC.loader:
    raise SystemExit(f"Unable to load player clip runtime: {PLAYER_SCRIPT}")
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)

ACTION_KEYWORDS = {"2分命中", "3分命中", "助攻", "抢断", "盖帽"}
USER_AGENT = "Mozilla/5.0"
SIGNATURE_W = 65
SIGNATURE_H = 36


@dataclass
class Event:
    event_id: str
    title: str
    team: str
    number: str
    player: str
    action: str
    period: str
    clock: str
    thumbnail_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-json", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--candidate-limit", type=int, default=250)
    parser.add_argument("--hash-cache", type=Path)
    parser.add_argument(
        "--period-start",
        action="append",
        default=[],
        metavar="PERIOD=SECONDS",
        help="Visually reviewed source start for a 12-minute period, for example 2=904.",
    )
    parser.add_argument("--stoppage-weight", type=float, default=0.2)
    parser.add_argument("--max-adjustment-seconds", type=float, default=30.0)
    parser.add_argument("--max-hamming-regression", type=int, default=128)
    parser.add_argument(
        "--audit-report",
        type=Path,
        help="Fail-closed event-location audit JSON (defaults beside output CSV).",
    )
    return parser.parse_args()


def collect_events(data: dict) -> list[Event]:
    containers = data.get("raw", {}).get("details", {}).get("集锦", {}).get("modeData") or []
    items: list[dict] = []
    for section in containers:
        items.extend((section.get("videos") or {}).get("collectVideos") or [])
    events: list[Event] = []
    for item in items:
        action = str(item.get("subName") or "")
        player = str(item.get("reletedPlayerName") or "").strip()
        thumbnail = str(item.get("urlThumbnail") or "").strip()
        title = str(item.get("title") or "").strip()
        if action not in ACTION_KEYWORDS or not player or not thumbnail:
            continue
        label = runtime.parse_clip_name(Path(title + ".mp4"))
        period = re.sub(r"(?:结束|完)$", "", label.period).strip()
        events.append(Event(
            event_id=str(item.get("id") or ""),
            title=title,
            team=str(item.get("teamName") or label.team),
            number=str(item.get("shirtNo") or label.number).removesuffix("号"),
            player=player,
            action=action,
            period=period,
            clock=label.clock,
            thumbnail_url=thumbnail,
        ))
    return sorted(
        events,
        key=lambda item: (
            runtime.period_rank(item.period),
            -runtime.clock_seconds(item.clock),
            item.title,
        ),
    )


def dhash(frame: bytes, width: int, height: int) -> int:
    bits = 0
    bit_position = 0
    for row in range(height):
        base = row * width
        for column in range(width - 1):
            if frame[base + column] > frame[base + column + 1]:
                bits |= 1 << bit_position
            bit_position += 1
    return bits


def signature_filter() -> str:
    return f"scale={SIGNATURE_W}:{SIGNATURE_H},format=gray"


def extract_overlay_hashes(video: Path) -> list[int]:
    frame_size = SIGNATURE_W * SIGNATURE_H
    process = subprocess.Popen(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
            "-an", "-vf", f"fps={runtime.HASH_FPS},{signature_filter()}",
            "-f", "rawvideo", "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    hashes: list[int] = []
    while True:
        frame = process.stdout.read(frame_size)
        if not frame:
            break
        if len(frame) != frame_size:
            break
        hashes.append(dhash(frame, SIGNATURE_W, SIGNATURE_H))
    _, stderr = process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode("utf-8", errors="replace"))
    return hashes


def thumbnail_hash(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    image = b""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                image = response.read()
            break
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    if not image:
        raise RuntimeError(f"unable to fetch event thumbnail after retries: {last_error}")
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0", "-vf", signature_filter(),
            "-frames:v", "1", "-f", "rawvideo", "pipe:1",
        ],
        input=image,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    expected = SIGNATURE_W * SIGNATURE_H
    if result.returncode or len(result.stdout) != expected:
        raise RuntimeError("unable to decode event thumbnail")
    return dhash(result.stdout, SIGNATURE_W, SIGNATURE_H)


def write_hash_cache(path: Path, hashes: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps({
        "signature": [SIGNATURE_W, SIGNATURE_H],
        "hashes": hashes,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fetch_thumbnail_hashes(
    events: list[Event],
    hashes: dict[str, int],
    cache_path: Path,
    workers: int,
) -> None:
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(thumbnail_hash, event.thumbnail_url): event for event in events}
        for future in as_completed(futures):
            event = futures[future]
            try:
                hashes[event.event_id] = future.result()
            except Exception as exc:
                failures[event.event_id] = str(exc)
                continue
            write_hash_cache(cache_path, hashes)
    if failures:
        sample = next(iter(failures.values()))
        raise RuntimeError(
            f"unable to fetch {len(failures)} event thumbnail(s) after retries; first error: {sample}"
        )


def best_thumbnail_match(source_hashes: list[int], target: int) -> tuple[int, int, int]:
    scores = [(value ^ target).bit_count() for value in source_hashes]
    best_index = min(range(len(scores)), key=scores.__getitem__)
    best_score = scores[best_index]
    exclusion = runtime.HASH_FPS * 5
    alternatives = [
        score for index, score in enumerate(scores)
        if abs(index - best_index) > exclusion
    ]
    second_score = min(alternatives) if alternatives else best_score
    return best_index, best_score, second_score


def candidate_matches(source_hashes: list[int], target: int, limit: int) -> list[tuple[int, int]]:
    scored = sorted(
        ((index, (value ^ target).bit_count()) for index, value in enumerate(source_hashes)),
        key=lambda item: (item[1], item[0]),
    )
    return scored[:max(1, limit)]


def game_elapsed(event: Event) -> float:
    rank = runtime.period_rank(event.period)
    clock = runtime.clock_seconds(event.clock)
    if rank >= 999 or clock < 0:
        return 0.0
    return (rank - 1) * 720 + (720 - clock)


def parse_period_starts(values: list[str]) -> dict[int, float]:
    starts: dict[int, float] = {}
    for value in values:
        period_text, separator, seconds_text = value.partition("=")
        if not separator:
            raise ValueError(f"invalid period start: {value}")
        starts[int(period_text)] = float(seconds_text)
    return starts


def location_anomalies(
    *,
    aligned_seconds: float,
    raw_seconds: float,
    aligned_hamming: int,
    best_hamming: int,
    max_adjustment_seconds: float,
    max_hamming_regression: int,
) -> list[str]:
    """Return blockers for a locator result that is unsafe to render automatically."""
    reasons: list[str] = []
    adjustment = abs(aligned_seconds - raw_seconds)
    regression = aligned_hamming - best_hamming
    if adjustment > max_adjustment_seconds:
        reasons.append("large_alignment_adjustment")
    if regression > max_hamming_regression:
        reasons.append("aligned_match_much_worse_than_raw_best")
    return reasons


def align_monotonic(
    events: list[Event],
    candidate_rows: list[list[tuple[int, int]]],
) -> list[tuple[int, int]]:
    if not events or len(events) != len(candidate_rows):
        raise ValueError("events and candidates must have the same non-zero length")
    costs: list[list[float]] = []
    previous: list[list[int]] = []
    first = candidate_rows[0]
    costs.append([score + (index / runtime.HASH_FPS) * 0.001 for index, score in first])
    previous.append([-1] * len(first))
    for row_index in range(1, len(events)):
        current = candidate_rows[row_index]
        prior = candidate_rows[row_index - 1]
        game_delta = max(0.0, game_elapsed(events[row_index]) - game_elapsed(events[row_index - 1]))
        row_costs = [float("inf")] * len(current)
        row_previous = [-1] * len(current)
        for current_index, (source_index, score) in enumerate(current):
            source_seconds = source_index / runtime.HASH_FPS
            for prior_index, (prior_source_index, _) in enumerate(prior):
                if costs[-1][prior_index] == float("inf"):
                    continue
                source_delta = source_seconds - prior_source_index / runtime.HASH_FPS
                if source_delta < game_delta - 2.0:
                    continue
                excess_stoppage = max(0.0, source_delta - game_delta)
                cost = costs[-1][prior_index] + score + excess_stoppage * 0.002
                if cost < row_costs[current_index]:
                    row_costs[current_index] = cost
                    row_previous[current_index] = prior_index
        if all(value == float("inf") for value in row_costs):
            raise RuntimeError(f"no monotonic thumbnail alignment at event {row_index + 1}")
        costs.append(row_costs)
        previous.append(row_previous)
    chosen_index = min(range(len(costs[-1])), key=costs[-1].__getitem__)
    chosen: list[tuple[int, int]] = []
    for row_index in range(len(events) - 1, -1, -1):
        chosen.append(candidate_rows[row_index][chosen_index])
        chosen_index = previous[row_index][chosen_index]
    return list(reversed(chosen))


def align_monotonic_dense(
    events: list[Event],
    source_hashes: list[int],
    target_hashes: list[int],
    *,
    period_starts: dict[int, float] | None = None,
    stoppage_weight: float = 0.2,
) -> list[tuple[int, int]]:
    if not events or len(events) != len(target_hashes):
        raise ValueError("events and target hashes must have the same non-zero length")
    sample_count = len(source_hashes)
    period_starts = period_starts or {}
    ordered_starts = sorted(period_starts.items())

    def bounds(event: Event) -> tuple[float, float]:
        rank = runtime.period_rank(event.period)
        clock = runtime.clock_seconds(event.clock)
        start = period_starts.get(rank, 0.0)
        minimum = start + max(0, 720 - clock) if clock >= 0 and rank in period_starts else 0.0
        later = [seconds for period, seconds in ordered_starts if period > rank]
        maximum = min(later) if later else sample_count / runtime.HASH_FPS
        return minimum - 2.0, maximum

    first_scores = [(value ^ target_hashes[0]).bit_count() for value in source_hashes]
    first_minimum, first_maximum = bounds(events[0])
    costs = [
        (
            score + max(0.0, index / runtime.HASH_FPS - first_minimum) * stoppage_weight
            if first_minimum <= index / runtime.HASH_FPS < first_maximum
            else float("inf")
        )
        for index, score in enumerate(first_scores)
    ]
    back_rows: list[list[int]] = [[-1] * sample_count]
    for row_index in range(1, len(events)):
        game_delta = max(0.0, game_elapsed(events[row_index]) - game_elapsed(events[row_index - 1]))
        minimum_samples = max(0, int((game_delta - 2.0) * runtime.HASH_FPS))
        adjusted_prefix_value = [float("inf")] * sample_count
        adjusted_prefix_index = [-1] * sample_count
        best_value = float("inf")
        best_index = -1
        for index, value in enumerate(costs):
            adjusted = value - stoppage_weight * index / runtime.HASH_FPS
            if adjusted < best_value:
                best_value = adjusted
                best_index = index
            adjusted_prefix_value[index] = best_value
            adjusted_prefix_index[index] = best_index
        row_costs = [float("inf")] * sample_count
        row_previous = [-1] * sample_count
        target = target_hashes[row_index]
        minimum_source, maximum_source = bounds(events[row_index])
        for source_index, source_hash in enumerate(source_hashes):
            source_seconds = source_index / runtime.HASH_FPS
            if source_seconds < minimum_source or source_seconds >= maximum_source:
                continue
            bound = source_index - minimum_samples
            if bound < 0:
                continue
            prior_index = adjusted_prefix_index[bound]
            if prior_index < 0:
                continue
            transition = stoppage_weight * (source_seconds - game_delta)
            row_costs[source_index] = (
                adjusted_prefix_value[bound]
                + transition
                + (source_hash ^ target).bit_count()
            )
            row_previous[source_index] = prior_index
        if all(value == float("inf") for value in row_costs):
            raise RuntimeError(f"no dense thumbnail alignment at event {row_index + 1}")
        costs = row_costs
        back_rows.append(row_previous)
    chosen_index = min(range(sample_count), key=costs.__getitem__)
    chosen: list[tuple[int, int]] = []
    for row_index in range(len(events) - 1, -1, -1):
        score = (source_hashes[chosen_index] ^ target_hashes[row_index]).bit_count()
        chosen.append((chosen_index, score))
        chosen_index = back_rows[row_index][chosen_index]
    return list(reversed(chosen))


def main() -> int:
    args = parse_args()
    data = json.loads(args.match_json.read_text(encoding="utf-8"))
    events = collect_events(data)
    if not events:
        raise SystemExit("No player-labeled event thumbnails found")
    cache_path = args.hash_cache or args.output_csv.with_suffix(".thumbnail-hashes.json")
    cache: dict[str, int] = {}
    if cache_path.is_file():
        cached_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached_payload.get("signature") == [SIGNATURE_W, SIGNATURE_H]:
            cache = {str(key): int(value) for key, value in (cached_payload.get("hashes") or {}).items()}
    hashes = {event.event_id: cache[event.event_id] for event in events if event.event_id in cache}
    missing = [event for event in events if event.event_id not in hashes]
    fetch_thumbnail_hashes(missing, hashes, cache_path, args.workers)
    source_hashes = extract_overlay_hashes(args.source.resolve())
    target_hashes = [hashes[event.event_id] for event in events]
    period_starts = parse_period_starts(args.period_start)
    aligned = align_monotonic_dense(
        events,
        source_hashes,
        target_hashes,
        period_starts=period_starts,
        stoppage_weight=args.stoppage_weight,
    )
    rows: list[dict[str, object]] = []
    blockers: list[dict[str, object]] = []
    for event, (index, aligned_score) in zip(events, aligned):
        raw_index, best, second = best_thumbnail_match(source_hashes, hashes[event.event_id])
        seconds = index / runtime.HASH_FPS
        raw_seconds = raw_index / runtime.HASH_FPS
        reasons = location_anomalies(
            aligned_seconds=seconds,
            raw_seconds=raw_seconds,
            aligned_hamming=aligned_score,
            best_hamming=best,
            max_adjustment_seconds=args.max_adjustment_seconds,
            max_hamming_regression=args.max_hamming_regression,
        )
        row: dict[str, object] = {
            "event_id": event.event_id,
            "title": event.title,
            "team": event.team,
            "number": event.number,
            "player": event.player,
            "action": event.action,
            "period": event.period,
            "clock": event.clock,
            "source_seconds": f"{seconds:.3f}",
            "source_time": runtime.fmt_time(seconds),
            "aligned_hamming": aligned_score,
            "raw_source_seconds": f"{raw_seconds:.3f}",
            "best_hamming": best,
            "second_hamming": second,
            "confidence_gap": second - best,
            "alignment_adjusted": index != raw_index,
            "adjustment_seconds": f"{seconds - raw_seconds:.3f}",
            "hamming_regression": aligned_score - best,
            "location_status": "blocked" if reasons else "accepted",
            "anomaly_reasons": ";".join(reasons),
        }
        rows.append(row)
        if reasons:
            blockers.append({
                "event_id": event.event_id,
                "title": event.title,
                "player": event.player,
                "period": event.period,
                "clock": event.clock,
                "adjustment_seconds": round(seconds - raw_seconds, 3),
                "aligned_hamming": aligned_score,
                "best_hamming": best,
                "reasons": reasons,
            })

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "event_id", "title", "team", "number", "player", "action", "period", "clock",
            "source_seconds", "source_time", "aligned_hamming", "raw_source_seconds",
            "best_hamming", "second_hamming", "confidence_gap", "alignment_adjusted",
            "adjustment_seconds", "hamming_regression", "location_status", "anomaly_reasons",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    audit_path = args.audit_report or args.output_csv.with_name("event-location-audit.json")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = {
        "status": "needs_attention" if blockers else "complete",
        "events": len(events),
        "accepted_events": len(events) - len(blockers),
        "blocked_events": len(blockers),
        "source_samples": len(source_hashes),
        "output_csv": str(args.output_csv.resolve()),
        "thresholds": {
            "max_adjustment_seconds": args.max_adjustment_seconds,
            "max_hamming_regression": args.max_hamming_regression,
        },
        "blockers": blockers,
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**audit, "audit_report": str(audit_path.resolve())}, ensure_ascii=False, indent=2))
    return 2 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
