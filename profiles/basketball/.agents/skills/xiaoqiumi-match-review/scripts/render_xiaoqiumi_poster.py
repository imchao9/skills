#!/usr/bin/env python3
"""Render Xiaoqiumi review poster HTML in five styles."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any


STYLES = ["cinematic-dark", "scoreboard-card", "newspaper", "neon-energy", "minimal-clean"]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def asset_url(path: str | None, out_dir: Path) -> str:
    if not path:
        return ""
    source = Path(path).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Asset does not exist: {source}")
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / source.name
    if source != target:
        shutil.copy2(source, target)
    return urllib.parse.quote(f"assets/{target.name}")


def slug(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip())
    return value.strip("-") or "poster"


def fmt_player(player: dict[str, Any]) -> str:
    no = player.get("playerNo")
    name = player.get("playerName") or "未知球员"
    prefix = f"{no}号{name}" if no else name
    return f"{prefix} {player.get('score', 0)}分 {player.get('totalBoards', 0)}板 {player.get('assists', 0)}助"


def stats_text(team: str, stats: dict[str, Any]) -> str:
    return f"{team} 篮板{stats.get('totalBoards', 0)} 助攻{stats.get('assists', 0)} 抢断{stats.get('steals', 0)} 失误{stats.get('error', 0)}"


def base_payload(data: dict[str, Any], photo: str | None, scoreboard_photo: str | None, out_dir: Path) -> dict[str, Any]:
    match = data["match"]
    home = match["homeTeam"]
    away = match["awayTeam"]
    home_score = int(home.get("score") or 0)
    away_score = int(away.get("score") or 0)
    winner = home if home_score >= away_score else away
    loser = away if winner is home else home
    winner_side = "home" if winner is home else "away"
    loser_side = "away" if winner_side == "home" else "home"
    periods = " / ".join(f"{p['label']} {p['home']}:{p['away']}" for p in data.get("periods", []))
    return {
        "match": match,
        "home": home,
        "away": away,
        "winner": winner,
        "loser": loser,
        "winnerSide": winner_side,
        "loserSide": loser_side,
        "winnerStats": data["teamStats"][winner_side],
        "loserStats": data["teamStats"][loser_side],
        "winnerLeaders": data["leaders"][f"{winner_side}Scorers"][:4],
        "loserLeaders": data["leaders"][f"{loser_side}Scorers"][:4],
        "periods": periods,
        "photo": asset_url(photo, out_dir),
        "scoreboardPhoto": asset_url(scoreboard_photo, out_dir),
    }


def render(style: str, payload: dict[str, Any]) -> str:
    match = payload["match"]
    home = payload["home"]
    away = payload["away"]
    winner = payload["winner"]
    loser = payload["loser"]
    photo_css = f"background-image: linear-gradient(90deg, rgba(0,0,0,.78), rgba(0,0,0,.38)), url('{payload['photo']}');" if payload["photo"] else ""
    scoreboard = f"<img class='scoreboard-img' src='{payload['scoreboardPhoto']}' alt='scoreboard'>" if payload["scoreboardPhoto"] else ""
    leaders = "".join(f"<li>{esc(fmt_player(p))}</li>" for p in payload["winnerLeaders"])
    loser_leaders = "".join(f"<li>{esc(fmt_player(p))}</li>" for p in payload["loserLeaders"])
    stat_a = esc(stats_text(winner["name"], payload["winnerStats"]))
    stat_b = esc(stats_text(loser["name"], payload["loserStats"]))
    article = (
        f"{winner['name']}以{winner['score']}:{loser['score']}拿下比赛。"
        f"球队在篮板保护、进攻延续和多人得分上更稳定，最终把优势保持到终场。"
        f"{loser['name']}核心球员持续回应，全队也在对抗中展现了韧性。"
    )
    classes = f"poster {style}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(winner['name'])} {esc(winner['score'])}:{esc(loser['score'])} {esc(loser['name'])}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #111; font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; }}
.poster {{ width: 1080px; height: 1440px; position: relative; overflow: hidden; padding: 58px 72px; color: #111; background: #f7f7f2; }}
.eyebrow {{ font-size: 24px; letter-spacing: 0; font-weight: 700; opacity: .78; }}
.title {{ font-size: 56px; line-height: 1.1; margin: 22px 0; font-weight: 900; }}
.score {{ display: flex; align-items: center; gap: 28px; margin: 24px 0; }}
.team {{ flex: 1; min-width: 0; }}
.team-name {{ font-size: 34px; font-weight: 850; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.team-score {{ font-size: 122px; font-weight: 950; line-height: .9; }}
.colon {{ font-size: 76px; font-weight: 900; opacity: .55; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 22px; }}
.box {{ border-radius: 8px; padding: 20px 22px; background: rgba(255,255,255,.82); border: 1px solid rgba(0,0,0,.12); }}
.box h3 {{ margin: 0 0 12px; font-size: 27px; }}
.box p {{ margin: 10px 0; font-size: 18px; line-height: 1.45; }}
.box ul {{ margin: 0; padding-left: 26px; font-size: 23px; line-height: 1.48; }}
.article {{ font-size: 27px; line-height: 1.42; margin-top: 22px; font-weight: 550; }}
.meta {{ position: absolute; left: 72px; right: 72px; bottom: 32px; display: flex; justify-content: space-between; font-size: 22px; opacity: .76; }}
.scoreboard-img {{ width: 100%; border-radius: 8px; display: block; object-fit: cover; max-height: 248px; }}
.cinematic-dark {{ color: #fff; background: radial-gradient(circle at 75% 20%, rgba(255,199,87,.35), transparent 32%), #111; {photo_css} background-size: cover; background-position: center; }}
.cinematic-dark .box {{ background: rgba(8,10,14,.68); border-color: rgba(255,255,255,.22); }}
.cinematic-dark .article {{ color: #f7f0de; }}
.cinematic-dark .team-score {{ color: #ffd35f; }}
.scoreboard-card {{ background: #17191f; color: #f6f6f6; }}
.scoreboard-card .box {{ background: #242833; border-color: #3f4657; }}
.scoreboard-card .title {{ color: #ffde72; }}
.scoreboard-card .score {{ background: #0b0d12; border: 2px solid #4b5568; padding: 28px; border-radius: 8px; }}
.newspaper {{ background: #f4efe4; color: #151515; padding: 58px 68px; }}
.newspaper .title {{ font-family: Georgia, "Times New Roman", serif; font-size: 64px; border-bottom: 4px solid #111; padding-bottom: 22px; }}
.newspaper .box {{ background: transparent; border: 2px solid #222; }}
.newspaper .article {{ column-count: 2; column-gap: 32px; font-size: 25px; }}
.neon-energy {{ background: linear-gradient(135deg, #080a14 0%, #121826 48%, #281313 100%); color: #f9fbff; }}
.neon-energy::before {{ content: ""; position: absolute; inset: 0; background: linear-gradient(118deg, transparent 0 56%, rgba(0,229,255,.26) 56% 68%, transparent 68%); }}
.neon-energy > * {{ position: relative; z-index: 1; }}
.neon-energy .team-score {{ color: #00e5ff; text-shadow: 0 0 22px rgba(0,229,255,.55); }}
.neon-energy .box {{ background: rgba(10,15,25,.86); border-color: rgba(255,255,255,.22); }}
.neon-energy .title {{ color: #ffea72; }}
.minimal-clean {{ background: #fbfbf8; color: #111; }}
.minimal-clean .title {{ font-size: 52px; }}
.minimal-clean .score {{ border-top: 4px solid #111; border-bottom: 4px solid #111; padding: 26px 0; }}
.minimal-clean .box {{ background: #fff; border-color: #ddd; }}
.minimal-clean .team-score {{ color: #1c5f8f; }}
</style>
</head>
<body>
<main class="{classes}">
  <div class="eyebrow">{esc(match.get('competitionName') or '篮球赛后复盘')} · {esc(match.get('roundName') or '')}</div>
  <h1 class="title">多点支撑稳住局面，{esc(winner['name'])}战胜{esc(loser['name'])}</h1>
  <section class="score">
    <div class="team">
      <div class="team-name">{esc(home['name'])}</div>
      <div class="team-score">{esc(home['score'])}</div>
    </div>
    <div class="colon">:</div>
    <div class="team">
      <div class="team-name">{esc(away['name'])}</div>
      <div class="team-score">{esc(away['score'])}</div>
    </div>
  </section>
  {scoreboard}
  <section class="grid">
    <div class="box">
      <h3>胜方得分点</h3>
      <ul>{leaders}</ul>
    </div>
    <div class="box">
      <h3>对手回应</h3>
      <ul>{loser_leaders}</ul>
    </div>
    <div class="box">
      <h3>团队数据</h3>
      <p>{stat_a}</p>
      <p>{stat_b}</p>
    </div>
    <div class="box">
      <h3>分节走势</h3>
      <p>{esc(payload['periods'] or '暂无分节数据')}</p>
    </div>
  </section>
  <p class="article">{esc(article)}</p>
  <div class="meta">
    <span>{esc(match.get('date') or '')}</span>
    <span>{esc(match.get('stadiumName') or '')}</span>
  </div>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Normalized JSON from fetch_xiaoqiumi_match.py.")
    parser.add_argument("--style", choices=STYLES + ["all"], default="cinematic-dark")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--photo", help="Optional court photo path.")
    parser.add_argument("--scoreboard-photo", help="Optional scoreboard photo path.")
    args = parser.parse_args()

    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = base_payload(data, args.photo, args.scoreboard_photo, args.out_dir)
    styles = STYLES if args.style == "all" else [args.style]
    match = data["match"]
    stem = slug(f"{match['homeTeam']['name']}-{match['homeTeam']['score']}-{match['awayTeam']['score']}-{match['awayTeam']['name']}")
    for style in styles:
        path = args.out_dir / f"{stem}-{style}.html"
        path.write_text(render(style, payload), encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
