#!/usr/bin/env python3
"""Incrementally import user-owned Xiaohongshu exports into an Obsidian vault."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


MANAGED_START = "<!-- xhs-sync:start -->"
MANAGED_END = "<!-- xhs-sync:end -->"
MANAGED_FRONTMATTER_KEYS = {
    "xhs_id",
    "xhs_source",
    "xhs_author",
    "xhs_author_id",
    "xhs_published_at",
    "xhs_collected_at",
    "xhs_kind",
    "xhs_collections",
    "xhs_tags",
    "xhs_likes",
    "xhs_collects",
    "xhs_comments_count",
    "xhs_views",
}
SECRET_QUERY_RE = re.compile(
    r"(?:^|_)(?:access_?token|token|xsec_?token|sign|signature|auth|authorization|"
    r"cookie|session|key|secret)(?:$|_)",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>()\]\"']+")
MEDIA_EXTENSIONS = {
    ".avif",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".webm",
    ".webp",
    ".wav",
}
VIDEO_EXTENSIONS = {".m4a", ".mov", ".mp3", ".mp4", ".webm", ".wav"}


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    media_copied: int = 0
    media_unchanged: int = 0
    remote_media: int = 0
    missing_media: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    planned: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "duplicates": self.duplicates,
            "media_copied": self.media_copied,
            "media_unchanged": self.media_unchanged,
            "remote_media": self.remote_media,
            "missing_media": self.missing_media,
            "skipped": self.skipped,
            "planned": self.planned,
        }


def first_value(item: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return default


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def listify(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [part.strip().lstrip("#") for part in re.split(r"[,，;；\n]", value) if part.strip()]
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, list):
        value = [value]
    result: list[str] = []
    for entry in value:
        if isinstance(entry, dict):
            text = stringify(first_value(entry, "name", "title", "tag", "label"))
        else:
            text = stringify(entry)
        if text and text not in result:
            result.append(text.lstrip("#"))
    return result


def sanitize_url(url: Any) -> str:
    text = stringify(url)
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return ""
    host = parts.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        netloc = f"{host}:{parts.port}" if parts.port else host
    except ValueError:
        return ""
    safe_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not SECRET_QUERY_RE.search(key)
    ]
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(safe_query), ""))


def sanitize_text(text: Any) -> str:
    value = stringify(text)
    return URL_RE.sub(lambda match: sanitize_url(match.group(0)) or "[redacted-url]", value)


def author_fields(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        return (
            sanitize_text(first_value(value, "name", "nickname", "nick_name", "username")),
            sanitize_text(first_value(value, "id", "user_id", "userId")),
        )
    return sanitize_text(value), ""


def truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return stringify(value).lower() in {"1", "true", "yes", "y"}


def infer_kind(raw: dict[str, Any]) -> str:
    explicit = sanitize_text(first_value(raw, "kind", "type", "source_type"))
    if explicit:
        return explicit
    kinds: list[str] = []
    flag_groups = (
        ("favorite", ("favorite", "favorited", "is_favorite", "is_collected")),
        ("liked", ("liked", "is_liked")),
        ("authored", ("authored", "is_authored", "is_self", "own_post")),
    )
    for label, keys in flag_groups:
        if any(truthy_flag(raw.get(key)) for key in keys):
            kinds.append(label)
    return ", ".join(kinds)


def filename_part(value: str, fallback: str = "untitled", limit: int = 80) -> str:
    cleaned = re.sub(r"[\x00-\x1f<>:\"/\\|?*#^\[\]]+", "-", value).strip(" .-_")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:limit].rstrip() or fallback)


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def canonical_item(raw: dict[str, Any]) -> dict[str, Any]:
    author, author_id = author_fields(first_value(raw, "author", "user", "creator", "nickname"))
    title = sanitize_text(first_value(raw, "title", "name", "note_title", default="未命名笔记"))
    content = sanitize_text(first_value(raw, "content", "desc", "description", "text", "note_text"))
    source = sanitize_url(first_value(raw, "url", "link", "share_url", "note_url"))
    stable_id = sanitize_text(first_value(raw, "note_id", "noteId", "id"))
    if not stable_id:
        identity = "\n".join((source, title, author))
        stable_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    stable_id = filename_part(stable_id, fallback="unknown", limit=64)

    media_values: list[Any] = []
    for key in ("media", "images", "image_list", "pictures", "videos", "video"):
        value = raw.get(key)
        if value is None:
            continue
        media_values.extend(value if isinstance(value, list) else [value])

    return {
        "id": stable_id,
        "title": title or "未命名笔记",
        "content": content,
        "source": source,
        "author": author,
        "author_id": author_id,
        "published_at": sanitize_text(
            first_value(raw, "published_at", "publish_time", "created_at", "time")
        ),
        "collected_at": sanitize_text(
            first_value(raw, "collected_at", "favorite_time", "saved_at")
        ),
        "kind": infer_kind(raw),
        "collections": listify(
            first_value(raw, "collections", "albums", "folders", "categories", "category", default=[])
        ),
        "tags": listify(first_value(raw, "tags", "topics", "hashtags", default=[])),
        "likes": sanitize_text(first_value(raw, "likes", "like_count")),
        "collects": sanitize_text(
            first_value(raw, "collects", "favorites_count", "favorite_count", "collect_count")
        ),
        "comments_count": sanitize_text(
            first_value(raw, "comments_count", "comment_count")
        ),
        "views": sanitize_text(first_value(raw, "views", "view_count", "read_count")),
        "media": media_values,
        "transcript": sanitize_text(
            first_value(raw, "transcript", "transcription", "video_text")
        ),
        "comments": first_value(raw, "comments", "comment_list", default=[]),
    }


def merge_canonical_items(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Prefer the later non-empty scalar while retaining richer list fields."""
    merged = dict(previous)
    for key, value in current.items():
        if key in {"media", "comments", "collections", "tags"}:
            if value:
                existing = merged.get(key)
                if not isinstance(existing, list):
                    existing = []
                combined: list[Any] = []
                seen: set[str] = set()
                for entry in [*existing, *value]:
                    signature = json.dumps(entry, ensure_ascii=False, sort_keys=True)
                    if signature not in seen:
                        seen.add(signature)
                        combined.append(entry)
                merged[key] = combined
        elif key == "kind" and value:
            kinds = listify([*listify(merged.get(key)), *listify(value)])
            merged[key] = ", ".join(kinds)
        elif value not in ("", None):
            merged[key] = value
    return merged


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = []
        for key in ("items", "notes", "data", "favorites", "results"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                values = candidate
                break
        if not values and any(key in payload for key in ("note_id", "noteId", "id", "url", "title")):
            values = [payload]
    else:
        values = []
    return [entry for entry in values if isinstance(entry, dict)]


def normalize_media(entry: Any) -> tuple[str, str]:
    if isinstance(entry, str):
        value = entry
        media_type = ""
    elif isinstance(entry, dict):
        value = stringify(first_value(entry, "path", "local_path", "file", "url", "src"))
        media_type = stringify(first_value(entry, "type", "media_type"))
    else:
        return "", ""
    return value, media_type


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_equal(left: Path, right: Path) -> bool:
    return left.stat().st_size == right.stat().st_size and file_digest(left) == file_digest(right)


def resolve_local_media(value: str, input_dir: Path, media_root: Path | None) -> Path | None:
    candidate = Path(value).expanduser()
    roots = [root.resolve() for root in (media_root, input_dir) if root is not None]
    for root in roots:
        path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            return path
    return None


def ensure_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} resolves outside the allowed root: {path}") from error
    return resolved


