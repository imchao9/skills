from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "locate_events_from_scoreboard_ocr.py"
SPEC = importlib.util.spec_from_file_location("locate_events_from_scoreboard_ocr", SCRIPT)
assert SPEC and SPEC.loader
locator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = locator
SPEC.loader.exec_module(locator)


class ScoreboardLocatorTest(unittest.TestCase):
    def test_uses_first_frame_in_clock_hold_near_predictor(self) -> None:
        observations = [
            locator.Observation(100, 600, "10:00"),
            locator.Observation(101, 600, "10:00"),
            locator.Observation(200, 600, "10:00"),
        ]
        source, _, clock = locator.choose_event_time(observations, 600, 105, 0, 300)
        self.assertEqual(source, 100)
        self.assertEqual(clock, 600)

    def test_interpolates_from_neighboring_clock(self) -> None:
        observations = [locator.Observation(100, 601, "10:01")]
        source, _, clock = locator.choose_event_time(observations, 600, 100, 0, 300)
        self.assertEqual(source, 101)
        self.assertEqual(clock, 601)

    def test_discards_overlay_clock_that_increases_within_period(self) -> None:
        observations = [
            locator.Observation(100, 108, "1:48"),
            locator.Observation(102, 106, "1:46"),
            locator.Observation(163, 63, "1:03"),
            locator.Observation(265, 120, "stat overlay 2:00"),
            locator.Observation(291, 720, "next period 12:00"),
        ]
        filtered = locator.monotonic_period_observations(observations, 0, 300)
        self.assertEqual(
            [(item.source_seconds, item.clock_seconds) for item in filtered],
            [(100, 108), (102, 106), (163, 63)],
        )


if __name__ == "__main__":
    unittest.main()
