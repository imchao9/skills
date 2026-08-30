from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_xiaoqiumi_commentary.py"
SPEC = importlib.util.spec_from_file_location("audit_xiaoqiumi_commentary", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def fixture() -> dict:
    return {
        "match": {
            "matchID": 1,
            "homeTeam": {"name": "主队", "score": 79},
            "awayTeam": {"name": "客队", "score": 90},
        },
        "periods": [
            {"label": "Q1", "home": 14, "away": 12},
            {"label": "Q2", "home": 28, "away": 30},
            {"label": "Q3", "home": 16, "away": 21},
            {"label": "Q4", "home": 21, "away": 27},
            {"label": "OT1", "home": 0, "away": 0},
        ],
        "teamStats": {
            "home": {"threeShotNum": 1, "error": 0},
            "away": {"threeShotNum": 8, "error": 0},
        },
    }


class CommentaryAuditTest(unittest.TestCase):
    def test_zero_overtime_placeholder_is_not_displayed(self) -> None:
        self.assertEqual(len(audit.display_periods(fixture())), 4)

    def test_article_rejects_zero_overtime_claim(self) -> None:
        report = audit.audit_article(fixture(), "主队与客队终场，另有 OT1 0:0。")
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("占位" in error for error in report["errors"]))

    def test_article_rejects_wrong_three_point_score_gap(self) -> None:
        report = audit.audit_article(fixture(), "主队与客队，双方通过三分球得到的分数相差18分。")
        self.assertEqual(report["facts"]["three_point_score_gap"], 21)
        self.assertTrue(any("21" in error for error in report["errors"]))

    def test_zero_turnovers_are_marked_unreliable(self) -> None:
        report = audit.audit_article(fixture(), "主队与客队完成比赛。")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["facts"]["unreliable_fields"], ["error"])


if __name__ == "__main__":
    unittest.main()