def render_media(
    note: dict[str, Any],
    *,
    vault: Path,
    folder: Path,
    input_dir: Path,
    media_root: Path | None,
    dry_run: bool,
    stats: ImportStats,
) -> list[str]:
    lines: list[str] = []
    destination_dir = folder / "_media" / note["id"]
    used_names: set[str] = set()

    for index, entry in enumerate(note["media"], start=1):
        if isinstance(entry, dict) and stringify(entry.get("vault_path")):
            relative_path = Path(stringify(entry["vault_path"]))
            if relative_path.is_absolute():
                raise ValueError("vault media path must be relative to the vault")
            target = ensure_inside(vault / relative_path, vault, "vault media")
            extension = target.suffix.lower()
            if extension and extension not in MEDIA_EXTENSIONS:
                stats.skipped.append(f"unsupported media: {target.name}")
                continue
            if not target.is_file():
                stats.missing_media.append(relative_path.as_posix())
                lines.append(f"- 缺失 Vault 媒体：`{target.name}`")
                continue
            stats.media_unchanged += 1
            prefix = "视频/音频" if extension in VIDEO_EXTENSIONS else "图片"
            lines.append(f"- {prefix}：![[{target.relative_to(vault).as_posix()}]]")
            continue

        value, declared_type = normalize_media(entry)
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            safe_url = sanitize_url(value)
            if not safe_url:
                continue
            stats.remote_media += 1
            label = "远程视频" if declared_type.lower() in {"video", "audio"} else "远程媒体"
            lines.append(f"- [{label} {index}]({safe_url})")
            continue

        source = resolve_local_media(value, input_dir, media_root)
        if source is None:
            stats.missing_media.append(value)
            lines.append(f"- 缺失本地媒体：`{Path(value).name}`")
            continue

        extension = source.suffix.lower()
        if extension and extension not in MEDIA_EXTENSIONS:
            stats.skipped.append(f"unsupported media: {source.name}")
            continue
        base_name = filename_part(source.stem, fallback=f"media-{index}", limit=60)
        target_name = f"{index:02d}-{base_name}{extension}"
        while target_name in used_names:
            target_name = f"{index:02d}-{base_name}-{len(used_names) + 1}{extension}"
        used_names.add(target_name)
        target = destination_dir / target_name
        ensure_inside(target, vault, "media destination")
        relative = target.relative_to(vault).as_posix()

        if target.is_file() and files_equal(source, target):
            stats.media_unchanged += 1
        else:
            if not dry_run:
                destination_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            stats.media_copied += 1
        prefix = "视频/音频" if extension in VIDEO_EXTENSIONS else "图片"
        lines.append(f"- {prefix}：![[{relative}]]")
    return lines


