from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "pure_cut_editor.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools are required")
class PureCutEditorTest(unittest.TestCase):
    def test_default_render_uses_one_pass_without_encoded_segment_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=8",
                "-f", "lavfi", "-i", "sine=frequency=700:sample_rate=44100:duration=8",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            delete_csv = root / "delete.csv"
            with delete_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["start", "end", "reason"])
                writer.writeheader()
                writer.writerow({"start": "2", "end": "4", "reason": "pause"})
            output = root / "pure.mp4"
            report = root / "report.json"
            result = subprocess.run([
                sys.executable, str(SCRIPT), str(source), "--delete-csv", str(delete_csv),
                "--output", str(output), "--report", str(report), "--preset", "ultrafast", "--force",
            ], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["render"]["strategy"], "single_pass_filter")
            self.assertEqual(payload["render"]["temporary_segment_count"], 0)
            self.assertEqual(payload["render"]["intermediate_segment_bytes_peak"], 0)
            self.assertTrue(payload["render"]["atomic_output"])
            self.assertTrue(output.is_file())
            self.assertFalse(any(root.glob(".*.part.mp4")))
            duration = float(payload["output_probe"]["format"]["duration"])
            self.assertGreater(duration, 5.8)
            self.assertLess(duration, 6.2)
            decoded = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
                capture_output=True,
            )
            self.assertEqual(decoded.returncode, 0, decoded.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
