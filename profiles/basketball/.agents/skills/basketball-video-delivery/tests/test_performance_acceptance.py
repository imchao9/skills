from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_performance_acceptance.py"


class PerformanceAcceptanceTest(unittest.TestCase):
    def test_cli_requires_and_recognizes_all_three_match_archetypes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixtures = [
                ("1", 30, 1, 2 * 1024 ** 3),
                ("2", 40, 1, 5 * 1024 ** 3),
                ("3", 2, 3, 3 * 1024 ** 3),
            ]
            run_dirs = []
            for match_id, events, segments, size in fixtures:
                run_dir = root / match_id
                delivery = run_dir / "output" / "delivery"
                delivery.mkdir(parents=True)
                (delivery / "fast-start.json").write_text(json.dumps({
                    "status": "ready_for_ai", "matchID": match_id,
                    "event_source": "direct", "event_metadata_count": events,
                    "event_download_count": 0, "replay_segment_count": segments,
                    "source_bytes": size, "stages": [],
                }), encoding="utf-8")
                run_dirs.append(run_dir)
            report = root / "performance.json"
            command = [sys.executable, str(SCRIPT)]
            for run_dir in run_dirs:
                command.extend(["--run-dir", str(run_dir)])
            command.extend(["--out", str(report)])
            result = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(len(payload["represented_archetypes"]), 3)
            self.assertTrue(all(run["checks"]["no_platform_event_downloads"] for run in payload["runs"]))


if __name__ == "__main__":
    unittest.main()
