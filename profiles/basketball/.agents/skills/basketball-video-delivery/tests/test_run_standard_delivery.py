from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_standard_delivery.py"
SPEC = importlib.util.spec_from_file_location("run_standard_delivery", SCRIPT)
assert SPEC and SPEC.loader
delivery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = delivery
SPEC.loader.exec_module(delivery)


class RunStandardDeliveryTest(unittest.TestCase):
    def test_match_id_from_h5_url(self) -> None:
        url = "https://example/#/MatchDetails?competitionID=1&matchid=400359920"
        self.assertEqual(delivery.match_id_from_ref(url), 400359920)

    def test_review_requires_every_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "artifact"
            artifact.write_text("ok", encoding="utf-8")
            review = {
                "status": "approved",
                "pure_cut": {
                    "approved": True,
                    "visual_approved": True,
                    "reviewed_delete_csv": str(artifact),
                },
                "player_clips": {
                    "approved": True,
                    "exceptions_reviewed": True,
                    "matches_csv": str(artifact),
                },
                "game_highlight": {
                    "approved": True,
                    "visual_approved": True,
                    "selection_csv": str(artifact),
                },
                "commentary": {
                    "approved": True,
                    "facts_audited": True,
                    "visual_approved": False,
                    "article_md": str(artifact),
                    "photo": str(artifact),
                },
            }
            with self.assertRaisesRegex(delivery.WaitingForReview, "visual_approved"):
                delivery.require_approved(review)

    def test_review_passes_only_with_all_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delete_csv = root / "delete.csv"
            delete_csv.write_text("start,end,reason\n0,30,warmup\n", encoding="utf-8")
            matches_csv = root / "matches.csv"
            matches_csv.write_text("team,player\nA,甲\n", encoding="utf-8")
            selection_csv = root / "selection.csv"
            selection_csv.write_text(
                "cluster,team,duration\n1,A,250\n2,B,250\n",
                encoding="utf-8",
            )
            article = root / "article.md"
            article.write_text(
                "# 球评\n"
                + "\n".join(f"## 章节{i}\n全场78投19中，双方保持高强度对抗。" for i in range(1, 5))
                + "比赛内容扎实。" * 100,
                encoding="utf-8",
            )
            photo = root / "photo.jpg"
            photo.write_bytes(b"image")
            pure_proxy = root / "pure.mp4"
            pure_proxy.write_bytes(b"video")
            pure_contact = root / "pure.jpg"
            pure_contact.write_bytes(b"sheet")
            game_draft = root / "game.mp4"
            game_draft.write_bytes(b"video")
            game_contact = root / "game.jpg"
            game_contact.write_bytes(b"sheet")
            html = root / "poster.html"
            html.write_text("<html></html>", encoding="utf-8")
            png = root / "poster.png"
            png.write_bytes(b"png")
            review = {
                "status": "approved",
                "pure_cut": {
                    "approved": True,
                    "visual_approved": True,
                    "reviewed_delete_csv": str(delete_csv),
                    "proxy_video": str(pure_proxy),
                    "contact_sheet": str(pure_contact),
                },
                "player_clips": {
                    "approved": True,
                    "exceptions_reviewed": True,
                    "matches_csv": str(matches_csv),
                },
                "game_highlight": {
                    "approved": True,
                    "visual_approved": True,
                    "selection_csv": str(selection_csv),
                    "draft_video": str(game_draft),
                    "contact_sheet": str(game_contact),
                },
                "commentary": {
                    "approved": True,
                    "facts_audited": True,
                    "visual_approved": True,
                    "article_md": str(article),
                    "photo": str(photo),
                    "html": str(html),
                    "png": str(png),
                },
            }
            delivery.require_approved(review)

    def test_review_rejects_made_before_attempts_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            delete_csv = root / "delete.csv"
            delete_csv.write_text("start,end,reason\n0,30,warmup\n", encoding="utf-8")
            matches_csv = root / "matches.csv"
            matches_csv.write_text("team,player\nA,甲\n", encoding="utf-8")
            selection_csv = root / "selection.csv"
            selection_csv.write_text(
                "cluster,team,duration\n1,A,250\n2,B,250\n",
                encoding="utf-8",
            )
            article = root / "article.md"
            article.write_text(
                "# 球评\n"
                + "\n".join(f"## 章节{i}\n全场19中78，双方保持高强度对抗。" for i in range(1, 5))
                + "比赛内容扎实。" * 100,
                encoding="utf-8",
            )
            photo = root / "photo.jpg"
            photo.write_bytes(b"image")
            pure_proxy = root / "pure.mp4"
            pure_proxy.write_bytes(b"video")
            pure_contact = root / "pure.jpg"
            pure_contact.write_bytes(b"sheet")
            game_draft = root / "game.mp4"
            game_draft.write_bytes(b"video")
            game_contact = root / "game.jpg"
            game_contact.write_bytes(b"sheet")
            html = root / "poster.html"
            html.write_text("<html></html>", encoding="utf-8")
            png = root / "poster.png"
            png.write_bytes(b"png")
            review = {
                "status": "approved",
                "pure_cut": {
                    "approved": True,
                    "visual_approved": True,
                    "reviewed_delete_csv": str(delete_csv),
                    "proxy_video": str(pure_proxy),
                    "contact_sheet": str(pure_contact),
                },
                "player_clips": {
                    "approved": True,
                    "exceptions_reviewed": True,
                    "matches_csv": str(matches_csv),
                },
                "game_highlight": {
                    "approved": True,
                    "visual_approved": True,
                    "selection_csv": str(selection_csv),
                    "draft_video": str(game_draft),
                    "contact_sheet": str(game_contact),
                },
                "commentary": {
                    "approved": True,
                    "facts_audited": True,
                    "visual_approved": True,
                    "article_md": str(article),
                    "photo": str(photo),
                    "html": str(html),
                    "png": str(png),
                },
            }
            with self.assertRaisesRegex(delivery.WaitingForReview, "19中78"):
                delivery.require_approved(review)

    def test_final_visual_review_requires_all_risk_checks(self) -> None:
        contract = {
            "status": "approved",
            "checks": {
                "pure_seams": {"required": True, "approved": True},
                "game_visual": {"required": False, "approved": True},
                "poster_visual": {"required": True, "approved": False},
            },
        }
        self.assertFalse(delivery.final_visual_review_is_approved(contract))
        contract["checks"]["poster_visual"]["approved"] = True
        self.assertTrue(delivery.final_visual_review_is_approved(contract))

    def test_auto_approved_final_visual_review_passes(self) -> None:
        self.assertTrue(delivery.final_visual_review_is_approved({"status": "auto_approved"}))

    def test_manifest_cache_invalidates_when_input_is_newer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact.mp4"
            artifact.write_bytes(b"old")
            manifest = root / "manifest.json"
            manifest.write_text(
                '{"status":"complete","full_decode":{"status":"complete"}}',
                encoding="utf-8",
            )
            self.assertTrue(delivery.manifest_is_current(manifest, [artifact]))
            artifact.write_bytes(b"new")
            self.assertFalse(delivery.manifest_is_current(manifest, [artifact]))

    def test_standard_run_propagates_download_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            run_dir = workspace / "runs" / "400377608"
            fast_report = run_dir / "output" / "delivery" / "fast-start.json"

            def failed_fast_start(name: str, command: list[str], log: Path) -> dict:
                self.assertEqual(name, "fast_start")
                fast_report.parent.mkdir(parents=True, exist_ok=True)
                fast_report.write_text(json.dumps({
                    "status": "needs_attention",
                    "reason": "sustained_low_throughput",
                    "download_report": "/tmp/download.json",
                    "health_report": "/tmp/health.json",
                    "download": {
                        "downloaded_bytes": 123,
                        "total_bytes": 1000,
                        "progress_percent": 12.3,
                        "speed_mib_per_second": 0.24,
                        "attempt": 3,
                        "max_attempts": 3,
                        "chunks_preserved": True,
                    },
                    "action_required": "inspect network or CDN, then resume",
                }), encoding="utf-8")
                raise RuntimeError("fast_start failed with exit 3")

            argv = [
                "run_standard_delivery.py",
                "400377608",
                "--workspace",
                str(workspace),
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(delivery, "ensure_tools"),
                mock.patch.object(delivery, "run", side_effect=failed_fast_start),
            ):
                self.assertEqual(delivery.main(), 4)

            standard_report = json.loads(
                (run_dir / "output" / "delivery" / "standard-run.json").read_text(encoding="utf-8")
            )
            self.assertEqual(standard_report["status"], "needs_attention")
            self.assertEqual(standard_report["phase"], "replay_download")
            self.assertTrue(standard_report["chunks_preserved"])
            self.assertFalse(standard_report["auto_shutdown_allowed"])
            self.assertEqual(standard_report["attempt"], 3)
            self.assertEqual(standard_report["max_attempts"], 3)
            self.assertIn("run_standard_delivery.py", standard_report["resume_command"])


if __name__ == "__main__":
    unittest.main()
