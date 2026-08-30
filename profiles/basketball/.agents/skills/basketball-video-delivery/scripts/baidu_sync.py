#!/usr/bin/env python3
"""Safely upload explicit, verified basketball deliverables to Baidu Netdisk."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath


UPLOAD_FAILURE_MARKERS = ("以下文件上传失败", "上传文件失败", "上传失败")
INVALID_REMOTE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f\ufe0f\U00010000-\U0010ffff]')


class RemoteVerificationNeedsAttention(RuntimeError):
    pass


def run(
    args: list[str], *, failure_markers: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    matched_marker = next((marker for marker in failure_markers if marker in output), None)
    if result.returncode or matched_marker:
        detail = (result.stderr or result.stdout).strip()
        reason = f"exit {result.returncode}" if result.returncode else f"reported failure: {matched_marker}"
        raise RuntimeError(f"command failed ({reason}): {shlex.join(args[:2])}\n{detail}")
    return result


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size",
        "-show_entries", "stream=codec_name,codec_type,width,height", "-of", "json", str(path),
    ])
    data = json.loads(result.stdout)
    if not data.get("streams") or float(data["format"]["duration"]) <= 0:
        raise ValueError(f"invalid media: {path}")
    return data


def remote_join(root: str, name: str) -> str:
    return str(PurePosixPath("/") / root.lstrip("/") / name)


def safe_remote_name(name: str) -> str:
    """Return a Baidu-compatible basename without changing the local source."""
    sanitized = INVALID_REMOTE_CHARS.sub("_", name).rstrip(" .")
    if sanitized in ("", ".", ".."):
        raise ValueError(f"filename becomes empty after remote sanitization: {name!r}")
    return sanitized


def ensure_unique_remote_names(items: list[dict], target: str) -> None:
    remote_names = [str(item["remote_name"]) for item in items]
    collisions = sorted({name for name in remote_names if remote_names.count(name) > 1})
    if collisions:
        raise ValueError(f"remote filename collision in {target}: {collisions}")


def ensure_unique_remote_paths(items: list[dict]) -> None:
    paths = [str(item["remote"]) for item in items]
    collisions = sorted({path for path in paths if paths.count(path) > 1})
    if collisions:
        raise ValueError(f"remote path collision across categories: {collisions}")


def mp4_files(directory: Path | None) -> list[Path]:
    if directory is None:
        return []
    return sorted(p.resolve() for p in directory.glob("*.mp4") if not p.name.startswith("."))


def local_fingerprint(path: Path) -> str:
    size = path.stat().st_size
    digest = hashlib.sha256(str(size).encode("ascii"))
    with path.open("rb") as handle:
        if size <= 3 * 1024 * 1024:
            digest.update(handle.read())
        else:
            for offset in (0, max(0, size // 2 - 512 * 1024), max(0, size - 1024 * 1024)):
                handle.seek(offset)
                digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()


def save_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def meta_matches_item(text: str, item: dict) -> bool:
    path_present = item["remote"] in text or item["remote_name"] in text
    size_present = re.search(rf"(?<!\d){int(item['bytes'])}(?!\d)", text) is not None
    return path_present and size_present


def verify_remote_item(
    cli: str,
    item: dict,
    *,
    attempts: int,
    interval_seconds: float,
    runner=run,
    sleeper=time.sleep,
) -> int:
    last_detail = ""
    for attempt in range(1, max(1, attempts) + 1):
        try:
            meta = runner([cli, "meta", item["remote"]]).stdout
            if meta_matches_item(meta, item):
                return attempt
            last_detail = meta.strip()[-500:]
        except RuntimeError as exc:
            last_detail = str(exc)[-500:]
        if attempt < attempts:
            sleeper(max(0.0, interval_seconds))
    raise RemoteVerificationNeedsAttention(
        f"remote metadata not indexed or byte size not confirmed after {attempts} attempts: "
        f"{item['remote_name']} ({last_detail})"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--pure", type=Path)
    parser.add_argument("--personal-dir", type=Path)
    parser.add_argument("--events-dir", type=Path)
    parser.add_argument("--team-highlight", type=Path, action="append", default=[])
    parser.add_argument("--game-highlight", type=Path, action="append", default=[])
    parser.add_argument("--highlight", type=Path, action="append", default=[])
    parser.add_argument(
        "--attachment",
        type=Path,
        action="append",
        default=[],
        help="Explicit non-video file uploaded to the match root (for example commentary MD/HTML/PNG).",
    )
    parser.add_argument("--cli", default=str(Path.home() / ".local/bin/BaiduPCS-Go"))
    parser.add_argument("--policy", choices=["skip", "rsync", "overwrite"], default="skip")
    parser.add_argument("--settle-seconds", type=int, default=60)
    parser.add_argument("--verify-attempts", type=int, default=12)
    parser.add_argument("--verify-interval-seconds", type=float, default=10)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cli = shutil.which(args.cli) or (args.cli if Path(args.cli).is_file() else None)
    if not cli:
        raise SystemExit(f"BaiduPCS-Go not found: {args.cli}")

    groups: list[tuple[str, str, list[Path]]] = []
    if args.pure:
        groups.append(("pure", args.target, [args.pure.resolve()]))
    personal = mp4_files(args.personal_dir)
    events = mp4_files(args.events_dir)
    team_highlights = [path.resolve() for path in args.team_highlight]
    game_highlights = [path.resolve() for path in [*args.game_highlight, *args.highlight]]
    attachments = [path.resolve() for path in args.attachment]
    if personal:
        groups.append(("personal", remote_join(args.target, "个人精彩集锦"), personal))
    if events:
        groups.append(("events", remote_join(args.target, "个人精彩片段"), events))
    if team_highlights:
        groups.append(("team_highlights", remote_join(args.target, "球队精彩集锦"), team_highlights))
    if game_highlights:
        groups.append(("game_highlights", remote_join(args.target, "比赛精彩集锦"), game_highlights))
    if attachments:
        groups.append(("attachments", args.target, attachments))
    if not groups:
        raise SystemExit("no deliverables selected")

    files = [path for _, _, paths in groups for path in paths]
    for path in files:
        if not path.is_file():
            raise SystemExit(f"missing deliverable: {path}")
        if args.settle_seconds > 0 and time.time() - path.stat().st_mtime < args.settle_seconds:
            raise SystemExit(f"file may still be changing: {path}")

    media = {
        str(path): probe(path)
        for path in files
        if path.suffix.lower() == ".mp4"
    }
    items = [
        {
            "category": category,
            "local": str(path),
            "name": path.name,
            "remote_name": safe_remote_name(path.name),
            "bytes": (
                int(media[str(path)]["format"]["size"])
                if str(path) in media
                else path.stat().st_size
            ),
            "local_fingerprint": local_fingerprint(path),
            "remote": remote_join(target, safe_remote_name(path.name)),
            "status": "planned",
        }
        for category, target, paths in groups
        for path in paths
    ]
    previous: dict[str, dict] = {}
    if args.execute and args.report and args.report.is_file():
        try:
            old = json.loads(args.report.read_text(encoding="utf-8"))
            previous = {
                f"{item.get('remote')}|{item.get('bytes')}|{item.get('local_fingerprint')}": item
                for item in old.get("items") or []
                if item.get("status") == "verified"
            }
        except (OSError, json.JSONDecodeError):
            previous = {}
    for item in items:
        if f"{item['remote']}|{item['bytes']}|{item['local_fingerprint']}" in previous:
            item["status"] = "verified"
            item["resumed_from_report"] = True
    for category, target, _ in groups:
        selected = [item for item in items if item["category"] == category]
        ensure_unique_remote_names(selected, target)
    ensure_unique_remote_paths(items)
    plan = {
        "status": "running" if args.execute else "planned",
        "mode": "execute" if args.execute else "dry-run",
        "target": args.target,
        "policy": args.policy,
        "local_bytes": sum(item["bytes"] for item in items),
        "remote_renamed_count": sum(item["name"] != item["remote_name"] for item in items),
        "counts": {category: len(paths) for category, _, paths in groups},
        "items": items,
    }
    save_report(args.report, plan)

    if args.execute:
        who = run([cli, "who"])
        if "uid: 0" in who.stdout or "用户名: ," in who.stdout:
            raise SystemExit("BaiduPCS-Go is not logged in")
        stage_parent = args.report.resolve().parent if args.report else Path.cwd()
        stage_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".baidu-upload-", dir=stage_parent) as temporary:
            staging_root = Path(temporary)
            for group_index, (category, target, paths) in enumerate(groups):
                selected = [item for item in items if item["category"] == category]
                pending = [item for item in selected if item["status"] != "verified"]
                if not pending:
                    continue
                staging_dir = staging_root / f"{group_index:02d}-{category}"
                staging_dir.mkdir()
                upload_paths: list[Path] = []
                pending_by_local = {item["local"]: item for item in pending}
                for path in paths:
                    item = pending_by_local.get(str(path))
                    if item is None:
                        continue
                    staged = staging_dir / item["remote_name"]
                    try:
                        os.link(path, staged)
                    except OSError as exc:
                        raise RuntimeError(
                            f"cannot stage remote-safe filename for {path}; "
                            "place the report on the same filesystem as the deliverables"
                        ) from exc
                    upload_paths.append(staged)
                run(
                    [cli, "upload", *map(str, upload_paths), target, "--policy", args.policy],
                    failure_markers=UPLOAD_FAILURE_MARKERS,
                )
                for item in pending:
                    item["status"] = "uploaded_waiting_for_index"
                    save_report(args.report, plan)
                    item["verification_attempts"] = verify_remote_item(
                        cli, item,
                        attempts=args.verify_attempts,
                        interval_seconds=args.verify_interval_seconds,
                    )
                    item["status"] = "verified"
                    save_report(args.report, plan)
        plan["status"] = "complete"
        plan["remote_bytes_verified"] = plan["local_bytes"]
        save_report(args.report, plan)

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def write_failure_report(error: BaseException) -> None:
    if "--report" not in sys.argv:
        return
    index = sys.argv.index("--report")
    if index + 1 >= len(sys.argv):
        return
    report = Path(sys.argv[index + 1])
    try:
        payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    needs_attention = isinstance(error, RemoteVerificationNeedsAttention)
    payload.update({
        "status": "needs_attention" if needs_attention else "failed",
        "phase": "remote_verification" if needs_attention else payload.get("phase"),
        "error": str(error),
        "resume_command": shlex.join([sys.executable, *sys.argv]),
        "auto_shutdown_allowed": False if needs_attention else payload.get("auto_shutdown_allowed"),
    })
    save_report(report, payload)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        if exc.code not in (None, 0):
            write_failure_report(exc)
        raise
    except Exception as exc:
        write_failure_report(exc)
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
