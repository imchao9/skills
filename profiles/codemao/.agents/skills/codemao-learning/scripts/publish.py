#!/usr/bin/env python3
"""Publish a validated codemao-learning draft to the configured Git repository."""

import argparse
from datetime import date
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse


FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class PublishError(Exception):
    def __init__(self, message, target_path=""):
        super().__init__(message)
        self.target_path = target_path


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise PublishError(f"invalid arguments: {message}")


def _frontmatter(content):
    try:
        text = content.decode("utf-8") if isinstance(content, bytes) else content
    except UnicodeDecodeError as exc:
        raise ValueError("draft must be valid UTF-8") from exc
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError("frontmatter must begin with an exact --- line")
    end = next(
        (index for index, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"),
        None,
    )
    if end is None:
        raise ValueError("frontmatter must end with an exact --- line")

    scalars = {}
    topics = None
    index = 1
    while index < end:
        raw = lines[index].rstrip("\r\n")
        match = re.fullmatch(r"(title|date|submitter):\s*(.+)", raw)
        if match:
            key, value = match.groups()
            if key in scalars or not value.strip():
                raise ValueError(f"invalid frontmatter field: {key}")
            value = value.strip()
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid quoted frontmatter field: {key}") from exc
                if not isinstance(value, str) or not value:
                    raise ValueError(f"invalid frontmatter field: {key}")
            scalars[key] = value
            index += 1
            continue
        if raw == "topics:":
            if topics is not None:
                raise ValueError("duplicate topics field")
            topics = []
            index += 1
            while index < end:
                item = re.fullmatch(r"\s+-\s+(.+)", lines[index].rstrip("\r\n"))
                if not item:
                    break
                value = item.group(1).strip()
                if not value:
                    raise ValueError("topic values must be non-empty")
                topics.append(value)
                index += 1
            continue
        raise ValueError(f"malformed frontmatter line: {raw}")

    if set(scalars) != {"title", "date", "submitter"}:
        raise ValueError("frontmatter requires title, date, and submitter")
    if topics is None or not 1 <= len(topics) <= 3:
        raise ValueError("topics must contain one to three values")
    return scalars, topics, lines, end


def validate_document(filename, content):
    match = FILENAME_RE.fullmatch(filename)
    if not match:
        raise ValueError("filename must match YYYY-MM-DD-TOPIC.md")
    filename_date, filename_topic = match.groups()
    try:
        date.fromisoformat(filename_date)
    except ValueError as exc:
        raise ValueError("filename date is not a real calendar date") from exc
    if not CJK_RE.search(filename_topic):
        raise ValueError("filename topic must contain a CJK Unified Ideograph")

    scalars, topics, _, _ = _frontmatter(content)
    if scalars["date"] != filename_date:
        raise ValueError("frontmatter date must equal filename date")
    if scalars["title"] != filename_topic:
        raise ValueError("frontmatter title must equal filename topic")
    return {
        "date": filename_date,
        "title": filename_topic,
        "submitter": scalars["submitter"],
        "topics": topics,
    }


def finalize_document(content, submitter):
    if not submitter or "\n" in submitter or "\r" in submitter:
        raise ValueError("submitter must be a non-empty single-line value")
    _, _, lines, end = _frontmatter(content)
    for index in range(1, end):
        if re.match(r"submitter:\s*", lines[index]):
            ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
            if not lines[index].endswith(("\n", "\r")):
                ending = ""
            serialized = json.dumps(submitter, ensure_ascii=False)
            lines[index] = f"submitter: {serialized}{ending}"
            break
    return "".join(lines).encode("utf-8")


def normalize_base_path(base_path):
    if not isinstance(base_path, str):
        raise ValueError("base_path must be a string")
    normalized = base_path.strip("/")
    if any(part == ".." for part in PurePosixPath(normalized).parts):
        raise ValueError("base_path must not contain .. segments")
    return normalized


def target_path(base_path, filename):
    match = FILENAME_RE.fullmatch(filename)
    if not match:
        raise ValueError("invalid filename")
    base = normalize_base_path(base_path)
    components = [component for component in (base, match.group(1), filename) if component]
    return "/".join(components)


def classify_target(existing_content, filename_date, submitter):
    if existing_content is None:
        return "created"
    try:
        scalars, _, _, _ = _frontmatter(existing_content)
    except ValueError:
        return "collision"
    if scalars.get("submitter") == submitter and scalars.get("date") == filename_date:
        return "updated"
    return "collision"


def build_parser():
    description = """Publish a learning draft.
Config JSON fields: repository_ssh_url, branch, and base_path; branch must be main.
A missing target is created. An existing target is replaced only for the same submitter
and filename date; otherwise it is a collision. The publisher never force-pushes.
It makes one safe retry after a non-fast-forward push by recloning and reclassifying
the target, then verifies exact bytes from origin/main. The original draft is deleted
only after remote verification; errors and collisions preserve it.
Exit codes: exit 0 created/updated, exit 1 validation/configuration/Git/verification
error, exit 3 collision."""
    parser = JsonArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("draft", help="UTF-8 Markdown draft to publish")
    parser.add_argument("--config", required=True, help="path to publisher config JSON")
    parser.add_argument("--submitter", required=True, help="publisher name recorded in Git and frontmatter")
    return parser


def _git(args, cwd=None, check=True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=False
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise PublishError(message or f"git {' '.join(args)} failed")
    return result


def _read_config(path):
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublishError(f"invalid config: {exc}") from exc
    if not isinstance(config, dict):
        raise PublishError("config must be a JSON object")
    for field in ("repository_ssh_url", "branch", "base_path"):
        if field not in config or not isinstance(config[field], str):
            raise PublishError(f"config field {field} must be a string")
    if not config["repository_ssh_url"]:
        raise PublishError("repository_ssh_url must not be empty")
    _validate_repository_url(config["repository_ssh_url"])
    if config["branch"] != "main":
        raise PublishError("config branch must equal main")
    try:
        config["base_path"] = normalize_base_path(config["base_path"])
    except ValueError as exc:
        raise PublishError(str(exc)) from exc
    return config


def _validate_repository_url(repository_url):
    scp_style = re.fullmatch(r"[^@\s/:]+@[^\s/:]+:.+", repository_url)
    parsed = urlparse(repository_url)
    ssh_url = (
        parsed.scheme == "ssh"
        and bool(parsed.hostname)
        and bool(parsed.path and parsed.path != "/")
    )
    if scp_style or ssh_url:
        return

    local_test_enabled = os.environ.get("CODEMAO_LEARNING_ALLOW_LOCAL_REMOTE") == "1"
    absolute_local = os.path.isabs(repository_url)
    file_local = (
        parsed.scheme == "file" and bool(parsed.path) and os.path.isabs(parsed.path)
    )
    if local_test_enabled and (absolute_local or file_local):
        return
    raise PublishError(
        "repository_ssh_url must be an SSH URL; local remotes require "
        "CODEMAO_LEARNING_ALLOW_LOCAL_REMOTE=1 for tests"
    )


def _existing_bytes(clone, target):
    result = _git(["show", f"HEAD:{target}"], cwd=clone, check=False)
    if result.returncode == 0:
        return result.stdout
    return None


def _is_non_fast_forward(result):
    message = (result.stdout + result.stderr).decode("utf-8", errors="replace").lower()
    return "non-fast-forward" in message or "fetch first" in message


def _publish_attempt(config, target, filename_date, title, submitter, finalized):
    with tempfile.TemporaryDirectory(prefix="codemao-learning-publish-") as temporary:
        clone = Path(temporary) / "repository"
        _git(
            [
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--branch",
                "main",
                config["repository_ssh_url"],
                str(clone),
            ]
        )
        _git(["config", "user.name", submitter], cwd=clone)
        email = _git(["config", "--get", "user.email"], cwd=clone, check=False)
        if email.returncode or not email.stdout.strip():
            raise PublishError("Git user.email is not configured")

        existing = _existing_bytes(clone, target)
        status = classify_target(existing, filename_date, submitter)
        if status == "collision":
            return {"kind": "collision"}
        if status == "updated" and existing == finalized:
            _git(["fetch", "origin", "main"], cwd=clone)
            remote = _git(["show", f"origin/main:{target}"], cwd=clone)
            if remote.stdout != finalized:
                raise PublishError("remote verification failed: bytes differ")
            commit = _git(["rev-parse", "origin/main"], cwd=clone).stdout.decode().strip()
            return {"kind": "success", "status": "updated", "commit": commit}

        destination = clone / Path(*PurePosixPath(target).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(finalized)
        _git(["add", "--", target], cwd=clone)
        verb = "发布" if status == "created" else "更新"
        _git(["commit", "-m", f"docs(learning): {verb}《{title}》"], cwd=clone)
        commit = _git(["rev-parse", "HEAD"], cwd=clone).stdout.decode().strip()
        pushed = _git(["push", "origin", "main"], cwd=clone, check=False)
        if pushed.returncode:
            if _is_non_fast_forward(pushed):
                return {"kind": "retry"}
            message = pushed.stderr.decode("utf-8", errors="replace").strip()
            raise PublishError(message or "git push failed")

        _git(["fetch", "origin", "main"], cwd=clone)
        remote = _git(["show", f"origin/main:{target}"], cwd=clone)
        if remote.stdout != finalized:
            raise PublishError("remote verification failed: bytes differ")
        return {"kind": "success", "status": status, "commit": commit}


def _result(status, target, message=None, commit=None):
    result = {"status": status, "target_path": target}
    if commit is not None:
        result["commit"] = commit
    if message is not None:
        result["message"] = message
    return result


def run(draft_path, config_path, submitter):
    draft = Path(draft_path)
    try:
        original = draft.read_bytes()
    except OSError as exc:
        raise PublishError(f"cannot read draft: {exc}") from exc
    try:
        metadata = validate_document(draft.name, original)
        finalized = finalize_document(original, submitter)
    except ValueError as exc:
        raise PublishError(str(exc)) from exc
    config = _read_config(config_path)
    target = target_path(config["base_path"], draft.name)

    try:
        for attempt_number in range(2):
            attempt = _publish_attempt(
                config,
                target,
                metadata["date"],
                metadata["title"],
                submitter,
                finalized,
            )
            if attempt["kind"] == "retry" and attempt_number == 0:
                continue
            if attempt["kind"] == "retry":
                raise PublishError("non-fast-forward push failed after one safe retry")
            if attempt["kind"] == "collision":
                return 3, _result(
                    "collision", target, "target belongs to a different or missing submitter"
                )
            try:
                draft.unlink()
            except OSError as exc:
                raise PublishError(f"published but could not delete draft: {exc}") from exc
            return 0, _result(attempt["status"], target, commit=attempt["commit"])
        raise PublishError("publication failed")
    except PublishError as exc:
        exc.target_path = target
        raise


def main(argv=None):
    target = ""
    try:
        args = build_parser().parse_args(argv)
        code, result = run(args.draft, args.config, args.submitter)
    except (PublishError, ValueError, OSError) as exc:
        target = getattr(exc, "target_path", target)
        result = _result("error", target, str(exc))
        code = 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
