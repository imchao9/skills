from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[2]
    / "xiaoqiumi-match-review"
    / "scripts"
    / "generate_xiaoqiumi_commentary.py"
)
SPEC = importlib.util.spec_from_file_location("generate_xiaoqiumi_commentary", SCRIPT)
assert SPEC and SPEC.loader
commentary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = commentary
SPEC.loader.exec_module(commentary)


class CommentaryDraftTest(unittest.TestCase):
    def test_team_line_uses_attempts_before_makes(self) -> None:
        line = commentary.team_line(
            "测试队",
            {
                "totalBoards": 30,
                "assists": 12,
                "shots": 78,
                "shootNum": 19,
                "threeShots": 30,
                "threeShotNum": 7,
                "freeThrows": 10,
                "freeThrowNum": 6,
                "steals": 5,
                "error": 8,
            },
        )
        self.assertIn("投篮78投19中", line)
        self.assertIn("三分30投7中", line)
        self.assertIn("罚球10罚6中", line)
        self.assertNotIn("19/78", line)


if __name__ == "__main__":
    unittest.main()
