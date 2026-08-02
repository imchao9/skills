from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "xiaoqiumi_download.py"
SPEC = importlib.util.spec_from_file_location("xiaoqiumi_download", SCRIPT)
assert SPEC and SPEC.loader
download = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = download
SPEC.loader.exec_module(download)


class XiaoqiumiDownloadTest(unittest.TestCase):
    def test_split_ranges_cover_every_byte_once(self) -> None:
        ranges = download.split_ranges(10, 3)
        self.assertEqual(ranges, [(0, 3), (4, 7), (8, 9)])
        covered = [byte for start, end in ranges for byte in range(start, end + 1)]
        self.assertEqual(covered, list(range(10)))

    def test_more_connections_than_bytes_are_capped(self) -> None:
        self.assertEqual(download.split_ranges(2, 8), [(0, 0), (1, 1)])

    def test_health_policy_detects_stall_and_sustained_low_speed(self) -> None:
        stalled = {
            "elapsed_seconds": 180,
            "last_progress_seconds_ago": 95,
            "window_seconds": 180,
            "speed_mib_per_second": 4.0,
            "eta_seconds": 100,
        }
        self.assertEqual(
            download.health_failure_reason(
                stalled,
                stall_seconds=90,
                slow_window_seconds=300,
                min_speed_mib=1.0,
                health_grace_seconds=120,
                max_eta_seconds=3600,
                eta_grace_seconds=600,
            ),
            "no_progress",
        )
        slow = {
            "elapsed_seconds": 320,
            "last_progress_seconds_ago": 1,
            "window_seconds": 300,
            "speed_mib_per_second": 0.24,
            "eta_seconds": 7200,
        }
        self.assertEqual(
            download.health_failure_reason(
                slow,
                stall_seconds=90,
                slow_window_seconds=300,
                min_speed_mib=1.0,
                health_grace_seconds=120,
                max_eta_seconds=3600,
                eta_grace_seconds=600,
            ),
            "sustained_low_throughput",
        )

    def test_health_policy_allows_healthy_transfer(self) -> None:
        healthy = {
            "elapsed_seconds": 700,
            "last_progress_seconds_ago": 1,
            "window_seconds": 300,
            "speed_mib_per_second": 8.0,
            "eta_seconds": 120,
        }
        self.assertIsNone(download.health_failure_reason(
            healthy,
            stall_seconds=90,
            slow_window_seconds=300,
            min_speed_mib=1.0,
            health_grace_seconds=120,
            max_eta_seconds=3600,
            eta_grace_seconds=600,
        ))

    def test_retry_resumes_same_parallel_layout_then_succeeds(self) -> None:
        unhealthy = download.DownloadHealthError(
            "no_progress",
            {"downloaded_bytes": 123, "total_bytes": 1000, "chunks_preserved": True},
        )
        with tempfile.TemporaryDirectory() as temporary:
            health = Path(temporary) / "health.json"
            output = Path(temporary) / "replay.mp4"
            with (
                mock.patch.object(download, "download_parallel", side_effect=[
                    unhealthy,
                    {"status": "complete", "bytes": 1000},
                ]) as parallel,
                mock.patch.object(download.time, "sleep"),
            ):
                result = download.download_parallel_with_retries(
                    "https://example.test/replay.mp4?secret=hidden",
                    "test",
                    output,
                    output.with_name("replay.mp4.part"),
                    8,
                    health_report=health,
                    max_attempts=3,
                    retry_backoff_seconds=0,
                    heartbeat_seconds=10,
                    stall_seconds=90,
                    slow_window_seconds=300,
                    min_speed_mib=1.0,
                    health_grace_seconds=120,
                    max_eta_seconds=3600,
                    eta_grace_seconds=600,
                )
            self.assertEqual(result["attempts"], 2)
            self.assertEqual(parallel.call_count, 2)
            self.assertEqual(parallel.call_args_list[0].args[2:5], parallel.call_args_list[1].args[2:5])

    def test_retry_exhaustion_writes_needs_attention_without_url_query(self) -> None:
        failures = [
            download.DownloadHealthError(
                "sustained_low_throughput",
                {
                    "downloaded_bytes": 250,
                    "total_bytes": 1000,
                    "speed_mib_per_second": 0.24,
                    "eta_seconds": 7200,
                },
            )
            for _ in range(3)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            health = Path(temporary) / "health.json"
            output = Path(temporary) / "replay.mp4"
            with (
                mock.patch.object(download, "download_parallel", side_effect=failures),
                mock.patch.object(download.time, "sleep"),
            ):
                with self.assertRaises(download.DownloadNeedsAttentionError):
                    download.download_parallel_with_retries(
                        "https://example.test/replay.mp4?secret=hidden",
                        "test",
                        output,
                        output.with_name("replay.mp4.part"),
                        8,
                        health_report=health,
                        max_attempts=3,
                        retry_backoff_seconds=0,
                        heartbeat_seconds=10,
                        stall_seconds=90,
                        slow_window_seconds=300,
                        min_speed_mib=1.0,
                        health_grace_seconds=120,
                        max_eta_seconds=3600,
                        eta_grace_seconds=600,
                    )
            payload = json.loads(health.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "needs_attention")
            self.assertEqual(payload["attempt"], 3)
            self.assertTrue(payload["chunks_preserved"])
            self.assertNotIn("secret=hidden", health.read_text(encoding="utf-8"))

    def test_source_change_stops_without_reusing_incompatible_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            health = Path(temporary) / "health.json"
            output = Path(temporary) / "replay.mp4"
            with mock.patch.object(
                download,
                "download_parallel",
                side_effect=download.DownloadSourceChangedError("remote object changed"),
            ) as parallel:
                with self.assertRaises(download.DownloadNeedsAttentionError):
                    download.download_parallel_with_retries(
                        "https://example.test/replay.mp4?secret=hidden",
                        "test",
                        output,
                        output.with_name("replay.mp4.part"),
                        8,
                        health_report=health,
                        max_attempts=3,
                        retry_backoff_seconds=0,
                        heartbeat_seconds=10,
                        stall_seconds=90,
                        slow_window_seconds=300,
                        min_speed_mib=1.0,
                        health_grace_seconds=120,
                        max_eta_seconds=3600,
                        eta_grace_seconds=600,
                    )
            payload = json.loads(health.read_text(encoding="utf-8"))
            self.assertEqual(parallel.call_count, 1)
            self.assertFalse(payload["retryable"])
            self.assertEqual(payload["attempt"], 1)

    def test_live_monitor_stops_a_trickling_transfer_and_keeps_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "replay.mp4"
            health = root / "health.json"

            def trickle(
                url: str,
                user_agent: str,
                path: Path,
                start: int,
                end: int,
                control: download.TransferControl,
            ) -> int:
                partial = path.with_name(path.name + ".part")
                for index in range(end - start + 1):
                    if control.cancelled.is_set():
                        raise RuntimeError("cancelled")
                    with partial.open("ab") as handle:
                        handle.write(b"x")
                    time.sleep(0.01)
                return partial.stat().st_size

            remote = {
                "status": "probed",
                "source": "https://example.test/replay.mp4",
                "bytes": 1000,
                "etag": "same-object",
                "accept_ranges": "bytes",
            }
            with (
                mock.patch.object(download, "probe_remote", return_value=remote),
                mock.patch.object(download, "download_range", side_effect=trickle),
            ):
                with self.assertRaises(download.DownloadHealthError) as caught:
                    download.download_parallel(
                        "https://example.test/replay.mp4?secret=hidden",
                        "test",
                        output,
                        output.with_name("replay.mp4.part"),
                        2,
                        health_report=health,
                        attempt=1,
                        max_attempts=3,
                        heartbeat_seconds=0.02,
                        stall_seconds=1,
                        slow_window_seconds=0.08,
                        min_speed_mib=1.0,
                        health_grace_seconds=0,
                        max_eta_seconds=3600,
                        eta_grace_seconds=600,
                    )
            payload = json.loads(health.read_text(encoding="utf-8"))
            self.assertEqual(caught.exception.reason, "sustained_low_throughput")
            self.assertEqual(payload["status"], "unhealthy")
            self.assertTrue(payload["chunks_preserved"])
            self.assertTrue(output.with_name(output.name + ".chunks").is_dir())
            self.assertNotIn("secret=hidden", health.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
