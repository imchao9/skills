from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "render_player_reels_from_matches.py"
SPEC = importlib.util.spec_from_file_location("render_player_reels_from_matches", SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renderer
SPEC.loader.exec_module(renderer)


class PlayerEventAuditTest(unittest.TestCase):
    def test_official_event_counts_must_match_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            match_json = Path(temporary) / "match.json"
            match_json.write_text(json.dumps({
                "players": {"home": [{
                    "playerNo": "30", "playerName": "李天驰", "twoShotNum": 2,
                    "threeShotNum": 1, "assists": 1, "steals": 0, "blocks": 0,
                }]},
            }), encoding="utf-8")
            rows = [
                {"number": "30", "player": "李天驰", "action": "2分命中"},
                {"number": "30", "player": "李天驰", "action": "3分命中"},
                {"number": "30", "player": "李天驰", "action": "助攻"},
            ]
            audit = renderer.build_event_stat_audit(rows, match_json)

        self.assertEqual(audit["status"], "needs_attention")
        self.assertIn("official=2, events=1", "\n".join(audit["errors"]))

    def test_unknown_player_is_never_silently_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            match_json = Path(temporary) / "match.json"
            match_json.write_text(json.dumps({"players": {"home": []}}), encoding="utf-8")
            audit = renderer.build_event_stat_audit(
                [{"number": "30", "player": "李天驰", "action": "2分命中"}], match_json
            )

        self.assertEqual(audit["status"], "needs_attention")
        self.assertTrue(any("unknown player" in error for error in audit["errors"]))


if __name__ == "__main__":
    unittest.main()
