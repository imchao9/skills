#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from review_memory import compute_finding_key
except Exception:  # pragma: no cover - keeps this script usable standalone.
    compute_finding_key = None  # type: ignore[assignment]

SEVERITIES = ["P0", "P1", "P2", "P3"]
INLINE_SEVERITIES = {"P0", "P1"}
OPEN_STATUSES = {"open", "candidate"}
FEEDBACK_STATUSES = {"developer_resolved", "waived", "rejected", "adopted"}
ACCEPTED_STATUSES = {"developer_resolved", "waived", "adopted"}
VALID_STATUSES = OPEN_STATUSES | FEEDBACK_STATUSES
COMMAND_RE = re.compile(r"/ai-review\s+(waive|reject)\s+([A-Za-z0-9_-]{8,64})(?:\s+(.+))?", re.IGNORECASE | re.DOTALL)
FINDING_KEY_RE = re.compile(r"finding_key\s*=\s*([A-Za-z0-9_-]{8,64})")
DEFAULT_SUMMARY_BRANCH = "main"
DEFAULT_SUMMARY_SUBDIR = "cr-notes"
DEFAULT_SUMMARY_REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SUMMARY_REPO_URL = "git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sanitize_slug(value: Optional[str]) -> str:
    value = value or "unknown"
    value = value.replace(".git", "")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value or "unknown"


def repo_path_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if "/-/" in path:
        path = path.split("/-/", 1)[0]
    return path or None


def project_id_from_payload(result: dict, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    mr_url = result.get("snapshot", {}).get("mr_url") or result.get("mr_url")
    repo_path = repo_path_from_url(mr_url)
    if repo_path:
        return quote(repo_path, safe="")
    repo_key = result.get("snapshot", {}).get("repo_key") or result.get("repo_key")
    if repo_key:
        repo_key = repo_key.replace("git@", "").replace(":", "/")
        if repo_key.endswith(".git"):
            repo_key = repo_key[:-4]
        parts = repo_key.split("/", 1)
        if len(parts) == 2:
            return quote(parts[1], safe="")
    raise ValueError("无法推断 GitLab project id，请传 --project-id。")


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) == 10:
        value = value + "T00:00:00+00:00"
    value = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid datetime: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def in_time_range(value: Optional[str], start: Optional[datetime], end: Optional[datetime]) -> bool:
    parsed = parse_datetime(value)
    if parsed is None:
        return start is None and end is None
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


def normalize_status(status: Optional[str]) -> str:
    status = (status or "open").strip()
    if status == "candidate":
        return "open"
    if status == "adopted":
        return "developer_resolved"
    if status not in VALID_STATUSES:
        return "open"
    return status


def normalize_severity(value: Optional[str]) -> str:
    value = (value or "P3").upper()
    return value if value in SEVERITIES else "P3"


def payload_findings(payload: Any) -> List[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("findings"), list):
            return payload["findings"]
        if isinstance(payload.get("issues"), list):
            return payload["issues"]
    return []


def context_meta(context: Optional[dict]) -> dict:
    if not context:
        return {}
    repo = context.get("repo") or {}
    mr = context.get("mr") or {}
    inputs = context.get("input") or {}
    return {
        "repo_key": repo.get("key"),
        "repo_name": repo.get("label"),
        "mr_iid": mr.get("iid"),
        "mr_url": mr.get("web_url"),
        "source_branch": mr.get("source_branch"),
        "target_branch": mr.get("target_branch"),
        "base_sha": inputs.get("base"),
        "start_sha": inputs.get("start"),
        "head_sha": inputs.get("head"),
        "target_type": "mr" if mr else ("branch" if inputs.get("base") and inputs.get("head") else "diff"),
        "db_mcp_status": context.get("db_mcp_status"),
        "blind_spots": context.get("notes") or [],
    }


def compute_key(repo_key: str, finding: dict) -> str:
    if finding.get("finding_key"):
        return str(finding["finding_key"])
    if compute_finding_key:
        return compute_finding_key(
            repo_key,
            finding.get("rule_id") or "GEN-001",
            finding.get("file") or "unknown",
            finding.get("title") or "untitled",
            finding.get("line"),
        )
    raw = "|".join([
        repo_key,
        finding.get("rule_id") or "GEN-001",
        finding.get("file") or "unknown",
        finding.get("title") or "untitled",
        str(finding.get("line") or 0),
    ])
    return uuid.uuid5(uuid.NAMESPACE_URL, raw).hex[:16]


