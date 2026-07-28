from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_final_visual_audit.py"
SPEC = importlib.util.spec_from_file_location("build_final_visual_audit", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class FinalVisualAuditTest(unittest.TestCase):
    def test_maps_source_delete_ranges_to_output_seams(self) -> None:
        seams = audit.output_seams([
            (10.0, 20.0, "timeout"),
            (40.0, 45.0, "dead air"),
        ])
        self.assertEqual(seams[0]["output_time"], 10.0)
        self.assertEqual(seams[1]["output_time"], 30.0)

    def test_even_sampling_keeps_first_and_last(self) -> None:
        items = [{"index": index} for index in range(10)]
        sampled = audit.evenly_sample(items, 4)
        self.assertEqual(sampled[0]["index"], 0)
        self.assertEqual(sampled[-1]["index"], 9)
        self.assertEqual(len(sampled), 4)

    def test_contract_is_current_only_with_matching_fingerprints_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            html = root / "audit.html"
            png = root / "audit.png"
            html.write_text("ok", encoding="utf-8")
            png.write_bytes(b"png")
            fingerprints = {"pure": {"bytes": 1}}
            contract = {
                "fingerprints": fingerprints,
                "evidence": {"html": str(html), "png": str(png)},
            }
            self.assertTrue(audit.current_contract(contract, fingerprints))
            self.assertFalse(audit.current_contract(contract, {"pure": {"bytes": 2}}))

    @unittest.skipUnless(
        all(shutil.which(command) for command in ("ffmpeg", "ffprobe")),
        "visual audit integration tools are unavailable",
    )
    def test_builds_risk_based_visual_evidence_with_real_media(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pure = root / "pure.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc=size=320x180:rate=5",
                    "-t", "8", "-pix_fmt", "yuv420p", str(pure),
                ],
                check=True,
            )
            game = root / "game.mp4"
            shutil.copy2(pure, game)
            poster = root / "poster.png"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=navy:s=1080x1440",
                    "-frames:v", "1", str(poster),
                ],
                check=True,
            )
            delete_csv = root / "delete.csv"
            delete_csv.write_text("start,end,reason\n1,2,timeout\n", encoding="utf-8")
            main_review = root / "ai-review.json"
            main_review.write_text(
                json.dumps({
                    "status": "approved",
                    "game_highlight": {"draft_video": str(game)},
                    "commentary": {"png": str(poster)},
                }),
                encoding="utf-8",
            )
            contract = root / "final-review.json"
            result = subprocess.run(
                [
                    sys.executable, str(SCRIPT),
                    "--pure", str(pure), "--delete-csv", str(delete_csv),
                    "--game", str(game), "--poster", str(poster),
                    "--main-review", str(main_review),
                    "--output-dir", str(root / "audit"), "--contract", str(contract),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(contract.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "needs_ai")
            self.assertTrue(payload["checks"]["pure_seams"]["required"])
            self.assertFalse(payload["checks"]["game_visual"]["required"])
            self.assertFalse(payload["checks"]["poster_visual"]["required"])
            self.assertTrue(Path(payload["evidence"]["html"]).is_file())
            self.assertTrue(Path(payload["evidence"]["png"]).is_file())
            self.assertTrue(Path(payload["evidence"]["seam_video"]).is_file())


if __name__ == "__main__":
    unittest.main()
