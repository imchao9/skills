from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "fast_start_delivery.py"
SPEC = importlib.util.spec_from_file_location("fast_start_delivery", SCRIPT)
assert SPEC and SPEC.loader
fast_start = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fast_start
SPEC.loader.exec_module(fast_start)


class FastStartDeliveryTest(unittest.TestCase):
    def test_default_cli_path_builds_players_directly_without_downloading_event_mp4s(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            match_id = 400000001
            run_dir = root / "runs" / str(match_id)
            source = run_dir / "source" / "比赛回放.mp4"
            source.parent.mkdir(parents=True)
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=20",
                    "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=44100:duration=20",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(source),
                ],
                check=True,
            )
            thumbnail = root / "event.jpg"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", "10", "-i", str(source), "-frames:v", "1", str(thumbnail),
                ],
                check=True,
            )
            fixture = root / "fixture-match.json"
            fixture.write_text(json.dumps({
                "players": {"home": [{
                    "playerNo": "23", "playerName": "小明", "twoShotNum": 1,
                    "threeShotNum": 0, "assists": 0, "steals": 0, "blocks": 0,
                }]},
                "raw": {"details": {"集锦": {"modeData": [{"videos": {
                    "playBacks": [{
                        "id": "replay-1", "title": "比赛回放", "time": "1200",
                        "url": "https://example.invalid/replay.mp4", "authorUserID": "phone",
                        "addDate": "2026-08-02 12:00:00",
                    }],
                    "collectVideos": [{
                        "id": "event-1", "title": "测试队 23号 小明 2分命中 第一节 11:47",
                        "teamName": "测试队", "shirtNo": "23", "reletedPlayerName": "小明",
                        "subName": "2分命中", "urlThumbnail": thumbnail.as_uri(),
                        "url": "https://example.invalid/event.mp4",
                    }],
                }}]}}},
            }, ensure_ascii=False), encoding="utf-8")
            fake_fetch = root / "fake_fetch.py"
            fake_fetch.write_text(
                "import os, shutil, sys\n"
                "from pathlib import Path\n"
                "shutil.copyfile(os.environ['FAST_START_FIXTURE_MATCH'], sys.argv[sys.argv.index('--out') + 1])\n"
                "Path(sys.argv[sys.argv.index('--facts-md') + 1]).write_text('fixture\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            argv = [
                str(SCRIPT), str(match_id), "--workspace", str(root),
                "--skip-pure-preflight",
            ]
            with (
                mock.patch.object(fast_start, "FETCH_MATCH", fake_fetch),
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(os.environ, {"FAST_START_FIXTURE_MATCH": str(fixture)}),
            ):
                self.assertEqual(fast_start.main(), 0)

            report = json.loads(
                (run_dir / "output" / "delivery" / "fast-start.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["status"], "ready_for_ai")
            self.assertEqual(report["event_source"], "direct")
            self.assertEqual(report["event_metadata_count"], 1)
            self.assertEqual(report["event_download_count"], 0)
            disk_stage = next(stage for stage in report["stages"] if stage["name"] == "disk_preflight")
            self.assertEqual(disk_stage["status"], "complete")
            self.assertGreater(disk_stage["required_free_bytes"], 0)
            self.assertFalse((run_dir / "source" / "labeled-events").exists())
            self.assertTrue(
                (run_dir / "output" / "player-clips-front15" / "个人精彩集锦" / "小明-个人精彩集锦_数据标注版.mp4").is_file()
            )
            event_dir = run_dir / "output" / "player-clips-front15" / "个人精彩片段"
            self.assertFalse(any(event_dir.glob("*.mp4")))
            players_csv = (
                run_dir / "output" / "player-clips-front15" / "reports" / "players.csv"
            ).read_text(encoding="utf-8")
            self.assertIn("per_player_temporary", players_csv)
            self.assertIn("data_labeled", players_csv)

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

    def test_acquire_replays_surfaces_download_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "runs" / "400377608"
            source = run_dir / "source" / "match.mp4"

            def failed_download(
                name: str,
                command: list[str],
                log: Path,
                stdin_text: str | None = None,
            ) -> dict:
                report = Path(command[command.index("--report") + 1])
                health = Path(command[command.index("--health-report") + 1])
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps({
                    "status": "needs_attention",
                    "reason": "no_progress",
                    "health_report": str(health),
                    "downloaded_bytes": 256,
                    "total_bytes": 1024,
                    "attempts": 3,
                    "chunks_preserved": True,
                }), encoding="utf-8")
                raise RuntimeError("download failed with exit 3")

            with (
                mock.patch.object(fast_start, "probe", return_value=None),
                mock.patch.object(fast_start, "run_logged", side_effect=failed_download),
            ):
                with self.assertRaises(fast_start.ReplayDownloadNeedsAttention) as caught:
                    fast_start.acquire_replays(
                        [{"id": "segment", "url": "https://example/replay.mp4?secret=1"}],
                        source,
                        run_dir,
                        8,
                    )

            self.assertEqual(caught.exception.payload["status"], "needs_attention")
            self.assertTrue(caught.exception.payload["chunks_preserved"])
            self.assertEqual(caught.exception.payload["attempts"], 3)


if __name__ == "__main__":
    unittest.main()