def normalize_finding(repo_key: str, snapshot_uuid: str, team: str, mr_iid: Any, finding: dict, index: int) -> dict:
    line = finding.get("line")
    try:
        line = int(line) if line not in (None, "") else None
    except (TypeError, ValueError):
        line = None
    normalized = {
        "snapshot_uuid": snapshot_uuid,
        "issue_no": finding.get("issue_no") or f"Issue-{index}",
        "finding_key": compute_key(repo_key, finding),
        "team": team,
        "repo_key": repo_key,
        "mr_iid": mr_iid,
        "severity": normalize_severity(finding.get("severity")),
        "category": finding.get("category") or "general",
        "rule_id": finding.get("rule_id") or "GEN-001",
        "title": finding.get("title") or "未命名问题",
        "file": finding.get("file") or "unknown",
        "line": line,
        "evidence": finding.get("evidence") or "",
        "impact": finding.get("impact") or "",
        "recommendation": finding.get("recommendation") or finding.get("recommended_fix") or "",
        "status": normalize_status(finding.get("status")),
        "discussion_id": finding.get("discussion_id"),
        "discussion_url": finding.get("discussion_url"),
    }
    return normalized


def severity_counts(findings: List[dict]) -> dict:
    counts = Counter(item.get("severity") for item in findings)
    return {severity: counts.get(severity, 0) for severity in SEVERITIES}


def build_result(context: Optional[dict], findings_payload: dict, args: argparse.Namespace) -> dict:
    meta = context_meta(context)
    team = args.team or findings_payload.get("team") or os.getenv("REVIEW_TEAM") or os.getenv("TEAM_NAME") or "unknown"
    repo_key = args.repo_key or findings_payload.get("repo_key") or meta.get("repo_key") or "unknown"
    repo_name = args.repo_name or findings_payload.get("repo_name") or findings_payload.get("repo_label") or meta.get("repo_name") or sanitize_slug(repo_key).split("-")[-1]
    mr_iid = args.mr_iid or findings_payload.get("mr_iid") or meta.get("mr_iid")
    target_type = args.target_type or findings_payload.get("target_type") or meta.get("target_type") or ("mr" if mr_iid else "branch")
    snapshot_uuid = args.snapshot_uuid or str(uuid.uuid4())
    created_at = args.created_at or utc_now()
    raw_findings = payload_findings(findings_payload)
    findings = [normalize_finding(repo_key, snapshot_uuid, team, mr_iid, item, idx) for idx, item in enumerate(raw_findings, start=1)]
    snapshot = {
        "snapshot_uuid": snapshot_uuid,
        "team": team,
        "repo_key": repo_key,
        "repo_name": repo_name,
        "repo_slug": sanitize_slug(repo_name),
        "target_type": target_type,
        "mr_iid": mr_iid,
        "mr_url": args.mr_url or findings_payload.get("mr_url") or meta.get("mr_url"),
        "source_branch": args.source_branch or findings_payload.get("source_branch") or meta.get("source_branch"),
        "target_branch": args.target_branch or findings_payload.get("target_branch") or meta.get("target_branch"),
        "base_sha": args.base_sha or findings_payload.get("base_sha") or findings_payload.get("base_ref") or meta.get("base_sha"),
        "start_sha": args.start_sha or findings_payload.get("start_sha") or meta.get("start_sha"),
        "head_sha": args.head_sha or findings_payload.get("head_sha") or findings_payload.get("head_ref") or meta.get("head_sha"),
        "branch_review_key": None,
        "created_at": created_at,
        "report_url": args.report_url,
    }
    if target_type != "mr":
        snapshot["branch_review_key"] = "|".join(str(part or "") for part in [repo_key, snapshot["target_branch"], snapshot["source_branch"], snapshot["head_sha"]])
    summary = {
        "issue_total": len(findings),
        "severity_counts": severity_counts(findings),
        "inline_comment_severities": sorted(INLINE_SEVERITIES),
        "status_counts": dict(Counter(item["status"] for item in findings)),
    }
    return {
        "schema_version": "ai-cr-mvp/v1",
        "snapshot": snapshot,
        "summary": summary,
        "findings": findings,
        "blind_spots": findings_payload.get("blind_spots") or meta.get("blind_spots") or [],
    }


def markdown_table_row(values: Sequence[Any]) -> str:
    escaped = []
    for value in values:
        text = "" if value is None else str(value)
        escaped.append(text.replace("|", "\\|").replace("\n", "<br>"))
    return "| " + " | ".join(escaped) + " |"


