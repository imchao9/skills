#!/usr/bin/env python3
"""Render a full-length Xiaoqiumi commentary as an editorial HTML poster."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any


TEAM_COLORS = {
    "松岗先锋队": ("#f4c94d", "#2468dc", "#ef3d4a"),
    "超流战队": ("#ff8a2a", "#f4c44d", "#20b8c8"),
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def asset_url(path: Path, out_dir: Path, embed: bool = False) -> str:
    source = path.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"Asset does not exist: {source}")
    if embed:
        media_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        payload = base64.b64encode(source.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{payload}"
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = (assets_dir / source.name).resolve()
    if source != target:
        shutil.copy2(source, target)
    return urllib.parse.quote(f"assets/{target.name}")


def slug(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip())
    return value.strip("-") or "longform-review"


def inline_markup(value: str) -> str:
    escaped = esc(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)


def markdown_article(markdown: str) -> tuple[str, str]:
    title = "完整球评"
    blocks: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(f"<p>{inline_markup(''.join(paragraph))}</p>")
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith("# "):
            flush()
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush()
            blocks.append(f"<h2>{esc(line[3:].strip())}</h2>")
            continue
        if line.startswith("> "):
            flush()
            blocks.append(f"<blockquote>{inline_markup(line[2:].strip())}</blockquote>")
            continue
        paragraph.append(line)
    flush()
    return title, "\n".join(blocks)


def shooting_rate(stats: dict[str, Any]) -> str:
    attempts = int(stats.get("shots") or 0)
    made = int(stats.get("shootNum") or 0)
    return f"{made / attempts * 100:.1f}%" if attempts else "0%"


def player_label(player: dict[str, Any]) -> str:
    number = player.get("playerNo")
    name = player.get("playerName") or "未知球员"
    return f"{number}号{name}" if number else str(name)


def metric_row(label: str, home: Any, away: Any, home_name: str, away_name: str) -> str:
    def numeric(value: Any) -> float:
        match = re.search(r"[\d.]+", str(value or 0))
        return float(match.group()) if match else 0.0

    home_value = numeric(home)
    away_value = numeric(away)
    maximum = max(home_value, away_value, 1)
    home_width = max(home_value / maximum * 100, 4)
    away_width = max(away_value / maximum * 100, 4)
    return f"""
    <div class="metric">
      <div class="metric-head"><span>{esc(label)}</span><strong>{esc(home)} <i>:</i> {esc(away)}</strong></div>
      <div class="bars">
        <div class="bar bar-home" style="width:{home_width:.1f}%"><span>{esc(home_name)}</span></div>
        <div class="bar bar-away" style="width:{away_width:.1f}%"><span>{esc(away_name)}</span></div>
      </div>
    </div>
    """


def render(data: dict[str, Any], article_md: str, photo_url: str) -> str:
    match = data["match"]
    home = match["homeTeam"]
    away = match["awayTeam"]
    home_score = int(home.get("score") or 0)
    away_score = int(away.get("score") or 0)
    winner_side = "home" if home_score >= away_score else "away"
    loser_side = "away" if winner_side == "home" else "home"
    winner = home if winner_side == "home" else away
    loser = away if winner_side == "home" else home
    winner_stats = data["teamStats"][winner_side]
    loser_stats = data["teamStats"][loser_side]
    home_stats = data["teamStats"]["home"]
    away_stats = data["teamStats"]["away"]
    leaders = data["leaders"][f"{winner_side}Scorers"][:3]
    mvp = leaders[0] if leaders else {}
    title, article_html = markdown_article(article_md)
    round_name = str(match.get("roundName") or "")
    round_match = re.search(r"\d+", round_name)
    round_number = int(round_match.group()) if round_match else 0
    round_label = f"{round_number:02d}" if round_number else "—"
    primary, secondary, opponent = TEAM_COLORS.get(winner["name"], ("#f4c94d", "#2468dc", "#ef3d4a"))
    periods = []
    for index, period in enumerate(data.get("periods", []), start=1):
        label = f"第{index}节" if index <= 4 else f"附加节{index - 4}"
        periods.append(f"<div class='period'><span>{esc(label)}</span><strong>{esc(period['home'])}:{esc(period['away'])}</strong></div>")

    metrics = "".join(
        [
            metric_row("篮板", home_stats.get("totalBoards"), away_stats.get("totalBoards"), home["name"], away["name"]),
            metric_row("投篮命中率", shooting_rate(home_stats), shooting_rate(away_stats), home["name"], away["name"]),
            metric_row("抢断", home_stats.get("steals"), away_stats.get("steals"), home["name"], away["name"]),
            metric_row("失误", home_stats.get("error"), away_stats.get("error"), home["name"], away["name"]),
        ]
    )
    supporting = "".join(
        f"<div class='support-player'><strong>{esc(player_label(player))}</strong><span>{esc(player.get('score', 0))}分 · {esc(player.get('totalBoards', 0))}板 · {esc(player.get('assists', 0))}助</span></div>"
        for player in leaders[1:]
    )
    rebound_margin = int(winner_stats.get("totalBoards") or 0) - int(loser_stats.get("totalBoards") or 0)
    if rebound_margin >= 8:
        story = f"{winner['name']}抢下{winner_stats.get('totalBoards', 0)}个篮板，以{winner['score']}:{loser['score']}赢下回合争夺。"
    else:
        story = f"{winner['name']}用更稳定的终结效率建立领先，以{winner['score']}:{loser['score']}把胜果保持到最后。"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root {{ --primary:{primary}; --secondary:{secondary}; --opponent:{opponent}; --ink:#111318; --paper:#f1eee5; }}
* {{ box-sizing:border-box; }}
html, body {{ margin:0; background:#111318; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; }}
.poster {{ width:1080px; min-height:3600px; height:auto; margin:0 auto; overflow:hidden; background:var(--paper); color:var(--ink); }}
.hero {{ height:900px; position:relative; padding:54px 68px; color:#fff; background-image:linear-gradient(180deg,rgba(6,9,16,.3) 0%,rgba(6,9,16,.78) 66%,#0a0d14 100%),linear-gradient(110deg,rgba(0,0,0,.2),transparent 58%),url('{photo_url}'); background-size:cover; background-position:center 62%; }}
.hero::before {{ content:""; position:absolute; inset:0; background:linear-gradient(118deg,transparent 0 55%,color-mix(in srgb,var(--primary) 42%,transparent) 55% 58%,transparent 58%),radial-gradient(circle at 78% 35%,color-mix(in srgb,var(--secondary) 45%,transparent),transparent 36%); }}
.hero > * {{ position:relative; z-index:1; }}
.kicker {{ display:flex; justify-content:space-between; align-items:center; padding-bottom:20px; border-bottom:1px solid rgba(255,255,255,.35); font-size:21px; font-weight:750; letter-spacing:.04em; }}
.edition, .section-label {{ color:var(--primary); }}
.headline {{ width:900px; margin:35px 0 24px; font-size:54px; line-height:1.12; font-weight:950; letter-spacing:-.035em; text-wrap:balance; }}
.scoreboard {{ display:grid; grid-template-columns:1fr 130px 1fr; align-items:end; margin-top:28px; }}
.side {{ min-width:0; }}
.side.away {{ text-align:right; }}
.team-name {{ font-size:34px; font-weight:850; white-space:nowrap; }}
.team-score {{ font-size:154px; line-height:.82; font-weight:950; color:var(--primary); text-shadow:0 8px 35px rgba(0,0,0,.45); }}
.versus {{ padding-bottom:18px; text-align:center; font-size:28px; font-weight:900; color:rgba(255,255,255,.62); }}
.result-line {{ display:flex; align-items:center; gap:16px; margin-top:32px; font-size:24px; font-weight:750; }}
.result-line::before {{ content:""; flex:0 0 68px; height:5px; background:var(--primary); }}
.insight {{ background:#0a0d14; color:#fff; padding:52px 68px 58px; }}
.section-label {{ font-size:18px; font-weight:900; letter-spacing:.16em; text-transform:uppercase; }}
.insight-grid {{ display:grid; grid-template-columns:1.08fr .92fr; gap:36px; margin-top:24px; }}
.mvp {{ position:relative; min-height:360px; padding:38px; overflow:hidden; background:linear-gradient(135deg,color-mix(in srgb,var(--secondary) 75%,#10141d),#10141d 70%); border-top:5px solid var(--primary); }}
.mvp::after {{ content:"{esc(mvp.get('playerNo') or '')}"; position:absolute; right:-5px; bottom:-50px; color:rgba(255,255,255,.09); font-size:250px; font-weight:950; line-height:1; }}
.mvp-tag {{ font-size:19px; font-weight:900; color:var(--primary); letter-spacing:.14em; }}
.mvp-name {{ margin-top:14px; font-size:53px; line-height:1.05; font-weight:950; }}
.mvp-score {{ margin-top:26px; font-size:82px; line-height:1; font-weight:950; color:var(--primary); }}
.mvp-score small {{ font-size:25px; margin-left:6px; }}
.mvp-line {{ margin-top:14px; font-size:24px; color:rgba(255,255,255,.82); }}
.support {{ display:flex; flex-direction:column; gap:16px; }}
.support-title {{ font-size:29px; font-weight:900; }}
.support-player {{ flex:1; display:flex; flex-direction:column; justify-content:center; padding:20px 24px; border-left:4px solid var(--opponent); background:rgba(255,255,255,.07); }}
.support-player strong {{ font-size:27px; }}
.support-player span {{ margin-top:7px; font-size:20px; color:rgba(255,255,255,.7); }}
.data-zone {{ padding:58px 68px 62px; background:#141820; color:#fff; }}
.data-head {{ display:flex; justify-content:space-between; align-items:end; margin-bottom:34px; }}
.data-head h2 {{ margin:8px 0 0; font-size:39px; }}
.data-head p {{ width:470px; margin:0; font-size:21px; line-height:1.55; color:rgba(255,255,255,.7); }}
.metric {{ margin:22px 0; }}
.metric-head {{ display:flex; justify-content:space-between; margin-bottom:10px; font-size:20px; }}
.metric-head strong {{ font-size:23px; }}
.metric-head i {{ margin:0 8px; color:rgba(255,255,255,.38); font-style:normal; }}
.bars {{ display:flex; flex-direction:column; gap:5px; }}
.bar {{ height:28px; display:flex; align-items:center; padding:0 12px; min-width:70px; font-size:14px; font-weight:850; white-space:nowrap; }}
.bar-home {{ background:linear-gradient(90deg,var(--opponent),color-mix(in srgb,var(--opponent) 45%,transparent)); }}
.bar-away {{ background:linear-gradient(90deg,var(--secondary),var(--primary)); color:#0a0d14; }}
.periods {{ display:grid; grid-template-columns:repeat(5,1fr); gap:3px; margin-top:40px; border-top:1px solid rgba(255,255,255,.18); padding-top:24px; }}
.period {{ padding:18px 12px; text-align:center; background:rgba(255,255,255,.06); }}
.period span {{ display:block; font-size:16px; color:rgba(255,255,255,.58); }}
.period strong {{ display:block; margin-top:7px; font-size:26px; }}
.article {{ padding:72px 68px 80px; background:var(--paper); }}
.article-header {{ display:grid; grid-template-columns:210px 1fr; gap:34px; margin-bottom:52px; padding-bottom:38px; border-bottom:4px solid var(--ink); }}
.article-index {{ font-size:76px; line-height:.9; font-weight:950; color:var(--primary); }}
.article-index small {{ display:block; margin-top:17px; font-size:16px; color:var(--ink); letter-spacing:.14em; }}
.article-title {{ margin:0; font-size:48px; line-height:1.16; letter-spacing:-.03em; }}
.article-deck {{ margin:16px 0 0; font-size:23px; line-height:1.55; color:#555b63; }}
.article-body {{ max-width:900px; font-family:"Songti SC","STSong",serif; font-size:27px; line-height:1.72; text-align:justify; }}
.article-body p {{ margin:0 0 1.05em; break-inside:avoid; }}
.article-body strong {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; font-weight:850; }}
.article-body code {{ padding:.08em .3em; border-radius:4px; background:#ddd7c9; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82em; }}
.article-body blockquote {{ margin:1.2em 0; padding:20px 24px; border-left:6px solid var(--primary); background:#e4dfd2; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; font-size:22px; line-height:1.55; }}
.article-body p:first-of-type::first-letter {{ float:left; margin:8px 10px 0 0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; font-size:78px; line-height:.7; font-weight:950; color:var(--primary); }}
.article-body h2 {{ break-after:avoid; margin:1.5em 0 .6em; padding-top:.45em; border-top:4px solid var(--primary); font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; font-size:28px; line-height:1.3; }}
.article-footer {{ display:flex; justify-content:space-between; align-items:center; margin-top:54px; padding-top:28px; border-top:1px solid #b8b1a3; font-size:17px; color:#65605a; }}
.article-footer strong {{ color:var(--ink); }}
</style>
</head>
<body>
<main class="poster">
  <section class="hero">
    <div class="kicker"><span>{esc(match.get('competitionName'))} · {esc(match.get('roundName'))}</span><span class="edition">FULL REVIEW / 完整球评</span></div>
    <h1 class="headline">{esc(title)}</h1>
    <div class="scoreboard">
      <div class="side home"><div class="team-name">{esc(home['name'])}</div><div class="team-score">{esc(home['score'])}</div></div>
      <div class="versus">FINAL<br>VS</div>
      <div class="side away"><div class="team-name">{esc(away['name'])}</div><div class="team-score">{esc(away['score'])}</div></div>
    </div>
    <div class="result-line">{esc(story)}</div>
  </section>
  <section class="insight">
    <div class="section-label">PLAYER IMPACT / 关键球员</div>
    <div class="insight-grid">
      <div class="mvp"><div class="mvp-tag">GAME MVP · 全场焦点</div><div class="mvp-name">{esc(player_label(mvp))}</div><div class="mvp-score">{esc(mvp.get('score', 0))}<small>分</small></div><div class="mvp-line">{esc(mvp.get('totalBoards', 0))} 篮板 · {esc(mvp.get('assists', 0))} 助攻 · {esc(mvp.get('steals', 0))} 抢断</div></div>
      <div class="support"><div class="support-title">胜方主要贡献</div>{supporting}</div>
    </div>
  </section>
  <section class="data-zone">
    <div class="data-head"><div><div class="section-label">MATCH DATA / 比赛拆解</div><h2>胜负藏在回合与效率里</h2></div><p>数据条按主队、客队顺序呈现。第五个计分段沿用接口记录，但不据此推断为常规加时。</p></div>
    {metrics}
    <div class="periods">{''.join(periods)}</div>
  </section>
  <article class="article">
    <header class="article-header"><div class="article-index">{round_label}<small>ROUND {round_number or '—'}</small></div><div><h2 class="article-title">{esc(title)}</h2><p class="article-deck">从比分走势、球员贡献、篮板与效率重新阅读这场比赛。以下为基于小球迷接口真实数据整理的完整赛后复盘。</p></div></header>
    <div class="article-body">{article_html}</div>
    <footer class="article-footer"><span>{esc(match.get('date'))} · {esc(match.get('stadiumName'))}</span><strong>ALPHA 篮球联赛 · 赛后复盘</strong></footer>
  </article>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--article-md", type=Path, required=True)
    parser.add_argument("--photo", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--embed-assets",
        action="store_true",
        help="Embed the hero photo as a data URL so the HTML is standalone.",
    )
    args = parser.parse_args()

    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    article_md = args.article_md.read_text(encoding="utf-8")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    photo_url = asset_url(args.photo, args.out_dir, args.embed_assets)
    match = data["match"]
    stem = slug(f"{match['homeTeam']['name']}-{match['homeTeam']['score']}-{match['awayTeam']['score']}-{match['awayTeam']['name']}-完整球评")
    output = args.out_dir / f"{stem}.html"
    output.write_text(render(data, article_md, photo_url), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
