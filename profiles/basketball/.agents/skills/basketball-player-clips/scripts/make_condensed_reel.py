#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PERIOD_ORDER = {
    "第一节": 1,
    "第二节": 2,
    "第三节": 3,
    "第四节": 4,
}
SCORING_ACTIONS = {"2分命中", "3分命中"}
ACTION_PRIORITY = {
    "3分命中": 100,
    "盖帽": 94,
    "抢断": 90,
    "2分命中": 86,
    "助攻": 82,
}


@dataclass(frozen=True)
class Event:
    row: dict[str, str]
    period_rank: int
    clock_seconds: int
    source_start: float
    source_end: float
    duration: float
    hamming: float
    output: Path


@dataclass
class Cluster:
    idx: int
    events: list[Event]
    chosen: Event
    score: float


def clock_seconds(value: str) -> int:
    parts = value.replace("-", "_").replace(":", "_").split("_")
    if len(parts) != 2:
        return -1
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return -1


def period_rank(value: str) -> int:
    if value in PERIOD_ORDER:
        return PERIOD_ORDER[value]
    if value.startswith("加时"):
        suffix = value[2:] or "1"
        try:
            return 4 + int(suffix)
        except ValueError:
            return 99
    return 99


def parse_report_time(value: str) -> float:
    hh, mm, rest = value.split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(rest)


def game_order_key(event: Event) -> tuple[int, int, str]:
    return (event.period_rank, -event.clock_seconds, event.output.name)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def read_events(matches_csv: Path) -> list[Event]:
    base_dir = matches_csv.parent.parent
    events: list[Event] = []
    with matches_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            output = Path(row["output"])
            if not output.is_absolute():
                output = base_dir / output
            events.append(
                Event(
                    row=row,
                    period_rank=period_rank(row["period"]),
                    clock_seconds=clock_seconds(row["clock"]),
                    source_start=parse_report_time(row["new_start"]),
                    source_end=parse_report_time(row["new_end"]),
                    duration=float(row["new_duration"]),
                    hamming=float(row["avg_hamming"]),
                    output=output,
                )
            )
    return events


def representative(events: list[Event]) -> Event:
    has_assist = any(event.row["action"] == "助攻" for event in events)
    has_score = any(event.row["action"] in SCORING_ACTIONS for event in events)

    def key(event: Event) -> tuple[int, int, float, int]:
        action = event.row["action"]
        clutch_score = 1 if action in SCORING_ACTIONS and (
            event.row["period"].startswith("加时") and 0 <= event.clock_seconds <= 90
            or event.row["period"] == "第四节" and 0 <= event.clock_seconds <= 120
        ) else 0
        assist_score_pair = 1 if has_assist and has_score and action == "助攻" else 0
        return (
            clutch_score,
            assist_score_pair,
            ACTION_PRIORITY.get(action, 0),
            -event.hamming,
            event.clock_seconds,
        )

    return max(events, key=key)


def cluster_score(cluster_events: list[Event], chosen: Event) -> float:
    actions = {event.row["action"] for event in cluster_events}
    score = ACTION_PRIORITY.get(chosen.row["action"], 0)
    score += min(len(cluster_events), 4) * 5
    if "助攻" in actions and actions & SCORING_ACTIONS:
        score += 18
    if "3分命中" in actions:
        score += 10
    if "盖帽" in actions:
        score += 8
    if "抢断" in actions:
        score += 5
    if chosen.row["period"].startswith("加时"):
        score += 28
    if chosen.row["period"] == "第四节" and 0 <= chosen.clock_seconds <= 120:
        score += 22
    if chosen.row["period"].startswith("加时") and 0 <= chosen.clock_seconds <= 180:
        score += 18
    if chosen.row["action"] in SCORING_ACTIONS and (
        chosen.row["period"].startswith("加时")
        or (chosen.row["period"] == "第四节" and 0 <= chosen.clock_seconds <= 120)
    ):
        score += 16
    score -= max(chosen.hamming - 45, 0) * 0.35
    return score


def build_clusters(events: list[Event], window_seconds: int, overlap_gap: float) -> list[Cluster]:
    sorted_events = sorted(events, key=game_order_key)
    groups: list[list[Event]] = []
    current: list[Event] = []
    current_source_end = -math.inf
    for event in sorted_events:
        if (
            current
            and event.period_rank == current[-1].period_rank
            and (
                abs(event.clock_seconds - current[-1].clock_seconds) <= window_seconds
                or event.source_start <= current_source_end + overlap_gap
            )
        ):
            current.append(event)
            current_source_end = max(current_source_end, event.source_end)
        else:
            if current:
                groups.append(current)
            current = [event]
            current_source_end = event.source_end
    if current:
        groups.append(current)

    clusters: list[Cluster] = []
    for idx, group in enumerate(groups, 1):
        chosen = representative(group)
        clusters.append(Cluster(idx=idx, events=group, chosen=chosen, score=cluster_score(group, chosen)))
    return clusters