def render_report(result: dict) -> str:
    snapshot = result["snapshot"]
    summary = result["summary"]
    findings = result["findings"]
    lines = [
        "# AI Code Review 报告",
        "",
        "## 报告信息",
        "",
        markdown_table_row(["字段", "内容"]),
        markdown_table_row(["---", "---"]),
        markdown_table_row(["审查快照ID", snapshot.get("snapshot_uuid")]),
        markdown_table_row(["团队", snapshot.get("team")]),
        markdown_table_row(["项目", snapshot.get("repo_name")]),
        markdown_table_row(["目标类型", snapshot.get("target_type")]),
        markdown_table_row(["MR", snapshot.get("mr_url") or snapshot.get("mr_iid") or "-"]),
        markdown_table_row(["分支", f"{snapshot.get('source_branch') or '-'} -> {snapshot.get('target_branch') or '-'}"]),
        markdown_table_row(["版本", f"{snapshot.get('base_sha') or '-'}..{snapshot.get('head_sha') or '-'}"]),
        markdown_table_row(["生成时间", snapshot.get("created_at")]),
        "",
        "## 风险摘要",
        "",
    ]
    counts = summary.get("severity_counts") or {}
    lines.append("- Issue 总数: " + str(summary.get("issue_total", 0)))
    for severity in SEVERITIES:
        lines.append(f"- {severity}: {counts.get(severity, 0)}")
    lines.extend([
        "",
        "## 重点问题汇总表",
        "",
        markdown_table_row(["Issue", "优先级", "问题描述", "问题分类", "审查状态", "文件", "详情跳转"]),
        markdown_table_row(["---", "---", "---", "---", "---", "---", "---"]),
    ])
    for finding in findings:
        anchor = finding["issue_no"].lower().replace("-", "-")
        file_line = f"{finding.get('file')}:{finding.get('line')}" if finding.get("line") else finding.get("file")
        lines.append(markdown_table_row([finding["issue_no"], finding["severity"], finding["title"], finding["category"], finding["status"], file_line, f"[{finding['issue_no']}](#{anchor})"]))
    lines.extend(["", "## Issue 详情", ""])
    for finding in findings:
        file_line = f"{finding.get('file')}:{finding.get('line')}" if finding.get("line") else finding.get("file")
        lines.extend([
            f"<a id=\"{finding['issue_no'].lower()}\"></a>",
            "",
            f"### {finding['issue_no']} {finding['severity']} {finding['title']}",
            "",
            f"- finding_key: `{finding['finding_key']}`",
            f"- rule_id: `{finding['rule_id']}`",
            f"- category: `{finding['category']}`",
            f"- location: `{file_line}`",
            f"- status: `{finding['status']}`",
            "",
            "**证据**",
            "",
            finding.get("evidence") or "-",
            "",
            "**影响**",
            "",
            finding.get("impact") or "-",
            "",
            "**建议**",
            "",
            finding.get("recommendation") or "-",
            "",
        ])
    blind_spots = result.get("blind_spots") or []
    if blind_spots:
        lines.extend(["## 剩余盲点", ""])
        for item in blind_spots:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def render_summary_comment(result: dict, report_url: Optional[str]) -> str:
    snapshot = result["snapshot"]
    summary = result["summary"]
    counts = summary.get("severity_counts") or {}
    findings = result.get("findings") or []
    top = sorted(findings, key=lambda item: (SEVERITIES.index(item.get("severity", "P3")), item.get("issue_no", "")))[:8]
    lines = [
        "## AI Code Review 结果",
        "",
        f"审查快照: `{snapshot.get('snapshot_uuid')}`",
        f"范围: `{snapshot.get('source_branch') or '-'} -> {snapshot.get('target_branch') or '-'}`",
        f"版本: `{snapshot.get('base_sha') or '-'}..{snapshot.get('head_sha') or '-'}`",
        "",
        "风险摘要:",
    ]
    for severity in SEVERITIES:
        lines.append(f"- {severity}: {counts.get(severity, 0)}")
    if top:
        lines.extend(["", "重点问题:"])
        for finding in top:
            lines.append(f"{finding['issue_no']}. [{finding['severity']}] {finding['title']} (`{finding['finding_key']}`)")
    if report_url or snapshot.get("report_url"):
        lines.extend(["", f"完整报告: {report_url or snapshot.get('report_url')}"])
    lines.extend([
        "",
        "处理说明:",
        "- P0/P1 会尽量创建行内 discussion，修复后可 Resolve 对应 discussion。",
        "- 如需豁免或认为误报，请回复 `/ai-review waive <finding_key> 原因` 或 `/ai-review reject <finding_key> 原因`。",
    ])
    return "\n".join(lines)


def render_finding_comment(finding: dict, snapshot_uuid: str) -> str:
    return "\n".join([
        f"[AI-CR][{finding['severity']}][finding_key={finding['finding_key']}][snapshot={snapshot_uuid}]",
        "",
        finding["title"],
        "",
        "证据:",
        finding.get("evidence") or "-",
        "",
        "建议:",
        finding.get("recommendation") or "-",
        "",
        "处理方式:",
        "- 修复后请 Resolve 本 discussion。",
        f"- 豁免: `/ai-review waive {finding['finding_key']} 原因`",
        f"- 不接受: `/ai-review reject {finding['finding_key']} 原因`",
    ])


