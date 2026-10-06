#!/usr/bin/env python3
"""Generate a first-draft Chinese Xiaoqiumi basketball commentary from normalized facts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def fmt_player(player: dict[str, Any], detail: bool = False) -> str:
    name = player.get("playerName") or "未知球员"
    no = player.get("playerNo")
    label = f"{no}号{name}" if no else name
    if detail:
        return f"{label}得到{player.get('score', 0)}分、{player.get('totalBoards', 0)}个篮板、{player.get('assists', 0)}次助攻"
    return f"{label}{player.get('score', 0)}分"


def team_line(team_name: str, stats: dict[str, Any]) -> str:
    return (
        f"{team_name}全场拿下{stats.get('totalBoards', 0)}个篮板、送出{stats.get('assists', 0)}次助攻，"
        f"投篮{stats.get('shots', 0)}投{stats.get('shootNum', 0)}中，"
        f"三分{stats.get('threeShots', 0)}投{stats.get('threeShotNum', 0)}中，"
        f"罚球{stats.get('freeThrows', 0)}罚{stats.get('freeThrowNum', 0)}中，"
        f"同时有{stats.get('steals', 0)}次抢断和{stats.get('error', 0)}次失误。"
    )


def generate(data: dict[str, Any]) -> str:
    match = data["match"]
    home = match["homeTeam"]
    away = match["awayTeam"]
    home_score = int(home.get("score") or 0)
    away_score = int(away.get("score") or 0)
    winner = home if home_score >= away_score else away
    loser = away if winner is home else home
    winner_side = "home" if winner is home else "away"
    loser_side = "away" if winner_side == "home" else "home"
    winner_stats = data["teamStats"][winner_side]
    loser_stats = data["teamStats"][loser_side]
    winner_scorers = data["leaders"][f"{winner_side}Scorers"]
    loser_scorers = data["leaders"][f"{loser_side}Scorers"]
    winner_top = winner_scorers[0] if winner_scorers else {}
    loser_top = loser_scorers[0] if loser_scorers else {}
    periods = "，".join(f"{p['label']} {p['home']}:{p['away']}" for p in data.get("periods", []))
    title = f"# 多点支撑稳住局面，{winner['name']}{winner['score']}:{loser['score']}战胜{loser['name']}"

    winner_names = "、".join(fmt_player(p) for p in winner_scorers[:5])
    loser_names = "、".join(fmt_player(p) for p in loser_scorers[:5])

    return f"""{title}

在{match.get('competitionName') or '本场比赛'}{match.get('roundName') or ''}中，{winner['name']}以 **{winner['score']}:{loser['score']}** 战胜{loser['name']}。
本场比赛地点为{match.get('stadiumName') or '赛场'}，比赛时间为{match.get('date') or '未知时间'}。
从比分走势来看，双方分节比分为{periods or '暂无分节数据'}，比赛中段和收官阶段的稳定性，成为影响最终结果的重要因素。

## {winner['name']}整体更稳，关键得分点持续输出

{winner['name']}本场最突出的地方，是核心得分点和轮换球员都能在不同阶段贡献分数。
{fmt_player(winner_top, True) if winner_top else '球队核心球员承担了主要输出。'}，是球队进攻端最稳定的支点。
此外，{winner_names or '多名球员均有得分贡献'}，让球队在进攻端不至于陷入单点依赖。

从团队数据看，{team_line(winner['name'], winner_stats)}
这些数据说明，{winner['name']}并不是只靠一两个回合解决比赛，而是在篮板保护、回合延续和多人参与上逐渐建立主动权。

## {loser['name']}核心球员撑起进攻，全队没有轻易放弃

{loser['name']}虽然未能拿下比赛，但球队并非没有亮点。
{fmt_player(loser_top, True) if loser_top else '球队主要得分点承担了大量进攻任务。'}，在进攻端持续给对手制造压力。
除此之外，{loser_names or '多名队员也有得分入账'}，说明球队在追分阶段仍然保持了进攻参与度。

从统计上看，{team_line(loser['name'], loser_stats)}
面对比分压力，{loser['name']}仍然维持了对抗强度，也在篮板和防守回合里尽力咬住比赛。

## 胜负关键：篮板、效率与稳定性

本场比赛的差距，主要体现在进攻效率和关键阶段的稳定性上。
{winner['name']}在篮板球上拿到{winner_stats.get('totalBoards', 0)}个，{loser['name']}拿到{loser_stats.get('totalBoards', 0)}个。
当比赛进入拉锯阶段，更多的篮板保护和二次进攻机会，往往会放大领先方的容错率。

同时，{winner['name']}全场送出{winner_stats.get('assists', 0)}次助攻，{loser['name']}送出{loser_stats.get('assists', 0)}次助攻。
两队都不是完全依靠个人单打，但{winner['name']}在比分转换和终结环节上更加稳定，最终把优势保持到了最后。

## 赛后复盘

对{winner['name']}来说，这场胜利的价值在于整体性。
球队既有稳定高分点，也有篮板、抢断、助攻等环节的持续支撑，后续只要继续控制失误和提升投篮选择，仍有继续提升空间。

对{loser['name']}来说，失利并不意味着整场比赛缺乏竞争力。
球队核心球员打出了存在感，队友也在不同阶段提供回应。
接下来的关键，是在保持对抗强度的同时，进一步提升进攻选择和关键回合的处理质量。

篮球比赛从来不只是比分。
胜利属于发挥更稳定的一方，而坚持、对抗和团队投入，同样是这场比赛值得被记住的部分。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Normalized JSON from fetch_xiaoqiumi_match.py.")
    parser.add_argument("--out", type=Path, required=True, help="Output Markdown path.")
    args = parser.parse_args()

    data = json.loads(args.json_path.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generate(data), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
