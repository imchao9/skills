from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "locate_event_thumbnails.py"
SPEC = importlib.util.spec_from_file_location("locate_event_thumbnails", SCRIPT)
assert SPEC and SPEC.loader
locator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = locator
SPEC.loader.exec_module(locator)


class LocateEventThumbnailsTest(unittest.TestCase):
    def test_best_match_and_confidence_gap(self) -> None:
        index, best, second = locator.best_thumbnail_match([0b0000, 0b1111, 0b0011], 0b1111)
        self.assertEqual(index, 1)
        self.assertEqual(best, 0)
        self.assertEqual(second, 0)

    def test_monotonic_alignment_rejects_backwards_best_match(self) -> None:
        events = [
            locator.Event("1", "a", "t", "1", "p", "2分命中", "第一节", "10:00", "u"),
            locator.Event("2", "b", "t", "1", "p", "2分命中", "第一节", "09:00", "u"),
        ]
        candidates = [
            [(200, 0), (20, 3)],
            [(100, 0), (150, 2)],
        ]
        self.assertEqual(locator.align_monotonic(events, candidates), [(20, 3), (150, 2)])

    def test_dense_alignment_uses_game_clock_progress(self) -> None:
        events = [
            locator.Event("1", "a", "t", "1", "p", "2分命中", "第一节", "10:00", "u"),
            locator.Event("2", "b", "t", "1", "p", "2分命中", "第一节", "09:00", "u"),
        ]
        source = [0] * 200
        source[20] = 0b1111
        source[150] = 0b1111
        chosen = locator.align_monotonic_dense(events, source, [0b1111, 0b1111])
        self.assertEqual([index for index, _ in chosen], [20, 150])

    def test_period_anchor_blocks_an_earlier_false_match(self) -> None:
        event = locator.Event("1", "a", "t", "1", "p", "2分命中", "第二节", "11:50", "u")
        source = [0] * 400
        source[20] = 0b1111
        source[220] = 0b1111
        chosen = locator.align_monotonic_dense(
            [event],
            source,
            [0b1111],
            period_starts={2: 100},
        )
        self.assertEqual(chosen[0][0], 220)


if __name__ == "__main__":
    unittest.main()
