#!/usr/bin/env python3
"""Fetch and normalize Xiaoqiumi basketball match data."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.xiaoqiumi.co/api"
KNOWN_TABS = {
    "赛况": "4529f187-1492-4556-a756-affa52458fd1",
    "数据": "ece45680-f934-4539-92c1-bf42b72238fb",
    "阵容": "818ea8ff-c2f9-4ae8-b41f-8be0e19c2b52",
    "集锦": "6b59bc76-9d1f-4be3-b697-527422611d3b",
}


def parse_match_ref(ref: str, sport_type: int | None) -> tuple[int, int]:
    if ref.isdigit():
        return int(ref), sport_type or 1

    query_parts: list[tuple[str, str]] = []
    parsed = urllib.parse.urlparse(ref)
    query_parts.extend(urllib.parse.parse_qsl(parsed.query))
    if parsed.fragment:
        fragment = parsed.fragment
        if "?" in fragment:
            query_parts.extend(urllib.parse.parse_qsl(fragment.split("?", 1)[1]))
        else:
            query_parts.extend(urllib.parse.parse_qsl(fragment))

    query = {k.lower(): v for k, v in query_parts}
    raw_matchid = query.get("matchid") or query.get("matchid".lower())
    if not raw_matchid:
        match = re.search(r"matchid=(\d+)", ref, re.I)
        raw_matchid = match.group(1) if match else None
    if not raw_matchid:
        raise SystemExit("Could not find matchid in input.")

    raw_sport_type = query.get("sporttype")
    return int(raw_matchid), int(raw_sport_type or sport_type or 1)


def post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 XiaoqiumiMatchReview/1.0",
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
    if result.get("code") != 200 and result.get("status") not in (1, "1", True):
        raise RuntimeError(f"{endpoint} returned unexpected status: {result}")
    return result


def unwrap(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def find_section(mode_data: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for section in mode_data:
        if section.get("sectionName") == name:
            return section
    return {}


def stat_map(section: dict[str, Any]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for row in section.get("sectionList") or []:
        title = row.get("title") or row.get("key")
        if title:
            result[str(title)] = {"home": row.get("home"), "away": row.get("away")}
    return result


def normalize_player(player: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "playerID",
        "playerName",
        "playerNo",
        "isStart",
        "playingTime",
        "score",
        "shots",
        "shootNum",
        "threeShots",
        "threeShotNum",
        "freeThrows",
        "freeThrowNum",
        "attackBoard",
        "defensiveBoard",
        "totalBoards",
        "assists",
        "foul",
        "fouls",
        "steals",
        "error",
        "blocks",
        "twoShots",
        "twoShotNum",
    ]
    return {key: player.get(key) for key in keys if key in player}


def normalize_periods(score_section: dict[str, Any]) -> list[dict[str, Any]]:
    rows = score_section.get("sectionList") or []
    if not rows:
        return []
    row = rows[0]
    home_list = row.get("homeList") or []
    away_list = row.get("awayList") or []
    home_scores = home_list[1:-1] if len(home_list) >= 3 else []
    away_scores = away_list[1:-1] if len(away_list) >= 3 else []
    periods = []
    for idx, (home, away) in enumerate(zip(home_scores, away_scores), start=1):
        label = f"Q{idx}" if idx <= 4 else f"OT{idx - 4}"
        periods.append({"label": label, "home": int(home), "away": int(away)})
    return periods


def top_players(players: list[dict[str, Any]], metric: str, limit: int = 5) -> list[dict[str, Any]]:
    return sorted(players, key=lambda p: (p.get(metric) or 0, p.get("score") or 0), reverse=True)[:limit]


def fetch_match(ref: str, sport_type: int | None) -> dict[str, Any]:
    match_id, sport = parse_match_ref(ref, sport_type)
    match_info_response = post("MatchInfo", {"sportType": sport, "MatchID": match_id})
    match_info = unwrap(match_info_response)

    tabs_by_name: dict[str, str] = {}
    for tab in match_info.get("tabs") or []:
        if tab.get("tabName") and tab.get("tabId"):
            tabs_by_name[str(tab["tabName"])] = str(tab["tabId"])
    for name, tab_id in KNOWN_TABS.items():
        tabs_by_name.setdefault(name, tab_id)

    details: dict[str, Any] = {}
    for name, tab_id in tabs_by_name.items():
        try:
            details[name] = unwrap(post("MatchDetail", {"sportType": sport, "MatchID": match_id, "tabId": tab_id}))
        except Exception as exc:  # noqa: BLE001 - keep partial data useful.
            details[name] = {"_error": str(exc), "tabId": tab_id}

    game_detail = details.get("赛况") if isinstance(details.get("赛况"), dict) else {}
    mode_data = game_detail.get("modeData") or []
    score_section = find_section(mode_data, "比分统计")
    best_section = find_section(mode_data, "全场最佳")
    full_stats_section = find_section(mode_data, "全场统计")
    team_stats_section = find_section(mode_data, "篮球球队统计")
    player_section = find_section(mode_data, "球员统计")

    home_players = [normalize_player(p) for p in player_section.get("homePlayers") or []]
    away_players = [normalize_player(p) for p in player_section.get("awayPlayers") or []]

    normalized = {
        "source": {
            "input": ref,
            "apiBase": API_BASE,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        },
        "match": {
            "sportType": sport,
            "matchID": match_id,
            "competitionID": match_info.get("competitionID"),
            "competitionName": match_info.get("competitionName"),
            "roundName": match_info.get("roundName"),
            "date": match_info.get("date"),
            "stadiumName": match_info.get("stadiumName") or match_info.get("stadium"),
            "status": match_info.get("status"),
            "homeTeam": {
                "id": match_info.get("homeTeamID"),
                "name": match_info.get("homeTeamName"),
                "score": match_info.get("homeScoreAll"),
                "logo": match_info.get("homeTeamPhoto"),
            },
            "awayTeam": {
                "id": match_info.get("awayTeamID"),
                "name": match_info.get("awayTeamName"),
                "score": match_info.get("awayScoreAll"),
                "logo": match_info.get("awayTeamPhoto"),
            },
        },
        "tabs": tabs_by_name,
        "periods": normalize_periods(score_section),
        "best": best_section.get("sectionList") or [],
        "fullStats": stat_map(full_stats_section),
        "teamStats": {
            "home": team_stats_section.get("homeTeamStat") or {},
            "away": team_stats_section.get("awayTeamStat") or {},
        },
        "players": {
            "home": home_players,
            "away": away_players,
        },
        "leaders": {
            "homeScorers": top_players(home_players, "score"),
            "awayScorers": top_players(away_players, "score"),
            "homeRebounders": top_players(home_players, "totalBoards"),
            "awayRebounders": top_players(away_players, "totalBoards"),
            "homeAssists": top_players(home_players, "assists"),
            "awayAssists": top_players(away_players, "assists"),
        },
        "raw": {
            "matchInfo": match_info_response,
            "details": details,
        },
    }
    return normalized


def player_line(player: dict[str, Any]) -> str:
    no = player.get("playerNo")
    name = player.get("playerName") or "未知球员"
    prefix = f"{no}号{name}" if no else name
    return f"{prefix} {player.get('score', 0)}分 {player.get('totalBoards', 0)}篮板 {player.get('assists', 0)}助攻"


def write_facts_md(data: dict[str, Any], path: Path) -> None:
    match = data["match"]
    home = match["homeTeam"]
    away = match["awayTeam"]
    periods = " / ".join(f"{p['label']} {p['home']}:{p['away']}" for p in data["periods"]) or "无分节数据"
    home_stats = data["teamStats"]["home"]
    away_stats = data["teamStats"]["away"]
    lines = [
        f"# {home['name']} {home['score']}:{away['score']} {away['name']}",
        "",
        f"- 比赛: {match.get('competitionName') or ''} {match.get('roundName') or ''}".strip(),
        f"- 时间: {match.get('date') or '未知'}",
        f"- 场地: {match.get('stadiumName') or '未知'}",
        f"- 分节: {periods}",
        f"- 球队统计（命中/出手）: {home['name']} 篮板{home_stats.get('totalBoards', 0)} 助攻{home_stats.get('assists', 0)} 抢断{home_stats.get('steals', 0)} 失误{home_stats.get('error', 0)} 投篮{home_stats.get('shootNum', 0)}/{home_stats.get('shots', 0)} 三分{home_stats.get('threeShotNum', 0)}/{home_stats.get('threeShots', 0)} 罚球{home_stats.get('freeThrowNum', 0)}/{home_stats.get('freeThrows', 0)}",
        f"- 球队统计（命中/出手）: {away['name']} 篮板{away_stats.get('totalBoards', 0)} 助攻{away_stats.get('assists', 0)} 抢断{away_stats.get('steals', 0)} 失误{away_stats.get('error', 0)} 投篮{away_stats.get('shootNum', 0)}/{away_stats.get('shots', 0)} 三分{away_stats.get('threeShotNum', 0)}/{away_stats.get('threeShots', 0)} 罚球{away_stats.get('freeThrowNum', 0)}/{away_stats.get('freeThrows', 0)}",
        "",
        "## 得分点",
        "",
        f"- {home['name']}: " + "；".join(player_line(p) for p in data["leaders"]["homeScorers"]),
        f"- {away['name']}: " + "；".join(player_line(p) for p in data["leaders"]["awayScorers"]),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", help="Xiaoqiumi match URL or numeric matchid.")
    parser.add_argument("--sport-type", type=int, default=None, help="Sport type, default is parsed from URL or 1.")
    parser.add_argument("--out", type=Path, required=True, help="Output normalized JSON path.")
    parser.add_argument("--facts-md", type=Path, help="Optional human-readable facts Markdown path.")
    args = parser.parse_args()

    data = fetch_match(args.match, args.sport_type)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.facts_md:
        write_facts_md(data, args.facts_md)
    print(f"Wrote {args.out}")
    if args.facts_md:
        print(f"Wrote {args.facts_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
