from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "assemble_replay_segments.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg tools are required")
class AssembleReplaySegmentsTest(unittest.TestCase):
    def make_segment(self, path: Path, *, size: str, color: str) -> None:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s={size}:d=1",
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", str(path),
            ],
            check=True,
        )

    def test_stream_copies_matching_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.mp4"
            second = root / "second.mp4"
            output = root / "assembled.mp4"
            report = root / "report.json"
            self.make_segment(first, size="320x180", color="red")
            self.make_segment(second, size="320x180", color="blue")
            subprocess.run(
                [
                    sys.executable, str(SCRIPT), str(first), str(second),
                    "--output", str(output), "--report", str(report),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["mode"], "stream-copy")
            self.assertEqual(payload["segment_count"], 2)
            self.assertTrue(output.is_file())

    def test_normalizes_incompatible_phone_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.mp4"
            second = root / "second.mp4"
            output = root / "assembled.mp4"
            report = root / "report.json"
            self.make_segment(first, size="320x180", color="red")
            self.make_segment(second, size="640x360", color="blue")
            subprocess.run(
                [
                    sys.executable, str(SCRIPT), str(first), str(second),
                    "--output", str(output), "--report", str(report),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["mode"], "normalized")
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
