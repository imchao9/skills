from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "basketball-player-clips" / "scripts" / "make_condensed_reel.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools are required")
class LowPeakGameMaterializationTest(unittest.TestCase):
    def test_game_builder_materializes_only_selected_missing_event_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=8",
                "-f", "lavfi", "-i", "sine=frequency=600:sample_rate=44100:duration=8",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            event = root / "events" / "selected.mp4"
            matches = root / "reports" / "matches.csv"
            matches.parent.mkdir()
            fields = [
                "team", "number", "player", "action", "period", "clock", "source",
                "new_start", "new_end", "new_duration", "avg_hamming", "output",
            ]
            with matches.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "team": "A", "number": "1", "player": "甲", "action": "3分命中",
                    "period": "第一节", "clock": "10:00", "source": str(source),
                    "new_start": "00:00:02.000", "new_end": "00:00:06.000",
                    "new_duration": "4", "avg_hamming": "0", "output": str(event),
                })
            output = root / "game.mp4"
            result = subprocess.run([
                sys.executable, str(SCRIPT), "--matches-csv", str(matches), "--output", str(output),
                "--min-seconds", "3", "--target-seconds", "4", "--max-seconds", "5",
            ], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(event.is_file())
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
