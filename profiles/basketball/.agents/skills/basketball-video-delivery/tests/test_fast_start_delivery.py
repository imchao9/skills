from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "fast_start_delivery.py"
SPEC = importlib.util.spec_from_file_location("fast_start_delivery", SCRIPT)
assert SPEC and SPEC.loader
fast_start = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fast_start
SPEC.loader.exec_module(fast_start)


class FastStartDeliveryTest(unittest.TestCase):
    def test_match_id_from_hash_url(self) -> None:
        ref = "https://www.xiaoqiumi.com/#/Match/MatchVideoList?matchID=400359919&sportType=1"
        self.assertEqual(fast_start.match_id_from_ref(ref), 400359919)

    def test_selects_single_long_replay_and_counts_only_event_clips(self) -> None:
        data = {
            "raw": {
                "details": {
                    "集锦": {
                        "modeData": [{
                            "videos": {
                                "playBacks": [
                                    {"title": "集锦", "time": "360", "url": "https://example/short.mp4"},
                                    {"title": "回放", "time": "4621", "url": "https://example/full.mp4"},
                                ],
                                "collectVideos": [
                                    {"title": "球员集锦", "subName": "个人集锦", "url": "https://example/player.mp4"},
                                    {"title": "2分命中", "subName": "2分命中", "url": "https://example/event.mp4"},
                                ],
                            }
                        }]
                    }
                }
            }
        }
        self.assertEqual([item["title"] for item in fast_start.select_replays(data)], ["回放"])
        self.assertEqual(fast_start.event_count(data), 1)

    def test_keeps_switch_phone_tail_and_deduplicates_near_identical_long_replays(self) -> None:
        data = {
            "raw": {"details": {"集锦": {"modeData": [{
                "videos": {"playBacks": [
                    {
                        "id": "highlight", "title": "全场精彩集锦", "subName": "全场集锦",
                        "time": "390", "url": "https://example/highlight.mp4",
                        "authorUserID": "main", "addDate": "2026-07-25 17:21:59",
                    },
                    {
                        "id": "pregame", "title": "比赛的精彩回放", "time": "280",
                        "url": "https://example/pregame.mp4", "authorUserID": "other",
                        "addDate": "2026-07-25 15:48:26",
                    },
                    {
                        "id": "long-a", "title": "比赛的精彩回放", "time": "4808",
                        "url": "https://example/long-a.mp4", "authorUserID": "main",
                        "addDate": "2026-07-25 17:23:29",
                    },
                    {
                        "id": "long-b", "title": "比赛的精彩回放", "time": "4930",
                        "url": "https://example/long-b.mp4", "authorUserID": "main",
                        "addDate": "2026-07-25 17:23:40",
                    },
                    {
                        "id": "tail", "title": "比赛的精彩回放", "time": "537",
                        "url": "https://example/tail.mp4", "authorUserID": "main",
                        "addDate": "2026-07-25 17:27:41",
                    },
                ]}
            }]}}}
        }
        self.assertEqual(
            [item["id"] for item in fast_start.select_replays(data)],
            ["long-b", "tail"],
        )

    def test_keeps_distinct_long_segments_created_far_apart(self) -> None:
        data = {
            "raw": {"details": {"集锦": {"modeData": [{
                "videos": {"playBacks": [
                    {
                        "id": "first", "title": "比赛回放", "time": "2400",
                        "url": "https://example/first.mp4", "authorUserID": "main",
                        "addDate": "2026-07-25 15:00:00",
                    },
                    {
                        "id": "second", "title": "比赛回放", "time": "2500",
                        "url": "https://example/second.mp4", "authorUserID": "main",
                        "addDate": "2026-07-25 16:00:00",
                    },
                ]}
            }]}}}
        }
        self.assertEqual(
            [item["id"] for item in fast_start.select_replays(data)],
            ["first", "second"],
        )

    def test_keeps_later_cross_device_short_continuation(self) -> None:
        data = {
            "raw": {"details": {"集锦": {"modeData": [{
                "videos": {"playBacks": [
                    {
                        "id": "main", "title": "比赛回放", "time": "4800",
                        "url": "https://example/main.mp4", "authorUserID": "phone-a",
                        "addDate": "2026-07-25 17:00:00",
                    },
                    {
                        "id": "tail", "title": "比赛回放", "time": "180",
                        "url": "https://example/tail.mp4", "authorUserID": "phone-b",
                        "addDate": "2026-07-25 17:10:00",
                    },
                ]}
            }]}}}
        }
        self.assertEqual(
            [item["id"] for item in fast_start.select_replays(data)],
            ["main", "tail"],
        )

    def test_rejects_short_media_as_full_replay(self) -> None:
        data = {
            "raw": {"details": {"集锦": {"modeData": [{
                "videos": {"playBacks": [{"title": "回放", "time": "360", "url": "https://example/short.mp4"}]}
            }]}}}
        }
        with self.assertRaisesRegex(ValueError, "under 20 minutes"):
            fast_start.select_replay(data)

    def test_no_replay_is_a_waiting_condition(self) -> None:
        data = {"raw": {"details": {"集锦": {"modeData": []}}}}
        with self.assertRaisesRegex(fast_start.ReplayUnavailableError, "no replay URL"):
            fast_start.select_replay(data)


if __name__ == "__main__":
    unittest.main()
