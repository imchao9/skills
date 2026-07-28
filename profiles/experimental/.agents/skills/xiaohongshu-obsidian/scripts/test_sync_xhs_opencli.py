#!/usr/bin/env python3
"""Offline regression tests for sync_xhs_opencli.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sync_xhs_opencli import (
    OpenCliError,
    parse_json_document,
    scan_downloaded_media,
    sync_xiaohongshu,
    write_sanitized_export,
)

SYNC_SCRIPT = Path(__file__).with_name("sync_xhs_opencli.py")


class FakeRunner:
    def __init__(self, *, authenticated: bool = True) -> None:
        self.authenticated = authenticated
        self.calls: list[tuple[str, ...]] = []

    def run_json(self, *args: str) -> Any:
        self.calls.append(args)
        command = args[0]
        if command == "whoami":
            return {"logged_in": self.authenticated}
        if command == "saved":
            return [
                {
                    "id": "note-1",
                    "title": "列表标题",
                    "author": "作者",
                    "likes": "12",
                    "url": (
                        "https://www.xiaohongshu.com/explore/note-1"
                        "?xsec_token=secret&source=web"
                    ),
                }
            ]
        if command == "liked":
            return [
                {
                    "id": "note-1",
                    "title": "列表标题",
                    "author": "作者",
                    "likes": "12",
                    "url": (
                        "https://www.xiaohongshu.com/explore/note-1"
                        "?xsec_token=other-secret&source=web"
                    ),
                }
            ]
        if command == "creator-notes":
            return [
                {
                    "id": "owned-1",
                    "title": "自发笔记",
                    "date": "2026年07月01日 10:00",
                    "views": 100,
                    "likes": 8,
                    "collects": 2,
                    "comments": 3,
                    "url": (
                        "https://creator.xiaohongshu.com/statistics/note-detail"
                        "?noteId=owned-1"
                    ),
                }
            ]
        if command == "note":
            return [
                {"field": "title", "value": "详情标题"},
                {"field": "author", "value": "作者"},
                {"field": "content", "value": "正文"},
                {"field": "likes", "value": "13"},
                {"field": "collects", "value": "4"},
                {"field": "comments", "value": "2"},
                {"field": "tags", "value": "#AI, Obsidian"},
            ]
        if command == "comments":
            return [
                {
                    "author": "甲",
                    "text": "主评论",
                    "likes": 2,
                    "time": "昨天",
                    "is_reply": False,
                    "reply_to": "",
                },
                {
                    "author": "乙",
                    "text": "回复",
                    "likes": 1,
                    "time": "昨天",
                    "is_reply": True,
                    "reply_to": "甲",
                },
            ]
        raise AssertionError(f"unexpected command: {args}")


class SyncXhsOpenCliTest(unittest.TestCase):
    def make_fake_opencli(self, root: Path) -> tuple[Path, Path]:
        executable = root / "fake-opencli.py"
        log_path = root / "fake-opencli.log"
        executable.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
command = args[1]
log_path = Path(os.environ["FAKE_OPENCLI_LOG"])
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(command + "\\n")

if command == "saved":
    payload = [{
        "id": "note-1",
        "title": "列表标题",
        "author": "作者",
        "likes": "12",
        "url": "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret&source=web",
    }]
elif command == "note":
    if os.environ.get("FAKE_OPENCLI_FAIL_NOTE_ONCE"):
        marker = Path(os.environ["FAKE_OPENCLI_FAIL_MARKER"])
        if not marker.exists():
            marker.write_text("failed", encoding="utf-8")
            print("temporary failure", file=sys.stderr)
            raise SystemExit(69)
    payload = [
        {"field": "title", "value": "详情标题"},
        {"field": "author", "value": "作者"},
        {"field": "content", "value": "正文"},
        {"field": "likes", "value": "13"},
    ]
elif command == "comments":
    if os.environ.get("FAKE_OPENCLI_FAIL_COMMENTS_ALWAYS"):
        print("temporary comments failure", file=sys.stderr)
        raise SystemExit(69)
    payload = [{
        "author": "评论者",
        "text": "评论正文",
        "likes": 2,
        "time": "昨天",
        "is_reply": False,
        "reply_to": "",
    }]
elif command == "download":
    output = Path(args[args.index("--output") + 1])
    note_dir = output / "note-1"
    note_dir.mkdir(parents=True, exist_ok=True)
    (note_dir / "note-1_1.jpg").write_bytes(b"image")
    payload = [{"index": 1, "type": "image", "status": "success", "size": "5 B"}]
elif command == "whoami":
    payload = {"logged_in": True}
else:
    payload = []
print(json.dumps(payload, ensure_ascii=False))
""",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable, log_path

    def run_cli(
        self,
        root: Path,
        executable: Path,
        log_path: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        vault = root / "Vault"
        vault.mkdir(exist_ok=True)
        state_file = root / "state.json"
        environment = os.environ.copy()
        environment["FAKE_OPENCLI_LOG"] = str(log_path)
        return subprocess.run(
            [
                sys.executable,
                str(SYNC_SCRIPT),
                "--opencli",
                str(executable),
                "--source",
                "saved",
                "--limit",
                "1",
                "--skip-auth-check",
                "--interval",
                "0",
                "--vault",
                str(vault),
                "--folder",
                "Sources/XHS",
                "--state-file",
                str(state_file),
                "--retries",
                "0",
                "--retry-delay",
                "0",
                *extra,
            ],
            cwd=SYNC_SCRIPT.parent,
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
            check=False,
        )

    def test_json_parser_ignores_runtime_warning(self) -> None:
        output = "(node:1) Warning: test\nUse trace\n[{\"id\":\"one\"}]\n"
        self.assertEqual(parse_json_document(output), [{"id": "one"}])

    def test_sync_merges_sources_enriches_and_sanitizes(self) -> None:
        runner = FakeRunner()
        items, report = sync_xiaohongshu(
            runner,
            sources=["saved", "liked", "authored"],
            limit=3,
            auth_check=True,
            fetch_details=True,
            fetch_comments=True,
            with_replies=True,
            interval=0,
        )

        self.assertEqual(len(items), 2)
        note = next(item for item in items if item["note_id"] == "note-1")
        self.assertEqual(note["kind"], "favorite, liked")
        self.assertEqual(note["title"], "详情标题")
        self.assertEqual(note["content"], "正文")
        self.assertEqual(note["comments_count"], "2")
        self.assertEqual(note["tags"], ["AI", "Obsidian"])
        self.assertNotIn("xsec_token", note["url"])
        self.assertNotIn("_raw_url", note)
        self.assertEqual(note["comments"][0]["replies"][0]["content"], "回复")
        authored = next(item for item in items if item["note_id"] == "owned-1")
        self.assertEqual(authored["kind"], "authored")
        self.assertEqual(authored["views"], "100")
        self.assertEqual(report.details_fetched, 1)
        self.assertEqual(report.comments_fetched, 1)
        self.assertEqual(report.errors, [])

    def test_export_never_persists_signed_url(self) -> None:
        runner = FakeRunner()
        items, report = sync_xiaohongshu(
            runner,
            sources=["saved"],
            limit=1,
            auth_check=True,
            fetch_details=False,
            interval=0,
        )
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "export.json"
            write_sanitized_export(output, items, report, ["saved"], 1)
            text = output.read_text(encoding="utf-8")
            self.assertNotIn("xsec_token", text)
            payload = json.loads(text)
            self.assertEqual(payload["manifest"]["completeness"].split(";")[0], "bounded")

    def test_media_scan_returns_only_supported_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            note_dir = root / "note-1"
            note_dir.mkdir()
            (note_dir / "note-1_1.jpg").write_bytes(b"image")
            (note_dir / "note-1_2.mp4").write_bytes(b"video")
            (note_dir / "ignored.txt").write_text("no", encoding="utf-8")
            media = scan_downloaded_media(root, "note-1")
            self.assertEqual([entry["type"] for entry in media], ["image", "video"])

    def test_login_is_required(self) -> None:
        with self.assertRaisesRegex(OpenCliError, "not logged in"):
            sync_xiaohongshu(
                FakeRunner(authenticated=False),
                sources=["saved"],
                limit=1,
                auth_check=True,
                interval=0,
            )

    def test_cli_state_makes_new_only_skip_seen_notes_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)

            first = self.run_cli(root, executable, log_path)
            self.assertEqual(first.returncode, 0, first.stderr)
            state_text = (root / "state.json").read_text(encoding="utf-8")
            self.assertNotIn("xsec_token", state_text)
            self.assertEqual(json.loads(state_text)["notes"]["note-1"]["status"], "complete")

            second = self.run_cli(root, executable, log_path, "--new-only")
            self.assertEqual(second.returncode, 0, second.stderr)
            second_result = json.loads(second.stdout)
            self.assertEqual(second_result["sync"]["skipped_seen"], 1)
            self.assertEqual(log_path.read_text(encoding="utf-8").splitlines().count("note"), 1)
            self.assertEqual(
                len(list((root / "Vault" / "Sources" / "XHS").glob("*.md"))),
                1,
            )

    def test_cli_retries_a_transient_note_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)
            with patch.dict(
                os.environ,
                {
                    "FAKE_OPENCLI_FAIL_NOTE_ONCE": "1",
                    "FAKE_OPENCLI_FAIL_MARKER": str(root / "note-failed-once"),
                },
            ):
                result = self.run_cli(
                    root,
                    executable,
                    log_path,
                    "--retries",
                    "1",
                )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["sync"]["retry_attempts"], 1)
            self.assertEqual(log_path.read_text(encoding="utf-8").splitlines().count("note"), 2)
            self.assertEqual(json.loads((root / "state.json").read_text())["notes"]["note-1"]["status"], "complete")

    def test_cli_resumes_a_partial_note_without_refetching_completed_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)
            with patch.dict(os.environ, {"FAKE_OPENCLI_FAIL_COMMENTS_ALWAYS": "1"}):
                first = self.run_cli(
                    root,
                    executable,
                    log_path,
                    "--comments",
                )

            self.assertEqual(first.returncode, 0, first.stderr)
            first_state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            first_note = first_state["notes"]["note-1"]
            self.assertEqual(first_note["status"], "partial")
            self.assertIn("details", first_note["completed_steps"])
            self.assertEqual(first_note["item"]["content"], "正文")

            second = self.run_cli(
                root,
                executable,
                log_path,
                "--comments",
                "--new-only",
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            second_result = json.loads(second.stdout)
            self.assertEqual(second_result["sync"]["resumed_steps"], 1)
            calls = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(calls.count("note"), 1)
            self.assertEqual(calls.count("comments"), 2)
            final_state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(final_state["notes"]["note-1"]["status"], "complete")
            note_text = next(
                (root / "Vault" / "Sources" / "XHS").glob("*.md")
            ).read_text(encoding="utf-8")
            self.assertIn("评论正文", note_text)

    def test_cli_keeps_checkpoint_when_import_fails_then_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)

            failed = self.run_cli(
                root,
                executable,
                log_path,
                "--folder",
                "../outside",
            )
            self.assertEqual(failed.returncode, 1)
            checkpoint = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["notes"]["note-1"]["status"], "partial")
            self.assertIn("details", checkpoint["notes"]["note-1"]["completed_steps"])

            resumed = self.run_cli(
                root,
                executable,
                log_path,
                "--new-only",
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(
                log_path.read_text(encoding="utf-8").splitlines().count("note"),
                1,
            )
            final_state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(final_state["notes"]["note-1"]["status"], "complete")

    def test_cli_redownloads_checkpointed_media_when_temporary_files_are_gone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)

            failed = self.run_cli(
                root,
                executable,
                log_path,
                "--download-media",
                "--folder",
                "../outside",
            )
            self.assertEqual(failed.returncode, 1)
            checkpoint = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertIn("media", checkpoint["notes"]["note-1"]["completed_steps"])

            resumed = self.run_cli(
                root,
                executable,
                log_path,
                "--download-media",
                "--new-only",
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            calls = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(calls.count("download"), 2)
            copied = list(
                (root / "Vault" / "Sources" / "XHS" / "_media" / "note-1").glob("*.jpg")
            )
            self.assertEqual(len(copied), 1)

    def test_cli_refresh_preserves_previous_comments_and_media_when_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable, log_path = self.make_fake_opencli(root)

            first = self.run_cli(
                root,
                executable,
                log_path,
                "--comments",
                "--download-media",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            note_path = next((root / "Vault" / "Sources" / "XHS").glob("*.md"))
            first_text = note_path.read_text(encoding="utf-8")
            self.assertIn("评论正文", first_text)
            self.assertIn("![[", first_text)

            second = self.run_cli(root, executable, log_path)
            self.assertEqual(second.returncode, 0, second.stderr)
            second_result = json.loads(second.stdout)
            self.assertEqual(second_result["import"]["unchanged"], 1)
            second_text = note_path.read_text(encoding="utf-8")
            self.assertIn("评论正文", second_text)
            self.assertIn("![[", second_text)


if __name__ == "__main__":
    unittest.main()
