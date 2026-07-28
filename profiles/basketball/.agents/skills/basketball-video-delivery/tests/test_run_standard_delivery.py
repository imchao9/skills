from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
