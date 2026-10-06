#!/usr/bin/env python3
"""Read authorized Xiaohongshu data through OpenCLI and import it into Obsidian."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from import_xhs_export import (
    ImportStats,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    import_items,
    listify,
    sanitize_text,
    sanitize_url,
)


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SENSITIVE_TEXT_RE = re.compile(
    r"(?i)\b(xsec[_-]?token|access[_-]?token|authorization|cookie|session|signature)"
    r"\s*[:=]\s*([^\s,&]+)"
)
SOURCE_COMMANDS = {
    "saved": ("saved", "favorite"),
    "liked": ("liked", "liked"),
    "authored": ("creator-notes", "authored"),
}


class OpenCliError(RuntimeError):
    """Safe OpenCLI error that never includes the invoked signed URL."""


@dataclass
class SyncReport:
    source_counts: dict[str, int] = field(default_factory=dict)
    unique_notes: int = 0
    details_fetched: int = 0
    comments_fetched: int = 0
    media_notes_downloaded: int = 0
    skipped_seen: int = 0
    retry_attempts: int = 0
    resumed_steps: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_counts": self.source_counts,
            "unique_notes": self.unique_notes,
            "details_fetched": self.details_fetched,
            "comments_fetched": self.comments_fetched,
            "media_notes_downloaded": self.media_notes_downloaded,
            "skipped_seen": self.skipped_seen,
            "retry_attempts": self.retry_attempts,
            "resumed_steps": self.resumed_steps,
            "errors": self.errors,
        }


def parse_json_document(output: str) -> Any:
    """Parse JSON even if a runtime warning was printed before it."""
    cleaned = ANSI_RE.sub("", output).strip()
    if not cleaned:
        raise ValueError("OpenCLI returned empty output")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(cleaned):
            if char not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(cleaned[index:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("OpenCLI output did not contain a JSON document")


def safe_error_text(value: Any) -> str:
    text = sanitize_text(ANSI_RE.sub("", str(value)))
    text = SENSITIVE_TEXT_RE.sub(r"\1=[redacted]", text)
    return " ".join(text.split())[:500] or "unknown error"


def empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "source": "opencli/xiaohongshu",
        "updated_at": "",
        "notes": {},
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError(f"unsupported sync state: {path}")
    notes = payload.get("notes")
    if not isinstance(notes, dict):
        raise ValueError(f"invalid sync state notes: {path}")
    return payload


def state_note_ids(state: dict[str, Any]) -> set[str]:
    notes = state.get("notes", {})
    return {
        str(note_id)
        for note_id, entry in notes.items()
        if isinstance(entry, dict) and entry.get("status") == "complete"
    }


def item_fingerprint(item: dict[str, Any]) -> str:
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def state_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in item.items()
        if not key.startswith("_")
    }


def checkpoint_state_note(
    state: dict[str, Any],
    item: dict[str, Any],
    step: str,
    error: str | None = None,
) -> None:
    notes = state.setdefault("notes", {})
    note_id = str(item["note_id"])
    entry = notes.get(note_id)
    if not isinstance(entry, dict):
        entry = {}
    completed_steps = {
        str(value)
        for value in entry.get("completed_steps", [])
        if isinstance(value, str)
    }
    if error is None:
        completed_steps.add(step)
    timestamp = datetime.now(timezone.utc).isoformat()
    entry.update(
        {
            "status": "partial",
            "source_types": listify(item.get("kind")),
            "completed_steps": sorted(completed_steps),
            "item": state_item(item),
            "content_hash": item_fingerprint(state_item(item)),
            "updated_at": timestamp,
        }
    )
    if error is None:
        last_error = entry.get("last_error")
        if isinstance(last_error, dict) and last_error.get("step") == step:
            entry.pop("last_error", None)
    else:
        entry["last_error"] = {
            "step": step,
            "error": safe_error_text(error),
            "at": timestamp,
        }
    notes[note_id] = entry
    state["updated_at"] = timestamp


def update_completed_state(
    state: dict[str, Any],
    items: list[dict[str, Any]],
    report: SyncReport,
    final_step: str,
) -> None:
    notes = state.setdefault("notes", {})
    failed_ids = {
        entry.get("note_id")
        for entry in report.errors
        if isinstance(entry, dict) and entry.get("note_id")
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    for item in items:
        note_id = str(item["note_id"])
        entry = notes.get(note_id)
        if not isinstance(entry, dict):
            entry = {}
        completed_steps = {
            str(value)
            for value in entry.get("completed_steps", [])
            if isinstance(value, str)
        }
        completed_steps.add(final_step)
        entry.update(
            {
                "status": "partial" if note_id in failed_ids else "complete",
                "source_types": listify(item.get("kind")),
                "completed_steps": sorted(completed_steps),
                "item": state_item(item),
                "content_hash": item_fingerprint(state_item(item)),
                "updated_at": timestamp,
            }
        )
        if note_id not in failed_ids:
            entry["last_success_at"] = timestamp
            entry.pop("last_error", None)
        notes[note_id] = entry
    state["updated_at"] = timestamp


def write_state(path: Path, state: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class OpenCliRunner:
    def __init__(self, executable: str = "opencli", timeout: float = 180) -> None:
        self.executable = executable
        self.timeout = timeout

    def run_json(self, *args: str) -> Any:
        command = [self.executable, "xiaohongshu", *args, "-f", "json"]
        environment = os.environ.copy()
        for key in (
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
        ):
            environment.pop(key, None)
        for key in ("NO_PROXY", "no_proxy"):
            existing = [part.strip() for part in environment.get(key, "").split(",") if part.strip()]
            environment[key] = ",".join(
                dict.fromkeys(["127.0.0.1", "localhost", "::1", *existing])
            )
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                env=environment,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise OpenCliError(f"OpenCLI executable not found: {self.executable}") from error
        except subprocess.TimeoutExpired as error:
            raise OpenCliError(f"OpenCLI timed out after {self.timeout:g}s") from error
        if completed.returncode != 0:
            detail = safe_error_text(completed.stderr or completed.stdout)
            raise OpenCliError(f"OpenCLI exited with {completed.returncode}: {detail}")
        try:
            return parse_json_document(completed.stdout)
        except ValueError as error:
            raise OpenCliError(str(error)) from error


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = []
        for key in ("items", "notes", "data", "results"):
            if isinstance(payload.get(key), list):
                values = payload[key]
                break
    else:
        values = []
    return [row for row in values if isinstance(row, dict)]


def field_rows_to_dict(payload: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for row in rows_from_payload(payload):
        field_name = str(row.get("field", "")).strip()
        if field_name:
            fields[field_name] = row.get("value", "")
    return fields


def logged_in(payload: Any) -> bool:
    if isinstance(payload, dict):
        value = payload.get("logged_in", payload.get("loggedIn"))
    else:
        value = field_rows_to_dict(payload).get("logged_in")
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def supports_public_note_command(raw_url: str) -> bool:
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return False
    return parts.hostname in {"www.xiaohongshu.com", "xiaohongshu.com", "xhslink.com"}


def normalize_list_item(source: str, raw: dict[str, Any]) -> dict[str, Any]:
    _, kind = SOURCE_COMMANDS[source]
    raw_url = str(raw.get("url", "") or "")
    item = {
        "note_id": str(raw.get("id", "") or ""),
        "url": sanitize_url(raw_url),
        "title": sanitize_text(raw.get("title", "")),
        "author": sanitize_text(raw.get("author", "")),
        "published_at": sanitize_text(raw.get("date", "")),
        "kind": kind,
        "likes": sanitize_text(raw.get("likes", "")),
        "collects": sanitize_text(raw.get("collects", "")),
        "comments_count": sanitize_text(raw.get("comments", "")),
        "views": sanitize_text(raw.get("views", "")),
        "tags": [],
        "comments": [],
        "media": [],
        "_raw_url": raw_url,
    }
    return item


def merge_source_item(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(previous)
    kinds: list[str] = []
    for value in (previous.get("kind"), current.get("kind")):
        for kind in listify(value):
            if kind not in kinds:
                kinds.append(kind)
    merged["kind"] = ", ".join(kinds)
    for key, value in current.items():
        if key in {"kind", "_raw_url"}:
            continue
        if key in {"tags", "comments", "media"}:
            if value:
                merged[key] = value
        elif value not in ("", None):
            merged[key] = value
    previous_url = str(previous.get("_raw_url", ""))
    current_url = str(current.get("_raw_url", ""))
    if supports_public_note_command(previous_url):
        merged["_raw_url"] = previous_url
    elif supports_public_note_command(current_url):
        merged["_raw_url"] = current_url
    else:
        merged["_raw_url"] = current_url or previous_url
    return merged


def apply_note_details(item: dict[str, Any], payload: Any) -> None:
    details = field_rows_to_dict(payload)
    aliases = {
        "title": "title",
        "author": "author",
        "content": "content",
        "likes": "likes",
        "collects": "collects",
        "comments": "comments_count",
    }
    for source_key, target_key in aliases.items():
        value = details.get(source_key)
        if value not in ("", None):
            item[target_key] = sanitize_text(value)
    if details.get("tags"):
        item["tags"] = listify(details["tags"])


def normalize_comments(payload: Any) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    last_root: dict[str, Any] | None = None
    for row in rows_from_payload(payload):
        content = sanitize_text(row.get("text", ""))
        if not content:
            continue
        comment = {
            "author": sanitize_text(row.get("author", "")),
            "content": content,
            "created_at": sanitize_text(row.get("time", "")),
            "likes": sanitize_text(row.get("likes", "")),
        }
        is_reply = row.get("is_reply") is True or str(row.get("is_reply", "")).lower() == "true"
        if is_reply and last_root is not None:
            last_root.setdefault("replies", []).append(comment)
            continue
        if is_reply and row.get("reply_to"):
            comment["content"] = (
                f"回复 {sanitize_text(row.get('reply_to'))}：{comment['content']}"
            )
        comment["replies"] = []
        roots.append(comment)
        last_root = comment
    return roots


def scan_downloaded_media(media_root: Path, note_id: str) -> list[dict[str, str]]:
    resolved_root = media_root.resolve()
    note_dir = (resolved_root / note_id).resolve()
    try:
        note_dir.relative_to(resolved_root)
    except ValueError:
        return []
    if not note_dir.is_dir():
        return []
    media: list[dict[str, str]] = []
    for path in sorted(note_dir.iterdir()):
        extension = path.suffix.lower()
        if path.is_file() and extension in MEDIA_EXTENSIONS:
            media.append(
                {
                    "type": "video" if extension in VIDEO_EXTENSIONS else "image",
                    "path": path.relative_to(resolved_root).as_posix(),
                }
            )
    return media


def checkpointed_media_exists(item: dict[str, Any], media_root: Path) -> bool:
    media = item.get("media")
    if not isinstance(media, list) or not media:
        return True
    resolved_root = media_root.resolve()
    for entry in media:
        if not isinstance(entry, dict):
            return False
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            return False
        candidate = (resolved_root / relative).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            return False
        if not candidate.is_file():
            return False
    return True


def vault_media_entries(
    vault: Path,
    folder_name: str,
    note_id: str,
) -> list[dict[str, str]]:
    resolved_vault = vault.expanduser().resolve()
    folder = (resolved_vault / folder_name).resolve()
    try:
        folder.relative_to(resolved_vault)
    except ValueError as error:
        raise ValueError("--folder must stay inside the vault") from error
    media_dir = (folder / "_media" / note_id).resolve()
    try:
        media_dir.relative_to(folder)
    except ValueError:
        return []
    if not media_dir.is_dir():
        return []
    entries: list[dict[str, str]] = []
    for path in sorted(media_dir.iterdir()):
        extension = path.suffix.lower()
        if path.is_file() and extension in MEDIA_EXTENSIONS:
            entries.append(
                {
                    "type": "video" if extension in VIDEO_EXTENSIONS else "image",
                    "vault_path": path.relative_to(resolved_vault).as_posix(),
                }
            )
    return entries


def hydrate_state_media_from_vault(
    state: dict[str, Any],
    vault: Path,
    folder_name: str,
) -> None:
    notes = state.get("notes", {})
    if not isinstance(notes, dict):
        return
    for note_id, entry in notes.items():
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        if not isinstance(item, dict):
            continue
        media = vault_media_entries(vault, folder_name, str(note_id))
        if media:
            item["media"] = media


def capture_vault_media(
    items: list[dict[str, Any]],
    vault: Path,
    folder_name: str,
) -> None:
    for item in items:
        media = vault_media_entries(vault, folder_name, str(item["note_id"]))
        if media:
            item["media"] = media


def sync_xiaohongshu(
    runner: OpenCliRunner,
    *,
    sources: list[str],
    limit: int,
    auth_check: bool = True,
    new_only: bool = False,
    seen_note_ids: set[str] | None = None,
    fetch_details: bool = True,
    fetch_comments: bool = False,
    comment_limit: int = 20,
    with_replies: bool = False,
    media_root: Path | None = None,
    interval: float = 2.5,
    retries: int = 2,
    retry_delay: float = 2,
    resume_state: dict[str, Any] | None = None,
    checkpoint: Callable[[dict[str, Any], str, str | None], None] | None = None,
) -> tuple[list[dict[str, Any]], SyncReport]:
    report = SyncReport()
    if auth_check and not logged_in(runner.run_json("whoami")):
        raise OpenCliError(
            "Xiaohongshu is not logged in. Log in through the Chrome session connected to OpenCLI."
        )
    deduplicated: dict[str, dict[str, Any]] = {}
    for source in sources:
        command, _ = SOURCE_COMMANDS[source]
        try:
            rows = rows_from_payload(runner.run_json(command, "--limit", str(limit)))
        except OpenCliError as error:
            report.errors.append(
                {"source": source, "step": "list", "error": safe_error_text(error)}
            )
            report.source_counts[source] = 0
            continue
        report.source_counts[source] = len(rows)
        for raw in rows:
            item = normalize_list_item(source, raw)
            note_id = item["note_id"]
            if not note_id:
                report.errors.append(
                    {"source": source, "step": "list", "error": "note without stable id skipped"}
                )
                continue
            if note_id in deduplicated:
                item = merge_source_item(deduplicated[note_id], item)
            deduplicated[note_id] = item

    if not deduplicated:
        details = "; ".join(
            f"{entry.get('source', 'unknown')}/{entry.get('step', 'unknown')}: "
            f"{entry.get('error', 'unknown error')}"
            for entry in report.errors
        )
        suffix = f" ({details})" if details else ""
        raise OpenCliError(f"OpenCLI returned no usable Xiaohongshu notes{suffix}")

    if new_only:
        seen_note_ids = seen_note_ids or set()
        for note_id in list(deduplicated):
            if note_id in seen_note_ids:
                report.skipped_seen += 1
                deduplicated.pop(note_id)
        if not deduplicated:
            report.unique_notes = 0
            return [], report

    def pause() -> None:
        if interval > 0:
            time.sleep(interval)

    def run_note_step(*args: str) -> Any:
        for attempt in range(retries + 1):
            try:
                return runner.run_json(*args)
            except OpenCliError:
                if attempt >= retries:
                    raise
                report.retry_attempts += 1
                if retry_delay > 0:
                    time.sleep(retry_delay)
        raise AssertionError("unreachable retry loop")

    resume_notes = (resume_state or {}).get("notes", {})
    for current_item in list(deduplicated.values()):
        item = current_item
        note_id = item["note_id"]
        prior_entry = resume_notes.get(note_id) if isinstance(resume_notes, dict) else None
        completed_steps: set[str] = set()
        if isinstance(prior_entry, dict):
            prior_item = prior_entry.get("item")
            if isinstance(prior_item, dict):
                item = merge_source_item(prior_item, item)
                deduplicated[note_id] = item
        if isinstance(prior_entry, dict) and prior_entry.get("status") == "partial":
            completed_steps = {
                str(value)
                for value in prior_entry.get("completed_steps", [])
                if isinstance(value, str)
            }
            if (
                media_root is not None
                and "media" in completed_steps
                and not checkpointed_media_exists(item, media_root)
            ):
                completed_steps.remove("media")
                item["media"] = []
        raw_url = str(item.get("_raw_url", ""))
        if not supports_public_note_command(raw_url):
            continue
        if fetch_details:
            if "details" in completed_steps:
                report.resumed_steps += 1
            else:
                try:
                    pause()
                    apply_note_details(item, run_note_step("note", raw_url))
                    report.details_fetched += 1
                    if checkpoint:
                        checkpoint(item, "details", None)
                except OpenCliError as error:
                    report.errors.append(
                        {
                            "note_id": note_id,
                            "step": "details",
                            "error": safe_error_text(error),
                        }
                    )
                    if checkpoint:
                        checkpoint(item, "details", str(error))
        if fetch_comments:
            args = ["comments", raw_url, "--limit", str(comment_limit)]
            if with_replies:
                args.extend(["--with-replies", "true"])
            if "comments" in completed_steps:
                report.resumed_steps += 1
            else:
                try:
                    pause()
                    item["comments"] = normalize_comments(run_note_step(*args))
                    report.comments_fetched += 1
                    if checkpoint:
                        checkpoint(item, "comments", None)
                except OpenCliError as error:
                    report.errors.append(
                        {
                            "note_id": note_id,
                            "step": "comments",
                            "error": safe_error_text(error),
                        }
                    )
                    if checkpoint:
                        checkpoint(item, "comments", str(error))
        if media_root is not None:
            if "media" in completed_steps:
                report.resumed_steps += 1
            else:
                try:
                    pause()
                    run_note_step("download", raw_url, "--output", str(media_root))
                    item["media"] = scan_downloaded_media(media_root, note_id)
                    report.media_notes_downloaded += 1
                    if checkpoint:
                        checkpoint(item, "media", None)
                except OpenCliError as error:
                    report.errors.append(
                        {
                            "note_id": note_id,
                            "step": "media",
                            "error": safe_error_text(error),
                        }
                    )
                    if checkpoint:
                        checkpoint(item, "media", str(error))

    report.unique_notes = len(deduplicated)
    for item in deduplicated.values():
        item.pop("_raw_url", None)
    return list(deduplicated.values()), report


def write_sanitized_export(
    output_path: Path,
    items: list[dict[str, Any]],
    report: SyncReport,
    sources: list[str],
    limit: int,
) -> None:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest": {
            "source": "opencli/xiaohongshu",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requested_sources": sources,
            "limit_per_source": limit,
            "completeness": "bounded; OpenCLI list commands expose a limit but no cursor",
            "report": report.as_dict(),
        },
        "items": items,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync authorized Xiaohongshu content through OpenCLI into Obsidian."
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=sorted(SOURCE_COMMANDS),
        help="Source to sync; repeat for multiple sources (default: saved)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows per source")
    parser.add_argument(
        "--skip-auth-check",
        action="store_true",
        help="Skip whoami after login was verified separately",
    )
    parser.add_argument("--skip-details", action="store_true", help="Skip full note body lookup")
    parser.add_argument("--new-only", action="store_true", help="Process only unseen note ids")
    parser.add_argument("--state-file", type=Path, help="Persistent sanitized sync state path")
    parser.add_argument("--retries", type=int, default=2, help="Retries after a note step fails")
    parser.add_argument("--retry-delay", type=float, default=2, help="Seconds before retrying")
    parser.add_argument("--comments", action="store_true", help="Fetch top-level comments")
    parser.add_argument("--comment-limit", type=int, default=20, help="Top-level comments per note")
    parser.add_argument("--with-replies", action="store_true", help="Include nested replies")
    parser.add_argument("--download-media", action="store_true", help="Download note images/videos")
    parser.add_argument("--media-output", type=Path, help="Persistent OpenCLI media output root")
    parser.add_argument("--vault", type=Path, help="Existing Obsidian vault root")
    parser.add_argument(
        "--folder",
        default="Sources/Xiaohongshu",
        help="Destination folder relative to the vault",
    )
    parser.add_argument("--output-json", type=Path, help="Write a sanitized reusable export")
    parser.add_argument("--dry-run", action="store_true", help="Preview vault changes")
    parser.add_argument("--interval", type=float, default=2.5, help="Seconds between note requests")
    parser.add_argument("--timeout", type=float, default=180, help="OpenCLI command timeout")
    parser.add_argument("--opencli", default="opencli", help="OpenCLI executable")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    sources = args.source or ["saved"]
    if not args.vault and not args.output_json:
        parser.error("provide --vault, --output-json, or both")
    if args.dry_run and not args.vault:
        parser.error("--dry-run requires --vault")
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if not 1 <= args.comment_limit <= 50:
        parser.error("--comment-limit must be between 1 and 50")
    if args.interval < 0:
        parser.error("--interval cannot be negative")
    if args.retries < 0:
        parser.error("--retries cannot be negative")
    if args.retry_delay < 0:
        parser.error("--retry-delay cannot be negative")
    if args.with_replies and not args.comments:
        parser.error("--with-replies requires --comments")
    if args.media_output and not args.download_media:
        parser.error("--media-output requires --download-media")
    if args.download_media and args.output_json and not args.media_output:
        parser.error("--output-json with --download-media requires persistent --media-output")

    temporary_media: tempfile.TemporaryDirectory[str] | None = None
    media_root: Path | None = None
    try:
        if args.state_file:
            state_path = args.state_file.expanduser().resolve()
        elif args.vault:
            state_path = args.vault.expanduser().resolve() / ".xhs-sync" / "state.json"
        else:
            state_path = args.output_json.expanduser().resolve().with_name(".xhs-sync-state.json")
        state = load_state(state_path)
        if args.vault:
            hydrate_state_media_from_vault(state, args.vault, args.folder)

        checkpoint_writer: Callable[[dict[str, Any], str, str | None], None] | None = None
        if not args.dry_run:
            def persist_checkpoint(
                item: dict[str, Any],
                step: str,
                error: str | None,
            ) -> None:
                checkpoint_state_note(state, item, step, error)
                write_state(state_path, state)

            checkpoint_writer = persist_checkpoint

        if args.download_media:
            if args.media_output:
                media_root = args.media_output.expanduser().resolve()
                media_root.mkdir(parents=True, exist_ok=True)
            else:
                temporary_media = tempfile.TemporaryDirectory(prefix="xhs-opencli-")
                media_root = Path(temporary_media.name).resolve()

        items, report = sync_xiaohongshu(
            OpenCliRunner(args.opencli, args.timeout),
            sources=sources,
            limit=args.limit,
            auth_check=not args.skip_auth_check,
            new_only=args.new_only,
            seen_note_ids=state_note_ids(state),
            fetch_details=not args.skip_details,
            fetch_comments=args.comments,
            comment_limit=args.comment_limit,
            with_replies=args.with_replies,
            media_root=media_root,
            interval=args.interval,
            retries=args.retries,
            retry_delay=args.retry_delay,
            resume_state=state,
            checkpoint=checkpoint_writer,
        )
        if args.output_json:
            write_sanitized_export(args.output_json, items, report, sources, args.limit)

        result: dict[str, Any] = {"sync": report.as_dict()}
        if args.output_json:
            result["output_json"] = str(args.output_json.expanduser().resolve())
        if args.vault:
            imported = (
                import_items(
                    items,
                    args.vault,
                    args.folder,
                    media_root=media_root,
                    dry_run=args.dry_run,
                )
                if items
                else ImportStats()
            )
            result["import"] = imported.as_dict()
            if not args.dry_run and items:
                capture_vault_media(items, args.vault, args.folder)
        result["state"] = {"path": str(state_path), "written": not args.dry_run}
        if not args.dry_run:
            update_completed_state(
                state,
                items,
                report,
                "import" if args.vault else "export",
            )
            write_state(state_path, state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, OpenCliError, json.JSONDecodeError) as error:
        print(json.dumps({"error": safe_error_text(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if temporary_media is not None:
            temporary_media.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