def run_glab(args: Sequence[str], cwd: Optional[Path] = None) -> Any:
    if shutil.which("glab") is None:
        raise ValueError("缺少 glab，无法发布或同步 GitLab 评论。")
    result = subprocess.run(["glab", *args], cwd=str(cwd or Path.cwd()), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise ValueError(f"glab {' '.join(args)} failed: {result.stderr.strip()}")
    stdout = result.stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return stdout


def gitlab_post(path: str, fields: Dict[str, Any], cwd: Optional[Path] = None) -> Any:
    args = ["api", path, "--method", "POST"]
    for key, value in fields.items():
        if value is None:
            continue
        args.extend(["-f", f"{key}={value}"])
    return run_glab(args, cwd=cwd)


def gitlab_get(path: str, cwd: Optional[Path] = None) -> Any:
    return run_glab(["api", path], cwd=cwd)


def run_git(args: Sequence[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def infer_default_summary_repo_root() -> Optional[Path]:
    try:
        root = run_git(["rev-parse", "--show-toplevel"], DEFAULT_SUMMARY_REPO_ROOT)
    except Exception:
        return None
    return Path(root).resolve()


def resolve_summary_repo_url(args: argparse.Namespace) -> str:
    return args.summary_repo_url or DEFAULT_SUMMARY_REPO_URL


def prepare_summary_workspace(args: argparse.Namespace) -> Tuple[Path, Path, str, Optional[Path]]:
    branch = args.summary_branch
    explicit_repo_root = args.summary_repo_root
    default_repo_root = None if explicit_repo_root or args.summary_repo_url else infer_default_summary_repo_root()
    repo_root_value = explicit_repo_root or default_repo_root
    if repo_root_value:
        repo_root = Path(repo_root_value).expanduser().resolve()
        run_git(["rev-parse", "--show-toplevel"], repo_root)
        if not args.no_fetch:
            run_git(["fetch", args.remote, f"{branch}:refs/remotes/{args.remote}/{branch}"], repo_root)
        parent = Path(tempfile.mkdtemp(prefix="ai-cr-summary-worktree-"))
        worktree = parent / "worktree"
        ref = branch if args.no_fetch else f"refs/remotes/{args.remote}/{branch}"
        try:
            run_git(["worktree", "add", "--detach", str(worktree), ref], repo_root)
        except Exception:
            shutil.rmtree(parent, ignore_errors=True)
            raise
        return worktree, parent, "worktree", repo_root

    repo_url = resolve_summary_repo_url(args)
    parent = Path(tempfile.mkdtemp(prefix="ai-cr-summary-clone-"))
    worktree = parent / "summary-repo"
    try:
        run_git(["clone", "--depth", "1", "--branch", branch, repo_url, str(worktree)], parent)
    except Exception:
        shutil.rmtree(parent, ignore_errors=True)
        raise
    return worktree, parent, "clone", None


def cleanup_summary_workspace(worktree: Path, parent: Path, source_type: str, keep_workspace: bool, repo_root: Optional[Path]) -> None:
    if keep_workspace:
        return
    if source_type == "worktree":
        try:
            run_git(["worktree", "remove", "--force", str(worktree)], repo_root or worktree)
        except Exception:
            pass
    shutil.rmtree(parent, ignore_errors=True)


def default_commit_message(snapshot: dict) -> str:
    repo_name = sanitize_slug(snapshot.get("repo_name") or snapshot.get("repo_slug") or "unknown")
    target = f"mr-{snapshot.get('mr_iid')}" if snapshot.get("target_type") == "mr" and snapshot.get("mr_iid") else sanitize_slug(snapshot.get("source_branch") or snapshot.get("head_sha") or "diff")
    return f"chore(cr-notes): archive {repo_name} {target}"


def push_summary_branch(worktree: Path, args: argparse.Namespace) -> None:
    push_args = ["push", args.remote, f"HEAD:{args.summary_branch}"]
    try:
        run_git(push_args, worktree)
        return
    except ValueError as exc:
        detail = str(exc)
        retryable = (
            "non-fast-forward" in detail
            or "fetch first" in detail
            or "stale info" in detail
            or "rejected" in detail
        )
        if not retryable:
            raise
    run_git(["fetch", args.remote, f"{args.summary_branch}:refs/remotes/{args.remote}/{args.summary_branch}"], worktree)
    run_git(["rebase", f"refs/remotes/{args.remote}/{args.summary_branch}"], worktree)
    run_git(push_args, worktree)


def archive_commit_push(result_json: Path, args: argparse.Namespace) -> dict:
    worktree, cleanup_root, source_type, repo_root = prepare_summary_workspace(args)
    try:
        summary_root = worktree / args.summary_subdir
        archive_output = archive_result(result_json, summary_root)
        changed = run_git(["status", "--porcelain", "--", args.summary_subdir], worktree)
        output = {
            **archive_output,
            "summary_repo_workspace": str(worktree),
            "summary_root": str(summary_root),
            "summary_branch": args.summary_branch,
            "summary_subdir": args.summary_subdir,
            "committed": False,
            "pushed": False,
        }
        if not changed:
            output["message"] = "汇总仓没有新增变更，跳过 commit/push。"
            return output

        result = load_json(result_json)
        message = args.commit_message or default_commit_message(result.get("snapshot") or {})
        run_git(["add", "--", args.summary_subdir], worktree)
        run_git([
            "-c",
            "user.name=AI Code Review Bot",
            "-c",
            "user.email=ai-code-review@example.local",
            "commit",
            "-m",
            message,
        ], worktree)
        output["committed"] = True
        output["commit"] = run_git(["rev-parse", "HEAD"], worktree)
        if not args.no_push:
            push_summary_branch(worktree, args)
            output["pushed"] = True
        else:
            output["message"] = "--no-push 已保留临时 workspace，便于手动检查或推送。"
        return output
    finally:
        cleanup_summary_workspace(worktree, cleanup_root, source_type, args.keep_workspace or args.no_push, repo_root)


def append_jsonl_once(path: Path, record: dict, keys: Sequence[str]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    wanted = tuple(record.get(key) for key in keys)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    current = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if tuple(current.get(key) for key in keys) == wanted:
                    return False
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    items = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                items.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return items


def upsert_repo(index_dir: Path, snapshot: dict) -> None:
    path = index_dir / "repos.json"
    repos: Dict[str, dict] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                repos = {item.get("repo_key"): item for item in loaded if item.get("repo_key")}
            elif isinstance(loaded, dict):
                repos = loaded
        except json.JSONDecodeError:
            repos = {}
    repo_key = snapshot["repo_key"]
    next_record = {
        "repo_key": snapshot.get("repo_key"),
        "repo_name": snapshot.get("repo_name"),
        "repo_slug": snapshot.get("repo_slug"),
        "team": snapshot.get("team"),
    }
    current = repos.get(repo_key)
    current_core = {key: current.get(key) for key in next_record} if current else None
    if current_core == next_record:
        return
    next_record["updated_at"] = utc_now()
    repos[repo_key] = next_record
    write_json(path, {key: repos[key] for key in sorted(repos)})


def archive_result(result_json: Path, summary_root: Path) -> dict:
    result = load_json(result_json)
    snapshot = result["snapshot"]
    index_dir = summary_root / "index"
    report_dir = summary_root / "reports" / sanitize_slug(snapshot.get("team")) / sanitize_slug(snapshot.get("repo_slug") or snapshot.get("repo_name"))
    target_label = f"mr-{snapshot.get('mr_iid')}" if snapshot.get("target_type") == "mr" and snapshot.get("mr_iid") else f"branch-{sanitize_slug(snapshot.get('source_branch'))}"
    report_dir = report_dir / target_label / snapshot["snapshot_uuid"]
    report_dir.mkdir(parents=True, exist_ok=True)
    copied_result = report_dir / "review-result.json"
    copied_report = report_dir / "review-report.md"
    shutil.copy2(result_json, copied_result)
    source_report = result_json.with_name("review-report.md")
    if source_report.exists():
        shutil.copy2(source_report, copied_report)
    else:
        copied_report.write_text(render_report(result), encoding="utf-8")
    snapshot_record = dict(snapshot)
    snapshot_record["result_path"] = str(copied_result.relative_to(summary_root))
    snapshot_record["report_path"] = str(copied_report.relative_to(summary_root))
    snapshot_added = append_jsonl_once(index_dir / "snapshots.jsonl", snapshot_record, ["snapshot_uuid"])
    finding_added = 0
    for finding in result.get("findings") or []:
        if append_jsonl_once(index_dir / "findings.jsonl", finding, ["snapshot_uuid", "finding_key"]):
            finding_added += 1
    upsert_repo(index_dir, snapshot)
    return {
        "report_dir": str(report_dir),
        "snapshot_added": snapshot_added,
        "findings_added": finding_added,
    }


def discussion_status(discussion: dict) -> bool:
    if "resolved" in discussion:
        return bool(discussion.get("resolved"))
    notes = discussion.get("notes") or []
    resolvable = [note for note in notes if note.get("resolvable")]
    if not resolvable:
        return False
    return all(note.get("resolved") for note in resolvable)


def parse_feedback_commands(discussion: dict) -> List[dict]:
    events = []
    for note in discussion.get("notes") or []:
        body = note.get("body") or ""
        for match in COMMAND_RE.finditer(body):
            command, finding_key, reason = match.groups()
            status = "waived" if command.lower() == "waive" else "rejected"
            events.append({
                "finding_key": finding_key,
                "discussion_id": discussion.get("id"),
                "event": command.lower(),
                "status_after": status,
                "reason": (reason or "").strip(),
                "updated_at": note.get("updated_at") or utc_now(),
                "author": (note.get("author") or {}).get("username"),
                "note_id": note.get("id"),
            })
    return events


def find_finding_key_in_discussion(discussion: dict) -> Optional[str]:
    for note in discussion.get("notes") or []:
        body = note.get("body") or ""
        match = FINDING_KEY_RE.search(body)
        if match:
            return match.group(1)
    return None


def latest_statuses(summary_root: Path) -> Dict[Tuple[str, str], str]:
    statuses: Dict[Tuple[str, str], str] = {}
    for finding in read_jsonl(summary_root / "index" / "findings.jsonl"):
        key = (str(finding.get("snapshot_uuid")), str(finding.get("finding_key")))
        statuses[key] = normalize_status(finding.get("status"))
    for event in read_jsonl(summary_root / "index" / "discussions.jsonl"):
        snapshot_uuid = str(event.get("snapshot_uuid") or "")
        finding_key = str(event.get("finding_key") or "")
        if snapshot_uuid and finding_key:
            statuses[(snapshot_uuid, finding_key)] = normalize_status(event.get("status_after"))
    return statuses


def build_stats(summary_root: Path, start: Optional[datetime], end: Optional[datetime], team: Optional[str]) -> dict:
    snapshots = read_jsonl(summary_root / "index" / "snapshots.jsonl")
    findings = read_jsonl(summary_root / "index" / "findings.jsonl")
    statuses = latest_statuses(summary_root)
    snapshot_by_id = {item.get("snapshot_uuid"): item for item in snapshots}
    selected_snapshots = {
        item.get("snapshot_uuid")
        for item in snapshots
        if item.get("snapshot_uuid")
        and in_time_range(item.get("created_at"), start, end)
        and (not team or item.get("team") == team)
    }
    selected_findings = []
    for finding in findings:
        snapshot_uuid = finding.get("snapshot_uuid")
        if snapshot_uuid not in selected_snapshots:
            continue
        status = statuses.get((str(snapshot_uuid), str(finding.get("finding_key"))), normalize_status(finding.get("status")))
        item = dict(finding)
        item["status"] = status
        selected_findings.append(item)

    teams = {snapshot_by_id[sid].get("team") for sid in selected_snapshots if sid in snapshot_by_id and snapshot_by_id[sid].get("team")}
    issue_total = len(selected_findings)
    feedback_total = sum(1 for item in selected_findings if item.get("status") not in OPEN_STATUSES)
    accepted_total = sum(1 for item in selected_findings if item.get("status") in ACCEPTED_STATUSES)

    team_rows = []
    by_team: Dict[str, List[dict]] = defaultdict(list)
    snapshots_by_team: Dict[str, set] = defaultdict(set)
    for sid in selected_snapshots:
        snapshot = snapshot_by_id.get(sid) or {}
        snapshots_by_team[snapshot.get("team") or "unknown"].add(sid)
    for finding in selected_findings:
        by_team[finding.get("team") or "unknown"].append(finding)
    for team_name in sorted(set(by_team) | set(snapshots_by_team)):
        items = by_team.get(team_name, [])
        sev_counts = severity_counts(items)
        feedback = sum(1 for item in items if item.get("status") not in OPEN_STATUSES)
        accepted = sum(1 for item in items if item.get("status") in ACCEPTED_STATUSES)
        top_by_severity = {}
        for severity in SEVERITIES:
            categories = Counter(item.get("category") or item.get("rule_id") or "general" for item in items if item.get("severity") == severity)
            top_by_severity[severity] = categories.most_common(5)
        team_rows.append({
            "team": team_name,
            "review_count": len(snapshots_by_team.get(team_name, set())),
            "issue_total": len(items),
            "severity_counts": sev_counts,
            "feedback_count": feedback,
            "feedback_ratio": round(feedback / len(items), 4) if items else 0,
            "accepted_count": accepted,
            "accepted_ratio": round(accepted / len(items), 4) if items else 0,
            "top_categories_by_severity": top_by_severity,
        })
    return {
        "summary": {
            "team_count": len(teams),
            "review_count": len(selected_snapshots),
            "issue_total": issue_total,
            "feedback_count": feedback_total,
            "feedback_ratio": round(feedback_total / issue_total, 4) if issue_total else 0,
            "accepted_count": accepted_total,
            "accepted_ratio": round(accepted_total / issue_total, 4) if issue_total else 0,
            "severity_counts": severity_counts(selected_findings),
        },
        "teams": team_rows,
    }


def cmd_build(args: argparse.Namespace) -> int:
    findings_payload = load_json(Path(args.findings_json))
    context = load_json(Path(args.context_json)) if args.context_json else None
    result = build_result(context, findings_payload, args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "review-result.json"
    report_path = output_dir / "review-report.md"
    write_json(result_path, result)
    report_path.write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"result": str(result_path), "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    output = archive_result(Path(args.result_json), Path(args.summary_root))
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_archive_and_push(args: argparse.Namespace) -> int:
    if getattr(args, "no_push", False):
        raise ValueError("archive-and-push 必须推送到远端；不再支持 --no-push。")
    output = archive_commit_push(Path(args.result_json), args)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def cmd_publish_gitlab(args: argparse.Namespace) -> int:
    result_path = Path(args.result_json)
    result = load_json(result_path)
    snapshot = result["snapshot"]
    mr_iid = args.mr_iid or snapshot.get("mr_iid")
    if not mr_iid:
        raise ValueError("publish-gitlab 需要 MR IID。")
    project_id = project_id_from_payload(result, args.project_id)
    summary_body = render_summary_comment(result, args.report_url)
    published = {"summary_note": None, "discussions": []}
    if args.dry_run:
        print(json.dumps({"project_id": project_id, "mr_iid": mr_iid, "summary_body": summary_body}, ensure_ascii=False, indent=2))
        return 0
    summary_note = gitlab_post(f"projects/{project_id}/merge_requests/{mr_iid}/notes", {"body": summary_body})
    published["summary_note"] = summary_note
    base_sha = snapshot.get("base_sha")
    start_sha = snapshot.get("start_sha") or base_sha
    head_sha = snapshot.get("head_sha")
    for finding in result.get("findings") or []:
        if finding.get("severity") not in INLINE_SEVERITIES:
            continue
        body = render_finding_comment(finding, snapshot["snapshot_uuid"])
        fields: Dict[str, Any] = {"body": body}
        if finding.get("file") and finding.get("line") and base_sha and head_sha:
            fields.update({
                "position[position_type]": "text",
                "position[base_sha]": base_sha,
                "position[start_sha]": start_sha,
                "position[head_sha]": head_sha,
                "position[new_path]": finding.get("file"),
                "position[new_line]": finding.get("line"),
            })
        discussion = gitlab_post(f"projects/{project_id}/merge_requests/{mr_iid}/discussions", fields)
        if isinstance(discussion, dict):
            finding["discussion_id"] = discussion.get("id")
            notes = discussion.get("notes") or []
            if notes:
                finding["discussion_url"] = notes[0].get("url")
        published["discussions"].append({"finding_key": finding.get("finding_key"), "discussion_id": finding.get("discussion_id")})
    write_json(result_path, result)
    print(json.dumps(published, ensure_ascii=False, indent=2))
    return 0


def cmd_sync_discussions(args: argparse.Namespace) -> int:
    result = load_json(Path(args.result_json))
    snapshot = result["snapshot"]
    mr_iid = args.mr_iid or snapshot.get("mr_iid")
    if not mr_iid:
        raise ValueError("sync-discussions 需要 MR IID。")
    project_id = project_id_from_payload(result, args.project_id)
    discussions = gitlab_get(f"projects/{project_id}/merge_requests/{mr_iid}/discussions") or []
    by_discussion = {str(item.get("discussion_id")): item for item in result.get("findings") or [] if item.get("discussion_id")}
    by_key = {str(item.get("finding_key")): item for item in result.get("findings") or [] if item.get("finding_key")}
    events = []
    for discussion in discussions:
        discussion_id = str(discussion.get("id"))
        finding = by_discussion.get(discussion_id)
        finding_key = finding.get("finding_key") if finding else find_finding_key_in_discussion(discussion)
        if not finding_key or finding_key not in by_key:
            for command_event in parse_feedback_commands(discussion):
                command_event["snapshot_uuid"] = snapshot.get("snapshot_uuid")
                events.append(command_event)
            continue
        if discussion_status(discussion):
            event = {
                "snapshot_uuid": snapshot.get("snapshot_uuid"),
                "finding_key": finding_key,
                "discussion_id": discussion_id,
                "event": "resolved",
                "status_after": "developer_resolved",
                "updated_at": utc_now(),
            }
            events.append(event)
            by_key[finding_key]["status"] = "developer_resolved"
        for command_event in parse_feedback_commands(discussion):
            command_event["snapshot_uuid"] = snapshot.get("snapshot_uuid")
            events.append(command_event)
            if command_event.get("finding_key") in by_key:
                by_key[command_event["finding_key"]]["status"] = command_event["status_after"]
    if args.summary_root:
        path = Path(args.summary_root) / "index" / "discussions.jsonl"
        added = 0
        for event in events:
            keys = ["snapshot_uuid", "finding_key", "discussion_id", "event", "status_after"]
            if event.get("note_id"):
                keys.append("note_id")
            if append_jsonl_once(path, event, keys):
                added += 1
        write_json(Path(args.result_json), result)
        print(json.dumps({"events": len(events), "added": added}, ensure_ascii=False, indent=2))
    else:
        write_json(Path(args.result_json), result)
        print(json.dumps({"events": events}, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    stats = build_stats(Path(args.summary_root), parse_datetime(args.start), parse_datetime(args.end), args.team)
    if args.csv_output:
        path = Path(args.csv_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["team", "review_count", "issue_total", "P0", "P1", "P2", "P3", "feedback_count", "feedback_ratio", "accepted_count", "accepted_ratio"])
            writer.writeheader()
            for row in stats["teams"]:
                sev = row["severity_counts"]
                writer.writerow({
                    "team": row["team"],
                    "review_count": row["review_count"],
                    "issue_total": row["issue_total"],
                    "P0": sev.get("P0", 0),
                    "P1": sev.get("P1", 0),
                    "P2": sev.get("P2", 0),
                    "P3": sev.get("P3", 0),
                    "feedback_count": row["feedback_count"],
                    "feedback_ratio": row["feedback_ratio"],
                    "accepted_count": row["accepted_count"],
                    "accepted_ratio": row["accepted_ratio"],
                })
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成、归档、发布和统计 AI 代码审查产物。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="生成 review-result.json 和 review-report.md。")
    build.add_argument("--findings-json", required=True)
    build.add_argument("--context-json")
    build.add_argument("--output-dir", required=True)
    build.add_argument("--team")
    build.add_argument("--repo-key")
    build.add_argument("--repo-name")
    build.add_argument("--mr-iid")
    build.add_argument("--mr-url")
    build.add_argument("--source-branch")
    build.add_argument("--target-branch")
    build.add_argument("--base-sha")
    build.add_argument("--start-sha")
    build.add_argument("--head-sha")
    build.add_argument("--target-type", choices=["mr", "branch", "diff"])
    build.add_argument("--snapshot-uuid")
    build.add_argument("--created-at")
    build.add_argument("--report-url")
    build.set_defaults(func=cmd_build)

    archive = subparsers.add_parser("archive", help="复制审查产物到本地汇总目录并更新索引；不提交、不推送。")
    archive.add_argument("--result-json", required=True)
    archive.add_argument("--summary-root", required=True)
    archive.set_defaults(func=cmd_archive)

    archive_push = subparsers.add_parser("archive-and-push", help="归档到汇总仓库 cr-notes，提交并强制执行 push。")
    archive_push.add_argument("--result-json", required=True)
    archive_push.add_argument("--summary-repo-url", help=argparse.SUPPRESS)
    archive_push.add_argument("--summary-repo-root", help=argparse.SUPPRESS)
    archive_push.add_argument("--summary-branch", default=DEFAULT_SUMMARY_BRANCH, help=argparse.SUPPRESS)
    archive_push.add_argument("--summary-subdir", default=DEFAULT_SUMMARY_SUBDIR, help=argparse.SUPPRESS)
    archive_push.add_argument("--remote", default="origin", help=argparse.SUPPRESS)
    archive_push.add_argument("--commit-message")
    archive_push.add_argument("--no-fetch", action="store_true", help=argparse.SUPPRESS)
    archive_push.add_argument("--keep-workspace", action="store_true", help=argparse.SUPPRESS)
    archive_push.set_defaults(func=cmd_archive_and_push, no_push=False)

    publish = subparsers.add_parser("publish-gitlab", help="发布 MR 总评论和 P0/P1 discussion。")
    publish.add_argument("--result-json", required=True)
    publish.add_argument("--project-id", help="GitLab project id 或 URL 编码后的项目路径；未传时从 MR URL 推断。")
    publish.add_argument("--mr-iid")
    publish.add_argument("--report-url")
    publish.add_argument("--dry-run", action="store_true")
    publish.set_defaults(func=cmd_publish_gitlab)

    sync = subparsers.add_parser("sync-discussions", help="同步 GitLab discussion 的 resolved 状态和反馈命令。")
    sync.add_argument("--result-json", required=True)
    sync.add_argument("--project-id")
    sync.add_argument("--mr-iid")
    sync.add_argument("--summary-root", help="传入后会把状态事件追加到 index/discussions.jsonl。")
    sync.set_defaults(func=cmd_sync_discussions)

    stats = subparsers.add_parser("stats", help="基于汇总仓库索引生成 CR 总览和团队统计。")
    stats.add_argument("--summary-root", required=True)
    stats.add_argument("--team")
    stats.add_argument("--start", help="包含边界的 UTC 时间或 YYYY-MM-DD。")
    stats.add_argument("--end", help="包含边界的 UTC 时间或 YYYY-MM-DD。")
    stats.add_argument("--csv-output")
    stats.set_defaults(func=cmd_stats)
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
