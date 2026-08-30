from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).parents[1] / "scripts" / "baidu_sync.py"
SPEC = importlib.util.spec_from_file_location("baidu_sync", SCRIPT)
assert SPEC and SPEC.loader
baidu_sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = baidu_sync
SPEC.loader.exec_module(baidu_sync)


class BaiduSyncTest(unittest.TestCase):
    def test_safe_remote_name_replaces_baidu_invalid_characters(self) -> None:
        self.assertEqual(
            baidu_sync.safe_remote_name("混沌湾区 30号 第一节 02:28.mp4"),
            "混沌湾区 30号 第一节 02_28.mp4",
        )

    def test_safe_remote_name_replaces_control_and_emoji_characters(self) -> None:
        self.assertEqual(
            baidu_sync.safe_remote_name("\x7f\x7f 黑仔与大孖👑-集锦.mp4"),
            "__ 黑仔与大孖_-集锦.mp4",
        )

    def test_remote_name_collision_is_rejected(self) -> None:
        items = [{"remote_name": "02_28.mp4"}, {"remote_name": "02_28.mp4"}]
        with self.assertRaisesRegex(ValueError, "collision"):
            baidu_sync.ensure_unique_remote_names(items, "/比赛/个人精彩片段")

    def test_upload_failure_text_is_not_treated_as_success(self) -> None:
        command = [sys.executable, "-c", "print('以下文件上传失败')"]
        with self.assertRaisesRegex(RuntimeError, "reported failure"):
            baidu_sync.run(command, failure_markers=baidu_sync.UPLOAD_FAILURE_MARKERS)

    def test_non_video_attachment_uses_file_size_without_probe(self) -> None:
        self.assertEqual(baidu_sync.safe_remote_name("球评_比赛.html"), "球评_比赛.html")

    def test_remote_meta_retries_until_exact_path_and_size_are_indexed(self) -> None:
        responses = iter([
            SimpleNamespace(stdout="not indexed"),
            SimpleNamespace(stdout="/比赛/片段.mp4 size: 12345"),
        ])
        attempts = baidu_sync.verify_remote_item(
            "baidu",
            {"remote": "/比赛/片段.mp4", "remote_name": "片段.mp4", "bytes": 12345},
            attempts=3,
            interval_seconds=0,
            runner=lambda _: next(responses),
            sleeper=lambda _: None,
        )
        self.assertEqual(attempts, 2)

    def test_remote_meta_rejects_size_as_part_of_a_larger_number(self) -> None:
        item = {"remote": "/比赛/a.mp4", "remote_name": "a.mp4", "bytes": 123}
        self.assertFalse(baidu_sync.meta_matches_item("/比赛/a.mp4 size: 91234", item))

    def test_remote_path_collision_across_categories_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "across categories"):
            baidu_sync.ensure_unique_remote_paths([
                {"remote": "/比赛/a.mp4"},
                {"remote": "/比赛/a.mp4"},
            ])


if __name__ == "__main__":
    unittest.main()
