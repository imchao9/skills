#!/usr/bin/env python3
"""Safely upload explicit, verified basketball deliverables to Baidu Netdisk."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]} {args[1]}\n{detail}")
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


def mp4_files(directory: Path | None) -> list[Path]:
    if directory is None:
        return []
    return sorted(p.resolve() for p in directory.glob("*.mp4") if not p.name.startswith("."))


def save_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--pure", type=Path)
    parser.add_argument("--personal-dir", type=Path)
    parser.add_argument("--events-dir", type=Path)
    parser.add_argument("--team-highlight", type=Path, action="append", default=[])
    parser.add_argument("--game-highlight", type=Path, action="append", default=[])
    parser.add_argument("--highlight", type=Path, action="append", default=[])
    parser.add_argument("--cli", default=str(Path.home() / ".local/bin/BaiduPCS-Go"))
    parser.add_argument("--policy", choices=["skip", "rsync", "overwrite"], default="skip")
    parser.add_argument("--settle-seconds", type=int, default=60)
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
    if personal:
        groups.append(("personal", remote_join(args.target, "个人精彩集锦"), personal))
    if events:
        groups.append(("events", remote_join(args.target, "个人精彩片段"), events))
    if team_highlights:
        groups.append(("team_highlights", remote_join(args.target, "球队精彩集锦"), team_highlights))
    if game_highlights:
        groups.append(("game_highlights", remote_join(args.target, "比赛精彩集锦"), game_highlights))
    if not groups:
        raise SystemExit("no deliverables selected")

    files = [path for _, _, paths in groups for path in paths]
    for path in files:
        if not path.is_file():
            raise SystemExit(f"missing deliverable: {path}")
        if args.settle_seconds > 0 and time.time() - path.stat().st_mtime < args.settle_seconds:
            raise SystemExit(f"file may still be changing: {path}")

    media = {str(path): probe(path) for path in files}
    items = [
        {
            "category": category,
            "local": str(path),
            "name": path.name,
            "bytes": int(media[str(path)]["format"]["size"]),
            "remote": remote_join(target, path.name),
            "status": "planned",
        }
        for category, target, paths in groups
        for path in paths
    ]
    plan = {
        "status": "running" if args.execute else "planned",
        "mode": "execute" if args.execute else "dry-run",
        "target": args.target,
        "policy": args.policy,
        "local_bytes": sum(item["bytes"] for item in items),
        "counts": {category: len(paths) for category, _, paths in groups},
        "items": items,
    }
    save_report(args.report, plan)

    if args.execute:
        who = run([cli, "who"])
        if "uid: 0" in who.stdout or "用户名: ," in who.stdout:
            raise SystemExit("BaiduPCS-Go is not logged in")
        for category, target, paths in groups:
            run([cli, "upload", *map(str, paths), target, "--policy", args.policy])
            selected = [item for item in items if item["category"] == category]
            meta = run([cli, "meta", *[item["remote"] for item in selected]]).stdout
            mismatches = [
                item["name"]
                for item in selected
                if item["remote"] not in meta or str(item["bytes"]) not in meta
            ]
            if mismatches:
                raise RuntimeError(f"remote verification failed for {category}: {mismatches}")
            for item in selected:
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
    payload.update({
        "status": "failed",
        "error": str(error),
        "resume_command": shlex.join([sys.executable, *sys.argv]),
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
