from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_event_direct_tracer.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools are required")
class EventDirectTracerTest(unittest.TestCase):
    def test_cli_cuts_one_located_event_without_platform_event_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=20",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=20",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(source),
                ],
                check=True,
            )
            match_json = root / "match.json"
            match_json.write_text(json.dumps({
                "players": {"home": [{
                    "playerNo": "23", "playerName": "小明", "twoShotNum": 1,
                    "threeShotNum": 0, "assists": 0, "steals": 0, "blocks": 0,
                }]},
            }), encoding="utf-8")
            locations = root / "locations.csv"
            fields = [
                "event_id", "title", "team", "number", "player", "action",
                "period", "clock", "source_seconds",
            ]
            with locations.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "event_id": "event-1",
                    "title": "测试队 23号 小明 2分命中 第一节 09:41",
                    "team": "测试队",
                    "number": "23",
                    "player": "小明",
                    "action": "2分命中",
                    "period": "第一节",
                    "clock": "09:41",
                    "source_seconds": "17.0",
                })
            output = root / "output"
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--match-json", str(match_json),
                    "--source", str(source),
                    "--event-id", "event-1",
                    "--locations-csv", str(locations),
                    "--output-dir", str(output),
                    "--preset", "ultrafast",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((output / "event-direct-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["mode"], "event_direct")
            self.assertEqual(report["event"]["event_id"], "event-1")
            self.assertEqual(report["event"]["player"], "小明")
            self.assertEqual(report["platform_event_download_count"], 0)
            self.assertTrue(all(report["mechanical_checks"].values()))
            self.assertTrue(Path(report["clip"]["path"]).is_file())
            self.assertTrue(Path(report["player_reel"]["path"]).is_file())
            self.assertTrue(Path(report["audit_contact_sheet"]).is_file())
            self.assertGreater(report["clip"]["duration_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
