#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


VALID_STATUSES = {"candidate", "open", "adopted", "developer_resolved", "waived", "rejected"}
VALID_EVENT_TYPES = {"finding_logged", "finding_status_changed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config() -> dict:
    path = skill_root() / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def store_path() -> Path:
    config = load_config()
    path = skill_root() / config["store_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    return path


def append_event(event: dict) -> None:
    path = store_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def iter_events() -> Iterable[dict]:
    path = store_path()
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                yield {"_parse_error": True, "_line_number": line_number, "_raw": raw_line.rstrip("\n")}
                continue
            event["_line_number"] = line_number
            yield event


def normalize_title(title: str) -> str:
    collapsed = " ".join(title.strip().lower().split())
    return collapsed


def compute_finding_key(repo_key: str, rule_id: str, file_path: str, title: str, line: Optional[int]) -> str:
    bucket_size = int(load_config().get("line_bucket_size", 20))
    line_bucket = 0 if line in (None, 0) else int(line) // bucket_size
    base = "|".join([repo_key, rule_id, file_path, normalize_title(title), str(line_bucket)])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def require_fields(payload: dict, required: List[str]) -> None:
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def load_review_input(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_log_review(args: argparse.Namespace) -> int:
    payload = load_review_input(Path(args.input_json))
    repo_key = args.repo_key or payload.get("repo_key")
    repo_label = args.repo_label or payload.get("repo_label") or repo_key
    if not repo_key:
        raise ValueError("必须提供 repo_key")

    findings = payload.get("findings") or []
    if not findings:
        print(json.dumps({"logged": 0, "reason": "没有 findings"}, ensure_ascii=False))
        return 0

    logged = []
    for finding in findings:
        require_fields(
            finding,
            ["rule_id", "category", "severity", "title", "file", "evidence", "recommendation"],
        )
        line = finding.get("line")
        finding_key = compute_finding_key(repo_key, finding["rule_id"], finding["file"], finding["title"], line)
        event = {
            "event_type": "finding_logged",
            "timestamp": utc_now(),
            "repo_key": repo_key,
            "repo_label": repo_label,
            "mr_iid": payload.get("mr_iid"),
            "mr_url": payload.get("mr_url"),
            "base_ref": payload.get("base_ref"),
            "head_ref": payload.get("head_ref"),
            "rule_id": finding["rule_id"],
            "category": finding["category"],
            "severity": finding["severity"],
            "title": finding["title"],
            "file": finding["file"],
            "line": line,
            "evidence": finding["evidence"],
            "recommendation": finding["recommendation"],
            "finding_key": finding_key,
            "status": finding.get("status", "candidate"),
        }
        append_event(event)
        logged.append(event)

    print(
        json.dumps(
            {
                "logged": len(logged),
                "repo_key": repo_key,
                "finding_keys": [item["finding_key"] for item in logged],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def latest_state() -> tuple[Dict[str, dict], int]:
    latest: Dict[str, dict] = {}
    parse_errors = 0
    for event in iter_events():
        if event.get("_parse_error"):
            parse_errors += 1
            continue
        if event.get("event_type") not in VALID_EVENT_TYPES:
            continue
        key = event.get("finding_key")
        if not key:
            continue
        previous = latest.get(key)
        if previous is None or event.get("_line_number", 0) >= previous.get("_line_number", 0):
            latest[key] = event
    return latest, parse_errors


def cmd_mark_finding(args: argparse.Namespace) -> int:
    if args.status not in VALID_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    latest, _ = latest_state()
    current = latest.get(args.finding_key)
    if current is None:
        raise ValueError(f"finding_key not found: {args.finding_key}")

    event = {
        "event_type": "finding_status_changed",
        "timestamp": utc_now(),
        "repo_key": current.get("repo_key"),
        "repo_label": current.get("repo_label"),
        "mr_iid": current.get("mr_iid"),
        "mr_url": current.get("mr_url"),
        "base_ref": current.get("base_ref"),
        "head_ref": current.get("head_ref"),
        "rule_id": current.get("rule_id"),
        "category": current.get("category"),
        "severity": current.get("severity"),
        "title": current.get("title"),
        "file": current.get("file"),
        "line": current.get("line"),
        "evidence": current.get("evidence"),
        "recommendation": current.get("recommendation"),
        "finding_key": args.finding_key,
        "status": args.status,
    }
    append_event(event)
    print(json.dumps({"finding_key": args.finding_key, "status": args.status}, ensure_ascii=False, indent=2))
    return 0


def cmd_query_findings(args: argparse.Namespace) -> int:
    grouped: Dict[str, dict] = {}
    counts = defaultdict(int)
    parse_errors = 0

    for event in iter_events():
        if event.get("_parse_error"):
            parse_errors += 1
            continue
        key = event.get("finding_key")
        if not key:
            continue
        counts[key] += 1 if event.get("event_type") == "finding_logged" else 0
        current = grouped.get(key)
        if current is None or event.get("_line_number", 0) >= current.get("_line_number", 0):
            grouped[key] = event

    items = []
    for key, item in grouped.items():
        item = dict(item)
        item["occurrences"] = counts[key]
        items.append(item)

    def matches(item: dict) -> bool:
        if args.repo_key and item.get("repo_key") != args.repo_key:
            return False
        if args.status and item.get("status") != args.status:
            return False
        if args.rule_id and item.get("rule_id") != args.rule_id:
            return False
        return True

    filtered = [item for item in items if matches(item)]
    filtered.sort(key=lambda item: (-item.get("occurrences", 0), item.get("severity", ""), item.get("title", "")))
    top = filtered[: args.top]
    print(
        json.dumps(
            {
                "total": len(filtered),
                "returned": len(top),
                "parse_errors": parse_errors,
                "findings": top,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="存储和查询 java-backend-code-review 的 findings。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    log_parser = subparsers.add_parser("log-review", help="把 review findings 记录为 candidate 事件。")
    log_parser.add_argument("--repo-key", help="稳定的仓库标识。")
    log_parser.add_argument("--repo-label", help="人类可读的仓库名称。")
    log_parser.add_argument("--input-json", required=True, help="包含 review findings 的 JSON 文件。")
    log_parser.set_defaults(func=cmd_log_review)

    mark_parser = subparsers.add_parser("mark-finding", help="修改已存储 finding 的状态。")
    mark_parser.add_argument("--finding-key", required=True, help="要更新的 finding key。")
    mark_parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES), help="新的 finding 状态。")
    mark_parser.set_defaults(func=cmd_mark_finding)

    query_parser = subparsers.add_parser("query-findings", help="查询已存储的 review findings。")
    query_parser.add_argument("--repo-key", help="按仓库标识过滤。")
    query_parser.add_argument("--status", choices=sorted(VALID_STATUSES), help="按最新状态过滤。")
    query_parser.add_argument("--rule-id", help="按规则编号过滤。")
    query_parser.add_argument("--top", type=int, default=20, help="最多返回的分组 finding 数量。")
    query_parser.set_defaults(func=cmd_query_findings)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
