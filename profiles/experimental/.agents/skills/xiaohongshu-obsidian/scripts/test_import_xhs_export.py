#!/usr/bin/env python3
"""Offline regression tests for import_xhs_export.py."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from import_xhs_export import import_export


class ImportXhsExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "Vault"
        self.media = self.root / "export"
        self.vault.mkdir()
        (self.media / "media").mkdir(parents=True)
        (self.media / "media" / "cover.jpg").write_bytes(b"fake-image")
        self.export = self.media / "export.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_export(self, content: str = "第一版正文") -> None:
        payload = {
            "items": [
                {
                    "note_id": "note-123",
                    "url": (
                        "https://www.xiaohongshu.com/explore/note-123"
                        "?xsec_token=secret&source=web"
                    ),
                    "title": "示例 / 笔记",
                    "content": content,
                    "author": {"name": "作者", "id": "u-1", "cookie": "do-not-copy"},
                    "liked": True,
                    "likes": "99",
                    "collects": "8",
                    "comments_count": "7",
                    "views": "1234",
                    "collections": ["收藏夹 A"],
                    "tags": ["标签一"],
                    "media": [
                        {"type": "image", "path": "media/cover.jpg"},
                        {
                            "type": "video",
                            "url": "https://user:password@media.example/video.mp4?signature=secret&v=1",
                        },
                    ],
                    "comments": [
                        {
                            "author": "评论者",
                            "content": "评论",
                            "replies": [{"author": "作者", "content": "回复"}],
                        }
                    ],
                    "access_token": "must-never-be-imported",
                },
                {
                    "note_id": "note-123",
                    "title": "示例 / 笔记",
                    "content": content,
                },
            ]
        }
        self.export.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_incremental_import_preserves_manual_content_and_secrets(self) -> None:
        self.write_export()
        first = import_export(self.export, self.vault, "Sources/XHS")
        self.assertEqual(first.created, 1)
        self.assertEqual(first.duplicates, 1)

        notes = list((self.vault / "Sources" / "XHS").glob("*.md"))
        self.assertEqual(len(notes), 1)
        note = notes[0]
        text = note.read_text(encoding="utf-8")
        self.assertIn("第一版正文", text)
        self.assertIn("评论者", text)
        self.assertIn("回复", text)
        self.assertIn("来源类型：liked", text)
        self.assertIn("点赞 99 · 收藏 8 · 评论 7 · 浏览 1234", text)
        self.assertIn("source=web", text)
        self.assertIn("v=1", text)
        self.assertNotIn("xsec_token", text)
        self.assertNotIn("signature", text)
        self.assertNotIn("user:password", text)
        self.assertNotIn("must-never-be-imported", text)
        self.assertTrue(
            (self.vault / "Sources" / "XHS" / "_media" / "note-123" / "01-cover.jpg").is_file()
        )

        text = text.replace(
            "## 我的整理\n\n在这里继续补充摘要、双链、事实核验和行动项。",
            "## 我的整理\n\n这是人工内容。\n\nmanual_field: keep",
        )
        note.write_text(text, encoding="utf-8")
        self.write_export("第二版正文")
        second = import_export(self.export, self.vault, "Sources/XHS")
        self.assertEqual(second.updated, 1)
        updated = note.read_text(encoding="utf-8")
        self.assertIn("第二版正文", updated)
        self.assertNotIn("第一版正文", updated)
        self.assertIn("这是人工内容", updated)
        self.assertIn("manual_field: keep", updated)

        third = import_export(self.export, self.vault, "Sources/XHS")
        self.assertEqual(third.unchanged, 1)

    def test_dry_run_writes_nothing(self) -> None:
        self.write_export()
        result = import_export(self.export, self.vault, "Sources/XHS", dry_run=True)
        self.assertEqual(result.created, 1)
        self.assertFalse((self.vault / "Sources").exists())

    def test_folder_cannot_escape_vault(self) -> None:
        self.write_export()
        with self.assertRaisesRegex(ValueError, "inside the vault"):
            import_export(self.export, self.vault, "../outside")

    def test_media_path_cannot_escape_export_root(self) -> None:
        outside = self.root / "private.jpg"
        outside.write_bytes(b"must-not-copy")
        payload = {
            "items": [
                {
                    "note_id": "unsafe-media",
                    "title": "不安全媒体路径",
                    "media": [{"path": "../private.jpg"}],
                }
            ]
        }
        self.export.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = import_export(self.export, self.vault, "Sources/XHS")
        self.assertEqual(result.media_copied, 0)
        self.assertEqual(result.missing_media, ["../private.jpg"])
        copied = list((self.vault / "Sources" / "XHS").rglob("*.jpg"))
        self.assertEqual(copied, [])

    def test_reuses_media_already_stored_inside_vault(self) -> None:
        media_path = (
            self.vault
            / "Sources"
            / "XHS"
            / "_media"
            / "vault-media"
            / "01-cover.jpg"
        )
        media_path.parent.mkdir(parents=True)
        media_path.write_bytes(b"vault-image")
        payload = {
            "items": [
                {
                    "note_id": "vault-media",
                    "title": "Vault 媒体",
                    "media": [
                        {
                            "type": "image",
                            "vault_path": media_path.relative_to(self.vault).as_posix(),
                        }
                    ],
                }
            ]
        }
        self.export.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        result = import_export(self.export, self.vault, "Sources/XHS")

        self.assertEqual(result.media_unchanged, 1)
        self.assertEqual(result.media_copied, 0)
        note = next((self.vault / "Sources" / "XHS").glob("*.md"))
        self.assertIn(
            "![[Sources/XHS/_media/vault-media/01-cover.jpg]]",
            note.read_text(encoding="utf-8"),
        )

    def test_vault_media_path_cannot_escape_vault(self) -> None:
        payload = {
            "items": [
                {
                    "note_id": "unsafe-vault-media",
                    "title": "不安全 Vault 媒体",
                    "media": [{"vault_path": "../private.jpg"}],
                }
            ]
        }
        self.export.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "outside the allowed root"):
            import_export(self.export, self.vault, "Sources/XHS")

    def test_reads_streamed_json_from_stdin(self) -> None:
        payload = json.dumps(
            [{"id": "streamed-1", "title": "标准输入笔记", "liked": True}],
            ensure_ascii=False,
        )
        with patch("sys.stdin", io.StringIO(payload)):
            result = import_export(Path("-"), self.vault, "Sources/XHS", dry_run=True)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.planned[0]["action"], "create")


if __name__ == "__main__":
    unittest.main()
