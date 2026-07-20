import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import publish


def draft_text(
    *,
    title="编程猫 API 设计",
    date="2026-07-12",
    submitter="Original",
    topics=("后端", "API"),
    body="正文\n",
):
    topic_lines = "\n".join(f"  - {topic}" for topic in topics)
    return (
        "---\n"
        f"title: {title}\n"
        f"date: {date}\n"
        f"submitter: {submitter}\n"
        "topics:\n"
        f"{topic_lines}\n"
        "---\n"
        f"{body}"
    )


class PublishUnitTests(unittest.TestCase):
    def test_rejects_invalid_dates_and_non_chinese_topics(self):
        invalid = [
            ("2026-02-30-编程猫.md", draft_text(date="2026-02-30", title="编程猫")),
            ("2026-07-12-api-123.md", draft_text(title="api-123")),
            ("2026-7-12-编程猫.md", draft_text(title="编程猫")),
        ]
        for filename, content in invalid:
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    publish.validate_document(filename, content.encode("utf-8"))

    def test_rejects_invalid_frontmatter(self):
        cases = {
            "missing": "正文\n",
            "malformed": "---\ntitle 编程猫\n---\n正文\n",
            "title mismatch": draft_text(title="别的主题"),
            "date mismatch": draft_text(date="2026-07-11"),
            "zero topics": draft_text(topics=()),
            "four topics": draft_text(topics=("一", "二", "三", "四")),
        }
        for label, content in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    publish.validate_document(
                        "2026-07-12-编程猫 API 设计.md", content.encode("utf-8")
                    )

    def test_calculates_target_paths_and_rejects_traversal(self):
        filename = "2026-07-12-编程猫.md"
        self.assertEqual(
            publish.target_path("", filename), "2026-07-12/2026-07-12-编程猫.md"
        )
        self.assertEqual(
            publish.target_path("/docs/learning/", filename),
            "docs/learning/2026-07-12/2026-07-12-编程猫.md",
        )
        for value in ("..", "docs/../secrets", "/../docs/"):
            with self.subTest(base_path=value), self.assertRaises(ValueError):
                publish.target_path(value, filename)

    def test_classifies_missing_same_and_different_submitter_targets(self):
        existing = draft_text(title="编程猫", submitter="Alice").encode("utf-8")
        self.assertEqual(publish.classify_target(None, "2026-07-12", "Alice"), "created")
        self.assertEqual(
            publish.classify_target(existing, "2026-07-12", "Alice"), "updated"
        )
        self.assertEqual(
            publish.classify_target(existing, "2026-07-12", "Bob"), "collision"
        )
        missing_submitter = existing.replace(b"submitter: Alice\n", b"")
        self.assertEqual(
            publish.classify_target(missing_submitter, "2026-07-12", "Alice"),
            "collision",
        )

    def test_help_describes_safety_contract(self):
        parser = publish.build_parser()
        help_text = parser.format_help()
        for phrase in (
            "exit 0",
            "exit 1",
            "exit 3",
            "repository_ssh_url",
            "branch",
            "base_path",
            "same submitter",
            "retry",
            "origin/main",
            "delete",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, help_text)

    def test_cli_argument_error_returns_one_json_object_and_exit_one(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = publish.main([])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "error")
        self.assertEqual(len(stdout.getvalue().splitlines()), 1)


class PublishIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.gitconfig = self.root / "gitconfig"
        self.gitconfig.write_text("[user]\n\temail = test@example.com\n", encoding="utf-8")
        self.env = os.environ.copy()
        self.env["GIT_CONFIG_GLOBAL"] = str(self.gitconfig)
        self.env["CODEMAO_LEARNING_ALLOW_LOCAL_REMOTE"] = "1"
        self._git("init", "--bare", "--initial-branch=main", str(self.remote))
        seed = self.root / "seed"
        self._git("clone", str(self.remote), str(seed))
        (seed / "README.md").write_text("seed\n", encoding="utf-8")
        self._git("-C", str(seed), "add", "README.md")
        self._git(
            "-C", str(seed), "-c", "user.name=Seed", "commit", "-m", "seed"
        )
        self._git("-C", str(seed), "push", "origin", "main")
        self.config = self.root / "config.json"
        self.write_config()

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args, check=True):
        return subprocess.run(
            ["git", *args],
            check=check,
            capture_output=True,
            env=self.env,
            text=True,
        )

    def write_config(self, **overrides):
        config = {
            "repository_ssh_url": str(self.remote),
            "branch": "main",
            "base_path": "learning",
        }
        config.update(overrides)
        self.config.write_text(json.dumps(config), encoding="utf-8")

    def run_publish(self, draft, submitter="Alice"):
        stdout = io.StringIO()
        old_env = os.environ.copy()
        os.environ.update(self.env)
        try:
            with contextlib.redirect_stdout(stdout):
                code = publish.main(
                    [str(draft), "--config", str(self.config), "--submitter", submitter]
                )
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        return code, json.loads(stdout.getvalue())

    def remote_bytes(self, target):
        result = subprocess.run(
            ["git", f"--git-dir={self.remote}", "show", f"main:{target}"],
            check=True,
            capture_output=True,
        )
        return result.stdout

    def seed_target(self, target, content):
        checkout = self.root / f"checkout-{len(list(self.root.glob('checkout-*')))}"
        self._git("clone", str(self.remote), str(checkout))
        path = checkout / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self._git("-C", str(checkout), "add", target)
        self._git(
            "-C", str(checkout), "-c", "user.name=Seed", "commit", "-m", "existing"
        )
        self._git("-C", str(checkout), "push", "origin", "main")

    def test_creates_remote_file_with_commit_and_exact_bytes_then_deletes_draft(self):
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        code, result = self.run_publish(draft)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "created")
        target = "learning/2026-07-12/2026-07-12-编程猫 API 设计.md"
        expected = draft_text(submitter='"Alice"').encode("utf-8")
        self.assertEqual(self.remote_bytes(target), expected)
        subject = self._git(
            f"--git-dir={self.remote}", "log", "-1", "--format=%s", "main"
        ).stdout.strip()
        self.assertEqual(subject, "docs(learning): 发布《编程猫 API 设计》")
        self.assertFalse(draft.exists())
        self.assertTrue(result.get("commit"))

    def test_updates_same_submitter_by_complete_replacement(self):
        target = "learning/2026-07-12/2026-07-12-编程猫 API 设计.md"
        old = draft_text(submitter="Alice", body="旧正文\nextra\n").encode("utf-8")
        self.seed_target(target, old)
        draft = self.root / Path(target).name
        draft.write_text(draft_text(body="新正文\n"), encoding="utf-8")
        code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (0, "updated"))
        self.assertEqual(
            self.remote_bytes(target),
            draft_text(submitter='"Alice"', body="新正文\n").encode(),
        )
        subject = self._git(
            f"--git-dir={self.remote}", "log", "-1", "--format=%s", "main"
        ).stdout.strip()
        self.assertEqual(subject, "docs(learning): 更新《编程猫 API 设计》")

    def test_identical_same_submitter_republish_is_idempotent_update(self):
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        first_code, first = self.run_publish(draft)
        self.assertEqual((first_code, first["status"]), (0, "created"))
        draft.write_text(draft_text(), encoding="utf-8")
        before = self._git(
            f"--git-dir={self.remote}", "rev-parse", "main"
        ).stdout.strip()
        before_count = self._git(
            f"--git-dir={self.remote}", "rev-list", "--count", "main"
        ).stdout.strip()

        second_code, second = self.run_publish(draft)

        after = self._git(f"--git-dir={self.remote}", "rev-parse", "main").stdout.strip()
        after_count = self._git(
            f"--git-dir={self.remote}", "rev-list", "--count", "main"
        ).stdout.strip()
        self.assertEqual((second_code, second["status"]), (0, "updated"))
        self.assertEqual(second["commit"], before)
        self.assertEqual(after, before)
        self.assertEqual(after_count, before_count)
        self.assertFalse(draft.exists())

    def test_yaml_sensitive_submitters_round_trip_exactly(self):
        names = ('Alice # Team', 'Alice: Team', 'Alice "Quoted"', r"Alice \\ Team")
        for index, name in enumerate(names):
            title = f"编程猫 YAML {index}"
            filename = f"2026-07-12-{title}.md"
            draft = self.root / filename
            draft.write_text(draft_text(title=title), encoding="utf-8")
            code, result = self.run_publish(draft, submitter=name)
            with self.subTest(name=name):
                self.assertEqual((code, result["status"]), (0, "created"))
                target = f"learning/2026-07-12/{filename}"
                remote = self.remote_bytes(target)
                parsed, _, _, _ = publish._frontmatter(remote)
                self.assertEqual(parsed["submitter"], name)
                quoted = json.dumps(name, ensure_ascii=False).encode("utf-8")
                self.assertIn(b"submitter: " + quoted + b"\n", remote)

    def test_collision_returns_three_preserves_remote_and_draft(self):
        target = "learning/2026-07-12/2026-07-12-编程猫 API 设计.md"
        original = draft_text(submitter="Bob", body="Bob 内容\n").encode()
        self.seed_target(target, original)
        draft = self.root / Path(target).name
        draft.write_text(draft_text(body="Alice 内容\n"), encoding="utf-8")
        code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (3, "collision"))
        self.assertIn("message", result)
        self.assertEqual(self.remote_bytes(target), original)
        self.assertTrue(draft.exists())

    def test_configuration_failure_preserves_draft(self):
        self.write_config(branch="dev")
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (1, "error"))
        self.assertTrue(draft.exists())

    def test_git_failure_preserves_draft(self):
        self.write_config(repository_ssh_url=str(self.root / "missing.git"))
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (1, "error"))
        self.assertEqual(
            result["target_path"],
            "learning/2026-07-12/2026-07-12-编程猫 API 设计.md",
        )
        self.assertTrue(draft.exists())

    def test_rejects_non_ssh_remote_without_explicit_local_test_flag(self):
        self.env.pop("CODEMAO_LEARNING_ALLOW_LOCAL_REMOTE", None)
        for remote in (str(self.remote), "file:///tmp/repository.git", "https://example.test/repo.git"):
            with self.subTest(remote=remote):
                self.write_config(repository_ssh_url=remote)
                draft = self.root / "2026-07-12-编程猫 API 设计.md"
                draft.write_text(draft_text(), encoding="utf-8")
                code, result = self.run_publish(draft)
                self.assertEqual((code, result["status"]), (1, "error"))
                self.assertIn("SSH", result["message"])
                self.assertTrue(draft.exists())

    def test_non_fast_forward_retries_once_then_succeeds(self):
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        outcomes = [
            {"kind": "retry"},
            {"kind": "success", "status": "created", "commit": "abc123"},
        ]
        with mock.patch.object(publish, "_publish_attempt", side_effect=outcomes) as attempt:
            code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (0, "created"))
        self.assertEqual(attempt.call_count, 2)
        self.assertFalse(draft.exists())

    def test_retry_reclassifies_latest_target_as_collision(self):
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        outcomes = [{"kind": "retry"}, {"kind": "collision"}]
        with mock.patch.object(publish, "_publish_attempt", side_effect=outcomes) as attempt:
            code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (3, "collision"))
        self.assertEqual(attempt.call_count, 2)
        self.assertTrue(draft.exists())

    def test_retry_exhaustion_stops_after_two_attempts_and_preserves_draft(self):
        draft = self.root / "2026-07-12-编程猫 API 设计.md"
        draft.write_text(draft_text(), encoding="utf-8")
        outcomes = [{"kind": "retry"}, {"kind": "retry"}]
        with mock.patch.object(publish, "_publish_attempt", side_effect=outcomes) as attempt:
            code, result = self.run_publish(draft)
        self.assertEqual((code, result["status"]), (1, "error"))
        self.assertEqual(attempt.call_count, 2)
        self.assertIn("after one safe retry", result["message"])
        self.assertTrue(draft.exists())


if __name__ == "__main__":
    unittest.main()
