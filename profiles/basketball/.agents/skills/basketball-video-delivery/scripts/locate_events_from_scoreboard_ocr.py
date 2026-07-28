#!/usr/bin/env python3
"""Map Xiaoqiumi player events to a full replay using a scoreboard OCR index."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path


LOCATOR = Path(__file__).with_name("locate_event_thumbnails.py")
SPEC = importlib.util.spec_from_file_location("event_thumbnail_locator_runtime", LOCATOR)
if not SPEC or not SPEC.loader:
    raise SystemExit(f"Unable to load locator runtime: {LOCATOR}")
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)

CLOCK_RE = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)(?!\d)")


@dataclass
class Observation:
    source_seconds: float
    clock_seconds: int
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match-json", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--ocr-tsv", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--period-start", action="append", required=True, metavar="PERIOD=SECONDS")
    parser.add_argument(
        "--event-source-override",
        action="append",
        default=[],
        metavar="EVENT_ID=SOURCE@SECONDS",
    )
    return parser.parse_args()


def parse_ocr(path: Path) -> list[Observation]:
    observations: list[Observation] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            filename, separator, text = line.rstrip("\n").partition("\t")
            if not separator:
                continue
            match = CLOCK_RE.search(text)
            if not match:
                continue
            minutes, seconds = int(match.group(1)), int(match.group(2))
            if minutes > 12:
                continue
            frame_index = int(Path(filename).stem)
            observations.append(Observation(
                source_seconds=float(frame_index - 1),
                clock_seconds=minutes * 60 + seconds,
                text=text,
            ))
    return observations


def group_observations(items: list[Observation], gap: float = 2.1) -> list[list[Observation]]:
    groups: list[list[Observation]] = []
    for item in sorted(items, key=lambda value: value.source_seconds):
        if groups and item.source_seconds - groups[-1][-1].source_seconds <= gap:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def monotonic_period_observations(
    observations: list[Observation],
    minimum_source: float,
    maximum_source: float,
    upward_tolerance: int = 3,
) -> list[Observation]:
    """Discard clocks that jump backwards into an already-finished game time.

    OCR sometimes reads a timeout/stat overlay value such as ``2:00`` after
    the scoreboard clock has already reached ``1:03``.  A basketball period
    clock can pause, but it cannot increase before the next period starts.
    """
    accepted: list[Observation] = []
    lowest_clock = 720
    for item in observations:
        if not minimum_source <= item.source_seconds < maximum_source:
            continue
        if item.clock_seconds > lowest_clock + upward_tolerance:
            continue
        accepted.append(item)
        lowest_clock = min(lowest_clock, item.clock_seconds)
    return accepted


def choose_event_time(
    observations: list[Observation],
    target_clock: int,
    predictor: float,
    minimum_source: float,
    maximum_source: float,
) -> tuple[float, str, int]:
    in_window = [
        item for item in observations
        if minimum_source <= item.source_seconds < maximum_source
    ]
    for error in range(16):
        candidates = [
            item for item in in_window
            if abs(item.clock_seconds - target_clock) == error
        ]
        if not candidates:
            continue
        groups = group_observations(candidates)
        options: list[tuple[float, str, int]] = []
        for group in groups:
            representative = group[0]
            estimated = representative.source_seconds + (representative.clock_seconds - target_clock)
            options.append((estimated, representative.text, representative.clock_seconds))
        return min(options, key=lambda item: abs(item[0] - predictor))
    raise RuntimeError(f"no OCR clock near target {target_clock // 60:02d}:{target_clock % 60:02d}")


def main() -> int:
    args = parse_args()
    import json

    data = json.loads(args.match_json.read_text(encoding="utf-8"))
    events = runtime.collect_events(data)
    starts = runtime.parse_period_starts(args.period_start)
    overrides: dict[str, tuple[str, float]] = {}
    for value in args.event_source_override:
        event_id, separator, source_ref = value.partition("=")
        source_path, at, seconds_text = source_ref.rpartition("@")
        if not separator or not at:
            raise ValueError(f"invalid event source override: {value}")
        overrides[event_id] = (str(Path(source_path).resolve()), float(seconds_text))
    observations = parse_ocr(args.ocr_tsv)
    if not observations:
        raise SystemExit("No scoreboard clock observations found")
    ordered_starts = sorted(starts.items())
    rows: list[dict[str, str]] = []
    last_period = -1
    last_clock = -1
    last_source = -1.0
    for event in events:
        period = runtime.runtime.period_rank(event.period)
        target_clock = runtime.runtime.clock_seconds(event.clock)
        if period not in starts or target_clock < 0:
            raise RuntimeError(f"missing period anchor or clock for {event.title}")
        next_starts = [seconds for rank, seconds in ordered_starts if rank > period]
        maximum = min(next_starts) if next_starts else observations[-1].source_seconds + 2
        period_observations = monotonic_period_observations(
            observations,
            starts[period],
            maximum,
        )
        baseline = starts[period] + (720 - target_clock)
        if period == last_period:
            predictor = last_source + max(0, last_clock - target_clock)
            minimum = max(starts[period], last_source - 2)
        else:
            predictor = baseline
            minimum = starts[period]
        source_file = str(args.source.resolve())
        if event.event_id in overrides:
            source_file, source = overrides[event.event_id]
            text = ""
            recognized_clock = target_clock
            method = "continuation_override"
        else:
            try:
                source, text, recognized_clock = choose_event_time(
                    period_observations,
                    target_clock,
                    predictor,
                    minimum,
                    maximum,
                )
                method = "exact_ocr" if recognized_clock == target_clock else "neighbor_clock_interpolation"
            except RuntimeError:
                source = predictor
                text = ""
                recognized_clock = target_clock
                method = "event_sequence_interpolation"
        rows.append({
            "event_id": event.event_id,
            "title": event.title,
            "team": event.team,
            "number": event.number,
            "player": event.player,
            "action": event.action,
            "period": event.period,
            "clock": event.clock,
            "source": source_file,
            "source_seconds": f"{source:.3f}",
            "source_time": runtime.runtime.fmt_time(source),
            "recognized_clock": f"{recognized_clock // 60:02d}:{recognized_clock % 60:02d}",
            "clock_error_seconds": str(abs(recognized_clock - target_clock)),
            "predictor_seconds": f"{predictor:.3f}",
            "method": method,
            "ocr_text": text,
        })
        last_period = period
        last_clock = target_clock
        last_source = source
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    exact = sum(row["clock_error_seconds"] == "0" for row in rows)
    print(f"events={len(rows)} exact_clock={exact} output={args.output_csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
