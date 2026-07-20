#!/usr/bin/env python3
"""Fetch Xiaoqiumi competition schedules and list recent matches."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.xiaoqiumi.co/api"
H5_MATCH_URL = "https://h5static.xiaoqiumi.com/littleFans/index.html#/pagesLive/MatchDetails/index"


def parse_comp_ref(ref: str, sport_type: int | None) -> tuple[int, int]:
    if ref.isdigit():
        return int(ref), sport_type or 1

    parsed = urllib.parse.urlparse(ref)
    pairs = urllib.parse.parse_qsl(parsed.query)
    if parsed.fragment:
        fragment = parsed.fragment
        if "?" in fragment:
            pairs.extend(urllib.parse.parse_qsl(fragment.split("?", 1)[1]))
        else:
            pairs.extend(urllib.parse.parse_qsl(fragment))

    query = {k.lower(): v for k, v in pairs}
    raw_comp_id = query.get("competitionid")
    if not raw_comp_id:
        match = re.search(r"competitionID=(\d+)", ref, re.I)
        raw_comp_id = match.group(1) if match else None
    if not raw_comp_id:
        raise SystemExit("Could not find competitionID in input.")

    return int(raw_comp_id), int(query.get("sporttype") or sport_type or 1)


def post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(4):
        req = urllib.request.Request(
            f"{API_BASE}/{endpoint}",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": "Mozilla/5.0 XiaoqiumiCompetitionFetcher/1.0",
                "Origin": "https://h5static.xiaoqiumi.com",
                "Referer": "https://h5static.xiaoqiumi.com/",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{endpoint} HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')}") from exc
        result = json.loads(body)
        if result.get("code") == 200 or result.get("status") in (1, "1", True):
            return result
        if result.get("msg") == "重复提交" and attempt < 3:
            time.sleep(1.2 + attempt * 0.8)
            continue
        raise RuntimeError(f"{endpoint} returned unexpected status: {result}")
    raise RuntimeError(f"{endpoint} failed after retries.")


def unwrap(response: dict[str, Any]) -> Any:
    return response.get("data")


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def match_url(match: dict[str, Any], competition_id: int, sport_type: int) -> str:
    query = urllib.parse.urlencode(
        {
            "competitionID": competition_id,
            "matchid": match.get("matchID"),
            "sportType": sport_type,
            "navlocked": "false",
            "hasAccessPassword": "false",
        }
    )
    return f"{H5_MATCH_URL}?{query}"


def normalize_match(match: dict[str, Any], competition_id: int, sport_type: int) -> dict[str, Any]:
    return {
        "matchID": match.get("matchID"),
        "competitionID": match.get("competitionID") or competition_id,
        "sportType": sport_type,
        "periodName": match.get("periodName"),
        "roundName": match.get("roundName"),
        "roundNum": match.get("roundNum"),
        "matchIndex": match.get("matchIndex"),
        "date": match.get("date"),
        "stadiumName": match.get("stadiumName"),
        "status": match.get("status"),
        "matchStatus": match.get("matchStatus"),
        "isHaveRecord": match.get("isHaveRecord"),
        "isHaveCollectVideo": match.get("isHaveCollectVideo"),
        "hasLive": match.get("hasLive"),
        "homeTeam": {
            "id": match.get("homeTeamID"),
            "name": match.get("homeTeamName"),
            "score": match.get("homeScoreAll"),
            "logo": match.get("homeTeamPhoto"),
        },
        "awayTeam": {
            "id": match.get("awayTeamID"),
            "name": match.get("awayTeamName"),
            "score": match.get("awayScoreAll"),
            "logo": match.get("awayTeamPhoto"),
        },
        "url": match_url(match, competition_id, sport_type),
    }


def current_period(periods: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((p for p in periods if p.get("isCuCurrentPeriod")), periods[0] if periods else None)


def current_round(period: dict[str, Any]) -> dict[str, Any] | None:
    rounds = period.get("dicList") or []
    return next((r for r in rounds if r.get("isCuCurrentGroup")), rounds[0] if rounds else None)


def schedule_payload(competition_id: int, sport_type: int, period: dict[str, Any], round_item: dict[str, Any] | None) -> dict[str, Any]:
    payload = {
        "CompetitionID": competition_id,
        "SportType": sport_type,
        "Mode": period.get("mode"),
        "PeriodID": period.get("periodID"),
        "RoundName": period.get("name"),
    }
    if round_item:
        payload["GroupId"] = round_item.get("groupId")
        payload["RoundName"] = round_item.get("name") or period.get("name")
    return payload


def flatten_schedule(schedule_data: list[dict[str, Any]], competition_id: int, sport_type: int) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for group in schedule_data or []:
        group_name = group.get("groupName")
        group_id = group.get("groupId")
        for item in group.get("groupScheduleList") or []:
            normalized = normalize_match(item, competition_id, sport_type)
            normalized["groupName"] = item.get("groupName") or group_name
            normalized["groupID"] = item.get("groupID") or group_id
            matches.append(normalized)
    return matches


def fetch_competition(ref: str, sport_type: int | None, all_rounds: bool) -> dict[str, Any]:
    competition_id, sport = parse_comp_ref(ref, sport_type)
    info_response = post("CompetitionInfo", {"SportType": sport, "CompetitionID": competition_id})
    info = unwrap(info_response) or {}
    season_id = info.get("seasonID")
    periods_response = post("CompPeriodList", {"SportType": sport, "CompetitionID": competition_id, "SeasonID": season_id, "Mode": 1})
    periods = unwrap(periods_response) or info.get("periods") or []

    targets: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    if all_rounds:
        for period in periods:
            rounds = period.get("dicList") or []
            if rounds:
                targets.extend((period, round_item) for round_item in rounds)
            else:
                targets.append((period, None))
    else:
        period = current_period(periods)
        if period:
            targets.append((period, current_round(period)))

    schedules = []
    matches: list[dict[str, Any]] = []
    seen_payloads: set[str] = set()
    for period, round_item in targets:
        payload = schedule_payload(competition_id, sport, period, round_item)
        key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if key in seen_payloads:
            continue
        seen_payloads.add(key)
        response = post("CompSchedule", payload)
        schedule_data = unwrap(response) or []
        schedules.append({"payload": payload, "data": schedule_data})
        matches.extend(flatten_schedule(schedule_data, competition_id, sport))

    deduped: dict[Any, dict[str, Any]] = {}
    for match in matches:
        deduped[match.get("matchID")] = match

    return {
        "source": {
            "input": ref,
            "apiBase": API_BASE,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "allRounds": all_rounds,
        },
        "competition": {
            "competitionID": competition_id,
            "sportType": sport,
            "seasonID": season_id,
            "competitionName": info.get("competitionName"),
            "shortName": info.get("shortName"),
            "startDate": info.get("startDate"),
            "endDate": info.get("endDate"),
            "stadium": info.get("stadium"),
        },
        "periods": periods,
        "matches": list(deduped.values()),
        "raw": {
            "competitionInfo": info_response,
            "periods": periods_response,
            "schedules": schedules,
        },
    }


def select_recent(matches: list[dict[str, Any]], limit: int, finished_only: bool) -> list[dict[str, Any]]:
    candidates = [m for m in matches if m.get("matchID")]
    if finished_only:
        candidates = [m for m in candidates if m.get("matchStatus") == 2 or m.get("status") == 9]
    now = datetime.now()

    def key(match: dict[str, Any]) -> tuple[int, datetime]:
        dt = parse_date(match.get("date")) or datetime.min
        return (abs(int((dt - now).total_seconds())), datetime.max - dt)

    return sorted(candidates, key=key)[:limit]


def write_list_md(data: dict[str, Any], matches: list[dict[str, Any]], path: Path) -> None:
    comp = data["competition"]
    lines = [
        f"# {comp.get('competitionName') or comp.get('shortName') or comp.get('competitionID')} 近期比赛",
        "",
        f"- competitionID: {comp.get('competitionID')}",
        f"- sportType: {comp.get('sportType')}",
        f"- 场地: {comp.get('stadium') or ''}",
        f"- 抓取时间: {data['source'].get('fetchedAt')}",
        "",
        "## Match List",
        "",
    ]
    for idx, match in enumerate(matches, start=1):
        home = match["homeTeam"]
        away = match["awayTeam"]
        score = f"{home.get('score')}:{away.get('score')}" if home.get("score") is not None or away.get("score") is not None else "vs"
        lines.append(
            f"{idx}. {match.get('date') or '未定'} | {match.get('periodName') or ''}{match.get('roundName') or ''} | "
            f"{home.get('name')} {score} {away.get('name')} | matchid={match.get('matchID')} | {match.get('url')}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("competition", help="Xiaoqiumi competition URL or numeric competitionID.")
    parser.add_argument("--sport-type", type=int, default=None, help="Sport type, default is parsed from URL or 1.")
    parser.add_argument("--all-rounds", action="store_true", help="Fetch every listed period/round instead of only the current one.")
    parser.add_argument("--recent-count", type=int, default=12, help="Number of recent/nearby matches to write to list Markdown.")
    parser.add_argument("--finished-only", action="store_true", help="Only include finished matches in the recent Markdown list.")
    parser.add_argument("--out", type=Path, required=True, help="Output full normalized JSON path.")
    parser.add_argument("--list-md", type=Path, help="Optional Markdown list path.")
    args = parser.parse_args()

    data = fetch_competition(args.competition, args.sport_type, args.all_rounds)
    recent = select_recent(data["matches"], args.recent_count, args.finished_only)
    data["recentMatches"] = recent
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.list_md:
        write_list_md(data, recent, args.list_md)
    print(f"Wrote {args.out}")
    print(f"Matches: {len(data['matches'])}; recent: {len(recent)}")
    if args.list_md:
        print(f"Wrote {args.list_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
