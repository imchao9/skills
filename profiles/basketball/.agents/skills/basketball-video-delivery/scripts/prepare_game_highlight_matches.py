#!/usr/bin/env python3
"""Normalize rendered event rows for the condensed game-highlight builder."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_team_maps(values: list[str]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"team mapping must be OLD=NEW: {value}")
        old, new = value.split("=", 1)
        if not old or not new:
            raise ValueError(f"team mapping must be OLD=NEW: {value}")
        mappings[old] = new
    return mappings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add duration and quality fields required by make_condensed_reel.py."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--team-map", action="append", default=[], metavar="OLD=NEW")
    args = parser.parse_args()

    team_maps = parse_team_maps(args.team_map)
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"no rendered events: {args.input}")

    required = {"new_start", "new_end", "output"}
    missing = sorted(required - rows[0].keys())
    if missing:
        raise SystemExit(f"missing required columns: {', '.join(missing)}")

    output_fields = list(rows[0].keys())
    for field in ("new_duration", "avg_hamming"):
        if field not in output_fields:
            output_fields.append(field)

    for row in rows:
        row["team"] = team_maps.get(row["team"], row["team"])
        duration = parse_time(row["new_end"]) - parse_time(row["new_start"])
        if duration <= 0:
            raise SystemExit(f"invalid event duration for {row.get('title', row['output'])}")
        row["new_duration"] = f"{duration:.3f}"
        # OCR clock error is the available deterministic confidence signal in
        # rendered-matches.csv. Lower is better, matching the reel builder's
        # avg_hamming ordering semantics.
        row["avg_hamming"] = row.get("clock_error_seconds") or "0"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"events: {len(rows)}")
    print(f"teams: {', '.join(sorted({row['team'] for row in rows}))}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
