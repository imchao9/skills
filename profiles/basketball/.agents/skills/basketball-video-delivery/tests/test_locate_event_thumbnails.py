from __future__ import annotations

import importlib.util
import http.client
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "locate_event_thumbnails.py"
SPEC = importlib.util.spec_from_file_location("locate_event_thumbnails", SCRIPT)
assert SPEC and SPEC.loader
locator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = locator
SPEC.loader.exec_module(locator)


class LocateEventThumbnailsTest(unittest.TestCase):
    def test_thumbnail_hash_retries_incomplete_read(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"complete-image"
        decoded = bytes(locator.SIGNATURE_W * locator.SIGNATURE_H)

        with (
            mock.patch.object(
                locator.urllib.request,
                "urlopen",
                side_effect=[http.client.IncompleteRead(b"partial", 3), response],
            ) as urlopen,
            mock.patch.object(locator.subprocess, "run", return_value=SimpleNamespace(
                returncode=0,
                stdout=decoded,
            )),
            mock.patch.object(locator.time, "sleep") as sleep,
        ):
            self.assertEqual(locator.thumbnail_hash("https://example.com/event.jpg"), 0)

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_write_hash_cache_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hashes.json"
            locator.write_hash_cache(path, {"event-1": 42})
            payload = locator.json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["signature"], [locator.SIGNATURE_W, locator.SIGNATURE_H])
        self.assertEqual(payload["hashes"], {"event-1": 42})

    def test_fetch_thumbnail_hashes_preserves_successes_when_one_fails(self) -> None:
        events = [
            locator.Event("good", "a", "t", "1", "p", "2分命中", "第一节", "10:00", "good"),
            locator.Event("bad", "b", "t", "1", "p", "2分命中", "第一节", "09:00", "bad"),
        ]

        def fetch(url: str) -> int:
            if url == "bad":
                raise RuntimeError("timed out")
            return 42

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "hashes.json"
            hashes: dict[str, int] = {}
            with mock.patch.object(locator, "thumbnail_hash", side_effect=fetch):
                with self.assertRaisesRegex(RuntimeError, "1 event thumbnail"):
                    locator.fetch_thumbnail_hashes(events, hashes, path, workers=2)
            payload = locator.json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(hashes, {"good": 42})
        self.assertEqual(payload["hashes"], {"good": 42})

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

    def test_li_tianchi_style_forced_alignment_is_blocked(self) -> None:
        reasons = locator.location_anomalies(
            aligned_seconds=131.5,
            raw_seconds=1050.5,
            aligned_hamming=1017,
            best_hamming=196,
            max_adjustment_seconds=30.0,
            max_hamming_regression=128,
        )
        self.assertEqual(
            reasons,
            ["large_alignment_adjustment", "aligned_match_much_worse_than_raw_best"],
        )

    def test_small_alignment_correction_is_accepted(self) -> None:
        self.assertEqual(locator.location_anomalies(
            aligned_seconds=131.5,
            raw_seconds=128.0,
            aligned_hamming=205,
            best_hamming=196,
            max_adjustment_seconds=30.0,
            max_hamming_regression=128,
        ), [])


if __name__ == "__main__":
    unittest.main()