def render_comment(comment: Any, depth: int = 0) -> list[str]:
    if not isinstance(comment, dict):
        text = sanitize_text(comment)
        return [f"{'  ' * depth}- {text}"] if text else []
    author, _ = author_fields(first_value(comment, "author", "user", "nickname"))
    content = sanitize_text(first_value(comment, "content", "text", "comment"))
    created_at = sanitize_text(first_value(comment, "created_at", "time", "date"))
    if not content:
        return []
    meta = " · ".join(part for part in (author, created_at) if part)
    line = f"{'  ' * depth}- "
    if meta:
        line += f"**{meta}**："
    line += content.replace("\n", "  \n" + "  " * depth)
    lines = [line]
    replies = first_value(comment, "replies", "children", "sub_comments", default=[])
    if isinstance(replies, list):
        for reply in replies:
            lines.extend(render_comment(reply, depth + 1))
    return lines


def render_managed_block(
    note: dict[str, Any],
    media_lines: list[str],
) -> str:
    lines = [
        MANAGED_START,
        "> [!info] 同步内容",
        "> 本区块由 `xiaohongshu-obsidian` 管理；请把人工整理写在区块外。",
        "",
        "## 来源内容",
    ]
    if note["source"]:
        lines.append(f"- 原文：[{note['title']}]({note['source']})")
    if note["author"]:
        lines.append(f"- 作者：{note['author']}")
    if note["published_at"]:
        lines.append(f"- 发布时间：{note['published_at']}")
    if note["collected_at"]:
        lines.append(f"- 收藏时间：{note['collected_at']}")
    if note["kind"]:
        lines.append(f"- 来源类型：{note['kind']}")
    if note["collections"]:
        lines.append(f"- 原收藏分类：{', '.join(note['collections'])}")
    if note["tags"]:
        lines.append(f"- 原话题标签：{', '.join('#' + tag for tag in note['tags'])}")
    engagement = [
        f"点赞 {note['likes']}" if note["likes"] else "",
        f"收藏 {note['collects']}" if note["collects"] else "",
        f"评论 {note['comments_count']}" if note["comments_count"] else "",
        f"浏览 {note['views']}" if note["views"] else "",
    ]
    engagement = [value for value in engagement if value]
    if engagement:
        lines.append(f"- 同步时互动数据：{' · '.join(engagement)}")
    if note["content"]:
        lines.extend(("", "### 正文", "", note["content"]))
    if media_lines:
        lines.extend(("", "### 媒体", "", *media_lines))
    if note["transcript"]:
        lines.extend(("", "### 视频转写", "", note["transcript"]))

    comment_lines: list[str] = []
    comments = note["comments"]
    if isinstance(comments, list):
        for comment in comments:
            comment_lines.extend(render_comment(comment))
    if comment_lines:
        lines.extend(("", "### 评论与回复", "", *comment_lines))
    lines.extend(("", MANAGED_END))
    return "\n".join(lines)


def managed_frontmatter(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "xhs_id": note["id"],
        "xhs_source": note["source"],
        "xhs_author": note["author"],
        "xhs_author_id": note["author_id"],
        "xhs_published_at": note["published_at"],
        "xhs_collected_at": note["collected_at"],
        "xhs_kind": note["kind"],
        "xhs_collections": note["collections"],
        "xhs_tags": note["tags"],
        "xhs_likes": note["likes"],
        "xhs_collects": note["collects"],
        "xhs_comments_count": note["comments_count"],
        "xhs_views": note["views"],
    }


