#!/usr/bin/env python3
"""Audit a Xiaoqiumi long-form review against normalized match facts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def display_periods(data: dict[str, Any]) -> list[dict[str, Any]]:
    periods = list(data.get("periods") or [])
    match = data["match"]
    final = (
        int(match["homeTeam"].get("score") or 0),
        int(match["awayTeam"].get("score") or 0),
    )
    regulation = periods[:4]
    regulation_sum = (
        sum(int(item.get("home") or 0) for item in regulation),
        sum(int(item.get("away") or 0) for item in regulation),
    )
    if len(regulation) == 4 and regulation_sum == final:
        return regulation
    selected = list(regulation)
    running = list(regulation_sum)
    for period in periods[4:]:
        selected.append(period)
        running[0] += int(period.get("home") or 0)
        running[1] += int(period.get("away") or 0)
        if tuple(running) == final:
            break
    return selected


def audit_article(data: dict[str, Any], article: str) -> dict[str, Any]:
    match = data["match"]
    home = match["homeTeam"]
    away = match["awayTeam"]
    final = (int(home.get("score") or 0), int(away.get("score") or 0))
    shown = display_periods(data)
    shown_sum = (
        sum(int(item.get("home") or 0) for item in shown),
        sum(int(item.get("away") or 0) for item in shown),
    )
    errors: list[str] = []
    warnings: list[str] = []
    if shown_sum != final:
        errors.append(f"计分段合计 {shown_sum[0]}:{shown_sum[1]} 与终场 {final[0]}:{final[1]} 不一致")
    regulation_complete = len(data.get("periods") or []) >= 4 and len(shown) == 4
    if regulation_complete and re.search(r"(?:OT\s*\d*|加时\w*|附加节\w*)[^\n。；]{0,20}0\s*[:：]\s*0", article, re.I):
        errors.append("四节比分已构成终场，文案不得呈现 OT/加时 0:0 占位记录")
    for pattern, label in ((r"(\d+)投(\d+)中", "投篮"), (r"(\d+)罚(\d+)中", "罚球")):
        for attempts, made in re.findall(pattern, article):
            if int(made) > int(attempts):
                errors.append(f"{label}描述倒置：{attempts}{'投' if label == '投篮' else '罚'}{made}中")
    expected_three_gap = abs(
        int(data["teamStats"]["home"].get("threeShotNum") or 0)
        - int(data["teamStats"]["away"].get("threeShotNum") or 0)
    ) * 3
    for value in re.findall(r"三分(?:球)?(?:得到的)?分数相差\s*(\d+)分", article):
        if int(value) != expected_three_gap:
            errors.append(f"三分得分差应为 {expected_three_gap} 分，文案写为 {value} 分")
    errors.extend(
        f"终场文案缺少关键事实：{fact}"
        for fact in (
            home["name"] if home["name"] not in article else "",
            away["name"] if away["name"] not in article else "",
        )
        if fact
    )
    unreliable = [
        field for field in ("error",)
        if int(data["teamStats"]["home"].get(field) or 0) == 0
        and int(data["teamStats"]["away"].get(field) or 0) == 0
    ]
    if unreliable:
        warnings.append("双方失误均为 0，视为接口不可用值，不用于控制球权或胜负结论")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "facts": {
            "match_id": match.get("matchID"),
            "final_score_home_away": list(final),
            "displayed_period_score_home_away": list(shown_sum),
            "displayed_periods": shown,
            "regulation_complete": regulation_complete,
            "ignored_zero_overtime_placeholders": max(0, len(data.get("periods") or []) - len(shown)),
            "three_point_score_gap": expected_three_gap,
            "unreliable_fields": unreliable,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path)
    parser.add_argument("--article-md", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit_article(
        json.loads(args.json_path.read_text(encoding="utf-8")),
        args.article_md.read_text(encoding="utf-8"),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