def select_clusters(clusters: list[Cluster], target_min: float, min_seconds: float, max_seconds: float) -> list[Cluster]:
    avg_duration = sum(cluster.chosen.duration for cluster in clusters) / len(clusters)
    target_count = max(1, round(target_min / avg_duration))
    by_period: dict[int, list[Cluster]] = {}
    for cluster in clusters:
        by_period.setdefault(cluster.chosen.period_rank, []).append(cluster)
    for period_clusters in by_period.values():
        period_clusters.sort(key=lambda cluster: (-cluster.score, game_order_key(cluster.chosen)))

    total_clusters = len(clusters)
    quotas: dict[int, int] = {}
    for period, period_clusters in by_period.items():
        quotas[period] = max(1, round(len(period_clusters) / total_clusters * target_count))

    selected: list[Cluster] = []
    selected_ids: set[int] = set()
    for period in sorted(by_period):
        for cluster in by_period[period][: quotas[period]]:
            selected.append(cluster)
            selected_ids.add(cluster.idx)

    def duration(items: list[Cluster]) -> float:
        return sum(item.chosen.duration for item in items)

    ranked = sorted(clusters, key=lambda cluster: (-cluster.score, game_order_key(cluster.chosen)))
    for cluster in ranked:
        if duration(selected) >= min_seconds:
            break
        if cluster.idx not in selected_ids:
            selected.append(cluster)
            selected_ids.add(cluster.idx)

    while duration(selected) > max_seconds:
        removable = [
            cluster
            for cluster in selected
            if sum(1 for item in selected if item.chosen.period_rank == cluster.chosen.period_rank) > 1
        ]
        if not removable:
            break
        victim = min(removable, key=lambda cluster: (cluster.score, -cluster.chosen.duration))
        selected.remove(victim)
        selected_ids.remove(victim.idx)

    for cluster in ranked:
        next_duration = duration(selected) + cluster.chosen.duration
        if next_duration > max_seconds:
            continue
        if duration(selected) >= target_min:
            break
        if cluster.idx not in selected_ids:
            selected.append(cluster)
            selected_ids.add(cluster.idx)

    rebalance_assists(selected)
    return sorted(selected, key=lambda cluster: game_order_key(cluster.chosen))


def rebalance_assists(selected: list[Cluster]) -> None:
    max_assists = max(1, round(len(selected) * 0.45))

    def assist_count() -> int:
        return sum(1 for cluster in selected if cluster.chosen.row["action"] == "助攻")

    def best_non_assist(cluster: Cluster) -> Event | None:
        alternatives = [event for event in cluster.events if event.row["action"] != "助攻"]
        if not alternatives:
            return None
        return max(
            alternatives,
            key=lambda event: (
                ACTION_PRIORITY.get(event.row["action"], 0),
                -event.hamming,
                event.clock_seconds,
            ),
        )

    replacement_candidates: list[tuple[int, float, Cluster, Event]] = []
    for cluster in selected:
        if cluster.chosen.row["action"] != "助攻":
            continue
        alternative = best_non_assist(cluster)
        if alternative is None:
            continue
        replacement_candidates.append(
            (
                ACTION_PRIORITY.get(alternative.row["action"], 0),
                -alternative.hamming,
                cluster,
                alternative,
            )
        )

    replacement_candidates.sort(reverse=True, key=lambda item: (item[0], item[1]))
    for _, _, cluster, alternative in replacement_candidates:
        if assist_count() <= max_assists:
            break
        cluster.chosen = alternative


def dedupe_selected_by_source_window(selected: list[Cluster], min_gap: float) -> list[Cluster]:
    kept: list[Cluster] = []
    by_score = sorted(selected, key=lambda cluster: (-cluster.score, game_order_key(cluster.chosen)))
    for cluster in by_score:
        overlaps = False
        for existing in kept:
            same_period = cluster.chosen.period_rank == existing.chosen.period_rank
            source_overlap = cluster.chosen.source_start < existing.chosen.source_end + min_gap and existing.chosen.source_start < cluster.chosen.source_end + min_gap
            if same_period and source_overlap:
                overlaps = True
                break
        if not overlaps:
            kept.append(cluster)
    return sorted(kept, key=lambda cluster: game_order_key(cluster.chosen))