def merge_frontmatter(existing: str, note: dict[str, Any]) -> tuple[str, str]:
    preserved: list[str] = []
    body = existing
    if existing.startswith("---\n"):
        end = existing.find("\n---\n", 4)
        if end != -1:
            raw_lines = existing[4:end].splitlines()
            preserved = [
                line
                for line in raw_lines
                if line.split(":", 1)[0].strip() not in MANAGED_FRONTMATTER_KEYS
            ]
            body = existing[end + 5 :]
    generated = [f"{key}: {yaml_scalar(value)}" for key, value in managed_frontmatter(note).items()]
    frontmatter = "---\n" + "\n".join([*preserved, *generated]) + "\n---\n"
    return frontmatter, body


def replace_managed_block(body: str, managed: str) -> str:
    start = body.find(MANAGED_START)
    end = body.find(MANAGED_END)
    if start != -1 and end != -1 and end >= start:
        end += len(MANAGED_END)
        prefix = body[:start].rstrip()
        before = prefix + "\n\n" if prefix else ""
        return before + managed + "\n\n" + body[end:].lstrip()
    manual = body.strip()
    suffix = manual if manual else "## 我的整理\n\n在这里继续补充摘要、双链、事实核验和行动项。"
    return managed + "\n\n" + suffix + "\n"


def find_note_path(folder: Path, note: dict[str, Any]) -> Path:
    suffix = f"--{note['id']}.md"
    if folder.is_dir():
        for candidate in folder.glob("*.md"):
            if candidate.name.endswith(suffix):
                return candidate
    title = filename_part(note["title"])
    return folder / f"{title}{suffix}"


def import_items(
    raw_items: list[dict[str, Any]],
    vault: Path,
    folder_name: str,
    *,
    input_dir: Path | None = None,
    media_root: Path | None = None,
    dry_run: bool = False,
) -> ImportStats:
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"vault does not exist: {vault}")
    folder = (vault / folder_name).resolve()
    try:
        folder.relative_to(vault)
    except ValueError as error:
        raise ValueError("--folder must stay inside the vault") from error
    if media_root is not None:
        media_root = media_root.expanduser().resolve()
        if not media_root.is_dir():
            raise ValueError(f"media root does not exist: {media_root}")
    if not raw_items:
        raise ValueError("no note objects found in the JSON export")
    input_dir = (input_dir or Path.cwd()).expanduser().resolve()

    stats = ImportStats()
    deduplicated: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        note = canonical_item(raw)
        if note["id"] in deduplicated:
            stats.duplicates += 1
            note = merge_canonical_items(deduplicated[note["id"]], note)
        deduplicated[note["id"]] = note

    for note in deduplicated.values():
        target = find_note_path(folder, note)
        ensure_inside(target, vault, "note destination")
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        media_lines = render_media(
            note,
            vault=vault,
            folder=folder,
            input_dir=input_dir,
            media_root=media_root,
            dry_run=dry_run,
            stats=stats,
        )
        frontmatter, body = merge_frontmatter(existing, note)
        rendered = frontmatter + replace_managed_block(body, render_managed_block(note, media_lines))
        if existing == rendered:
            action = "unchanged"
            stats.unchanged += 1
        elif existing:
            action = "update"
            stats.updated += 1
        else:
            action = "create"
            stats.created += 1
        stats.planned.append({"action": action, "path": str(target)})
        if not dry_run and existing != rendered:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
    return stats


def import_export(
    input_path: Path,
    vault: Path,
    folder_name: str,
    *,
    media_root: Path | None = None,
    dry_run: bool = False,
) -> ImportStats:
    if str(input_path) == "-":
        payload = json.load(sys.stdin)
        input_dir = Path.cwd().resolve()
    else:
        input_path = input_path.expanduser().resolve()
        if not input_path.is_file():
            raise ValueError(f"input JSON does not exist: {input_path}")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        input_dir = input_path.parent
    return import_items(
        extract_items(payload),
        vault,
        folder_name,
        input_dir=input_dir,
        media_root=media_root,
        dry_run=dry_run,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Incrementally import a Xiaohongshu JSON export into an Obsidian vault."
    )
    parser.add_argument("input", type=Path, help="Path to the JSON export, or - for stdin")
    parser.add_argument("--vault", required=True, type=Path, help="Existing Obsidian vault root")
    parser.add_argument(
        "--folder",
        default="Sources/Xiaohongshu",
        help="Destination folder relative to the vault (default: Sources/Xiaohongshu)",
    )
    parser.add_argument("--media-root", type=Path, help="Root for relative local media paths")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        stats = import_export(
            args.input,
            args.vault,
            args.folder,
            media_root=args.media_root,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(stats.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