def concat_outputs(outputs: list[Path], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    concat_file = target.with_suffix(".concat.txt")
    concat_file.write_text(
        "\n".join("file '" + str(path.resolve()).replace("'", "'\\''") + "'" for path in outputs) + "\n",
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", str(target),
        ]
    )


def materialize_event(event: Event) -> None:
    source_text = event.row.get("source") or ""
    if event.output.is_file() and not source_text:
        return
    if not source_text:
        raise SystemExit(f"Missing output clip and source path: {event.output}")
    source = Path(source_text).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Missing source replay: {source}")
    event.output.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{event.source_start:.3f}", "-i", str(source),
        "-t", f"{event.duration:.3f}", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-c:a", "aac", "-b:a", "128k",
        "-avoid_negative_ts", "make_zero", str(event.output),
    ])


def write_selection_report(selected: list[Cluster], output: Path) -> None:
    report = output.with_name(output.stem + "_selection.csv")
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cluster",
                "period",
                "clock",
                "team",
                "number",
                "player",
                "action",
                "duration",
                "score",
                "members",
                "output",
            ],
        )
        writer.writeheader()
        for cluster in selected:
            chosen = cluster.chosen
            members = " | ".join(
                f"{event.row['team']} {event.row['number']} {event.row['player']} {event.row['action']} {event.row['period']} {event.row['clock']}".strip()
                for event in cluster.events
            )
            writer.writerow(
                {
                    "cluster": cluster.idx,
                    "period": chosen.row["period"],
                    "clock": chosen.row["clock"],
                    "team": chosen.row["team"],
                    "number": chosen.row["number"],
                    "player": chosen.row["player"],
                    "action": chosen.row["action"],
                    "duration": f"{chosen.duration:.3f}",
                    "score": f"{cluster.score:.3f}",
                    "members": members,
                    "output": str(chosen.output),
                }
            )


def contact_sheet(video: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            "fps=1/15,scale=320:-1,tile=6x4",
            "-frames:v",
            "1",
            str(output),
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a condensed 5-7 minute basketball highlight reel")
    parser.add_argument("--matches-csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-seconds", type=float, default=300.0)
    parser.add_argument("--target-seconds", type=float, default=360.0)
    parser.add_argument("--max-seconds", type=float, default=420.0)
    parser.add_argument("--cluster-window", type=int, default=10)
    parser.add_argument("--overlap-gap", type=float, default=2.0)
    parser.add_argument("--selected-min-gap", type=float, default=2.0)
    parser.add_argument("--contact-sheet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    events = read_events(args.matches_csv)
    if not events:
        raise SystemExit("No events in matches CSV")
    clusters = build_clusters(events, args.cluster_window, args.overlap_gap)
    selected = select_clusters(clusters, args.target_seconds, args.min_seconds, args.max_seconds)
    selected = dedupe_selected_by_source_window(selected, args.selected_min_gap)
    selected_duration = sum(cluster.chosen.duration for cluster in selected)
    if selected_duration < args.min_seconds:
        ranked = sorted(clusters, key=lambda cluster: (-cluster.score, game_order_key(cluster.chosen)))
        selected_by_id = {cluster.idx for cluster in selected}
        for cluster in ranked:
            if cluster.idx in selected_by_id:
                continue
            candidate = dedupe_selected_by_source_window(selected + [cluster], args.selected_min_gap)
            candidate_duration = sum(item.chosen.duration for item in candidate)
            if len(candidate) == len(selected) + 1 and candidate_duration <= args.max_seconds:
                selected = candidate
                selected_by_id.add(cluster.idx)
                if candidate_duration >= args.min_seconds:
                    break
    total_duration = sum(cluster.chosen.duration for cluster in selected)
    if not (args.min_seconds <= total_duration <= args.max_seconds):
        raise SystemExit(
            f"Selected duration {total_duration:.3f}s is outside "
            f"{args.min_seconds:.3f}-{args.max_seconds:.3f}s"
        )

    for cluster in selected:
        materialize_event(cluster.chosen)
    concat_outputs([cluster.chosen.output for cluster in selected], args.output)
    write_selection_report(selected, args.output)
    if args.contact_sheet:
        contact_sheet(args.output, args.output.with_name(args.output.stem + "_contact_sheet.jpg"))

    print(f"clusters: {len(clusters)}")
    print(f"selected: {len(selected)}")
    print(f"duration: {total_duration:.3f}")
    print(f"output: {args.output}")
    print(f"selection report: {args.output.with_name(args.output.stem + '_selection.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
