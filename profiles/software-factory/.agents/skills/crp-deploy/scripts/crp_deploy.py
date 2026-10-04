#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from auth import (
    AUTH_DOC_PATH,
    BROWSER_USER_AGENT,
    DEFAULT_AUTH_FILE,
    DEFAULT_STORAGE_STATE,
    build_auth_help_payload,
    resolve_cookie_header,
)


DEFAULT_BASE_URL = "https://crp.codemao.cn"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = SKILL_ROOT / "output"
WORKFLOW_LOG_DIR = OUTPUT_DIR / "workflow-logs"
DEFAULT_METRICS_FILE = OUTPUT_DIR / "crp-metrics.json"
CMDB_BASE_URL = "https://cmdb.codemao.cn/new"
CMDB_PROJECT_MODULES_URL_TEMPLATE = "https://cmdb.codemao.cn/new//zcmdb/api/business/project_modules?project_id={project_id}"

BUILD_SUCCESS_STATUSES = {"success"}
BUILD_FAILURE_STATUSES = {"failure", "failed", "fail", "abort", "aborted", "canceled", "cancelled", "error"}
BUILD_TERMINAL_STATUSES = BUILD_SUCCESS_STATUSES | BUILD_FAILURE_STATUSES
RELEASE_SUCCESS_STATUSES = {"end", "released"}
RELEASE_FAILURE_STATUSES = {"failure", "failed", "fail", "abort", "aborted", "canceled", "cancelled", "error"}
RELEASE_TERMINAL_STATUSES = RELEASE_SUCCESS_STATUSES | RELEASE_FAILURE_STATUSES
ACTIVE_BUILD_STATUSES = {"new", "pending", "queue", "queued", "running", "building", "releasing"}
ACTIVE_RELEASE_STATUSES = {"new", "pending", "queue", "queued", "running", "building", "releasing"}
JSON_PRETTY = False
TRANSIENT_HTTP_STATUS_CODES = {429, 502, 503, 504}
RETRYABLE_HTTP_METHODS = {"GET"}
REQUEST_MAX_ATTEMPTS = 3
REQUEST_RETRY_BASE_SECONDS = 0.5
BOOTSTRAP_COOKIE_NAMES = {"user_name", "display_name"}
PARAMETER_CANDIDATE_LIMIT = 10
QA_CANDIDATE_LIMIT = 50
COMPACT_TEXT_LIMIT = 160
LONG_TEXT_FIELDS = {"message", "error", "reason", "description", "result", "release_check"}
AUTH_REFRESH_NEXT = "run `node scripts/auth-login.js` in skill root, or read references/auth.md; then rerun previous command"
WORKFLOW_LOG_CLEANUP_SUFFIXES = (".state.json.lock", ".state.json", ".jsonl")


class AuthRequiredError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(str(payload.get("message") or "CRP auth is required."))


class WorkflowParameterError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(str(payload.get("err") or "workflow_parameter_error"))


class WorkflowBlockedError(RuntimeError):
    pass


class WorkflowReportedError(RuntimeError):
    pass


@dataclass
class WorkflowTargets:
    requirement: dict[str, Any]
    requirement_id: int
    modules: list[dict[str, Any]]
    module_names: list[str]
    businesses: list[str]
    change_contents: list[str]


@dataclass
class WorkflowExpectations:
    build_seconds: float | None
    release_seconds: float | None


@dataclass
class WorkflowPreflight:
    baseline_build_id: int
    chosen_test: dict[str, Any] | None
    chosen_test_detail: dict[str, Any] | None
    build_payload: list[dict[str, Any]]
    missing_test_modules: list[str] = field(default_factory=list)


@dataclass
class WorkflowDeployContext:
    targets: WorkflowTargets
    expectations: WorkflowExpectations
    preflight: WorkflowPreflight


@dataclass
class WorkflowResumeContext:
    requirement_id: int
    modules: list[dict[str, Any]]
    module_names: list[str]
    businesses: list[str]
    change_contents: list[str]
    baseline_build_id: int
    build_seconds: float | None
    release_seconds: float | None


@dataclass
class WorkflowExecutionState:
    test_id: int | None = None
    build_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    create_build_response: Any = None
    build_ids_by_module: dict[str, int] = field(default_factory=dict)
    build_id_binding: str | None = None
    release_id: int | None = None
    release_started: bool = False
    update_image_started: bool = False
    image_updated: bool = False
    done: bool = False


@dataclass
class ResolvedModule:
    requested_name: str
    full_name: str
    source: str
    short_name: str
    module: dict[str, Any]


@dataclass
class WorkflowLogCleanupGroup:
    run_id: str
    paths: list[Path]

    def latest_mtime(self) -> float:
        return max(path.stat().st_mtime for path in self.paths)

    def total_size(self) -> int:
        return sum(path.stat().st_size for path in self.paths)

    def lock_path(self) -> Path | None:
        for path in self.paths:
            if path.name.endswith(".state.json.lock"):
                return path
        return None


def format_network_error(exc: urllib.error.URLError, *, url: str) -> str:
    reason = getattr(exc, "reason", exc)
    reason_text = str(reason)
    if isinstance(reason, OSError) and getattr(reason, "errno", None) == 8:
        return (
            f"{url} 无法解析域名。当前运行环境的 DNS/网络不可用，请在沙箱外重新执行该命令。"
        )
    if "nodename nor servname provided" in reason_text or "name or service not known" in reason_text:
        return (
            f"{url} 无法解析域名。当前运行环境的 DNS/网络不可用，请在沙箱外重新执行该命令。"
        )
    if "network is unreachable" in reason_text.lower():
        return f"{url} 当前网络不可达，请在沙箱外重新执行该命令。"
    return f"{url} 请求失败: {reason_text}"


def should_retry_url_error(exc: urllib.error.URLError) -> bool:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, TimeoutError):
        return True
    reason_text = str(reason).lower()
    retry_markers = {
        "timed out",
        "timeout",
        "temporarily unavailable",
        "temporary failure",
        "connection reset",
        "connection aborted",
        "connection refused",
        "broken pipe",
        "eof occurred",
    }
    return any(marker in reason_text for marker in retry_markers)


def should_retry_http_error(method: str, exc: urllib.error.HTTPError) -> bool:
    return method.upper() in RETRYABLE_HTTP_METHODS and exc.code in TRANSIENT_HTTP_STATUS_CODES


def request_retry_sleep(attempt: int) -> None:
    time.sleep(REQUEST_RETRY_BASE_SECONDS * attempt)


def perform_json_request(
    method: str,
    url: str,
    *,
    base_url: str,
    cookie_header: str,
    timeout: float,
    context: ssl.SSLContext,
    json_body: Any = None,
    referer: str | None = None,
) -> Any:
    data, _, _ = perform_json_request_with_response_meta(
        method,
        url,
        base_url=base_url,
        cookie_header=cookie_header,
        timeout=timeout,
        context=context,
        json_body=json_body,
        referer=referer,
    )
    return data


def perform_json_request_with_response_meta(
    method: str,
    url: str,
    *,
    base_url: str,
    cookie_header: str,
    timeout: float,
    context: ssl.SSLContext,
    json_body: Any = None,
    referer: str | None = None,
) -> tuple[Any, Any, str]:
    body = None
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Cookie": cookie_header,
        "User-Agent": BROWSER_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
        headers["Origin"] = base_url.rstrip("/")
    if referer:
        headers["Referer"] = referer

    current_cookie_header = cookie_header
    bootstrap_applied = False
    method_upper = method.upper()
    for attempt in range(1, REQUEST_MAX_ATTEMPTS + 1):
        headers["Cookie"] = current_cookie_header
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                final_url = response.geturl()
                raw_bytes = response.read()
                encoding = (response.headers.get("Content-Encoding") or "").lower()
                if "gzip" in encoding:
                    raw_bytes = gzip.decompress(raw_bytes)
                elif "deflate" in encoding:
                    raw_bytes = zlib.decompress(raw_bytes)

                raw_text = raw_bytes.decode("utf-8", errors="replace")
                if final_url.startswith(f"{base_url.rstrip('/')}/login") or "<!DOCTYPE html" in raw_text[:200]:
                    raise RuntimeError(f"CRP auth appears expired. Read {AUTH_DOC_PATH}.")
                if not raw_text.strip():
                    bootstrap_updates = {
                        key: value
                        for key, value in parse_set_cookie_values(response.headers).items()
                        if key in BOOTSTRAP_COOKIE_NAMES
                    }
                    if method_upper in RETRYABLE_HTTP_METHODS and not bootstrap_applied and bootstrap_updates:
                        current_cookie_header = merge_cookie_header(current_cookie_header, bootstrap_updates)
                        bootstrap_applied = True
                        continue
                    return None, response.headers, current_cookie_header
                try:
                    return json.loads(raw_text), response.headers, current_cookie_header
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"{method} {url} returned non-JSON content. Read {AUTH_DOC_PATH} and refresh auth."
                    ) from exc
        except urllib.error.HTTPError as exc:
            if should_retry_http_error(method_upper, exc) and attempt < REQUEST_MAX_ATTEMPTS:
                request_retry_sleep(attempt)
                continue
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            if method_upper in RETRYABLE_HTTP_METHODS and should_retry_url_error(exc) and attempt < REQUEST_MAX_ATTEMPTS:
                request_retry_sleep(attempt)
                continue
            raise RuntimeError(format_network_error(exc, url=url)) from exc
    raise RuntimeError(f"{method} {url} failed after {REQUEST_MAX_ATTEMPTS} attempts")


def parse_set_cookie_values(headers: Any) -> dict[str, str]:
    values: dict[str, str] = {}
    get_all = getattr(headers, "get_all", None)
    raw_values = get_all("Set-Cookie") if callable(get_all) else None
    if raw_values is None:
        single = headers.get("Set-Cookie")
        raw_values = [single] if single else []
    for raw in raw_values:
        if not raw:
            continue
        pair = str(raw).split(";", 1)[0].strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        name = name.strip()
        if name:
            values[name] = value.strip()
    return values


def merge_cookie_header(cookie_header: str, updates: dict[str, str]) -> str:
    cookies: dict[str, str] = {}
    order: list[str] = []
    for item in cookie_header.split(";"):
        part = item.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        if name not in cookies:
            order.append(name)
        cookies[name] = value.strip()
    for name, value in updates.items():
        if name not in cookies:
            order.append(name)
        cookies[name] = value
    return "; ".join(f"{name}={cookies[name]}" for name in order)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def json_dumps(payload: Any, *, pretty: bool | None = None) -> str:
    use_pretty = JSON_PRETTY if pretty is None else pretty
    if use_pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def print_json(payload: Any) -> None:
    print(json_dumps(payload), flush=True)


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "...(truncated)"


def truncate_long_text_fields(value: Any, *, limit: int, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            item_key: truncate_long_text_fields(item_value, limit=limit, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [truncate_long_text_fields(item, limit=limit, key=key) for item in value]
    if isinstance(value, str) and key in LONG_TEXT_FIELDS:
        return truncate_text(value, limit)
    return value


def compact_qa_candidates(payload: dict[str, Any], *, limit: int = QA_CANDIDATE_LIMIT) -> dict[str, Any]:
    if "qa_candidates" not in payload:
        return payload
    compact = dict(payload)
    candidates = compact.get("qa_candidates")
    if not isinstance(candidates, list):
        return compact
    candidate_count = int(compact.get("qa_candidate_count") or len(candidates))
    omitted = max(0, candidate_count - limit)
    compact["qa_candidate_count"] = candidate_count
    compact["qa_candidates"] = candidates[:limit]
    if omitted:
        compact["qa_candidates_omitted"] = omitted
    else:
        compact.pop("qa_candidates_omitted", None)
    return compact


def workflow_error_code(entry: dict[str, Any]) -> str | None:
    step = entry.get("step")
    original_error = str(entry.get("error") or "")
    if step == "workflow-failed" and original_error and is_auth_error(RuntimeError(original_error)):
        return "auth_expired"
    original_error_lower = original_error.lower()
    if step == "workflow-failed" and (
        "parameter" in original_error_lower
        or "req_" in original_error_lower
        or "mod_" in original_error_lower
        or ("requirement" in original_error_lower and ("ambiguous" in original_error_lower or "not found" in original_error_lower or "did not match" in original_error_lower))
        or ("module" in original_error_lower and ("ambiguous" in original_error_lower or "not found" in original_error_lower or "did not match" in original_error_lower))
    ):
        return "parameter_error"
    if step == "workflow-blocked":
        stage = entry.get("stage")
        if stage == "build":
            return "active_build"
        if stage == "release":
            return "active_release"
        return "workflow_blocked"
    return {
        "build-failed": "build_failed",
        "build-timeout": "build_timeout",
        "release-failed": "release_failed",
        "release-timeout": "release_timeout",
        "workflow-failed": "workflow_failed",
        "workflow-parameter-failed": "parameter_error",
        "build-conflict": "active_build",
        "release-conflict": "active_release",
    }.get(str(step))


def compact_release_package_status(package: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "package_id": package.get("package_id") or package.get("id"),
        "business": package.get("business"),
        "status": package.get("status") or package.get("zops_job_status"),
        "duration": package.get("duration"),
        "url": package.get("url") or package.get("release_url") or package.get("ali_url"),
        "result": truncate_text(str(package.get("result")), COMPACT_TEXT_LIMIT) if package.get("result") else None,
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def compact_workflow_stdout(entry: dict[str, Any]) -> dict[str, Any]:
    if entry.get("step") == "workflow-started":
        return {"run_id": entry.get("run_id"), "stage": "started"}
    drop_keys = {"ts", "command", "run_id", "log_path", "step", "expected"}
    payload = {key: value for key, value in entry.items() if key not in drop_keys}
    error_code = workflow_error_code(entry)
    if error_code:
        original_error = payload.get("error")
        payload["error"] = error_code
        if entry.get("step") == "workflow-failed" and original_error:
            payload["reason"] = original_error
        payload.pop("message", None)
    if entry.get("step") == "workflow-test":
        payload = {"stage": "test", **payload}
    if str(entry.get("step") or "").endswith("-timeout"):
        payload["status"] = "timeout"
    if payload.get("stage") == "done":
        payload.pop("eta", None)
    if "target_module_names" in payload:
        payload["target_modules"] = payload.pop("target_module_names")
    if "packages" in payload and isinstance(payload["packages"], list):
        payload["packages"] = [
            compact_release_package_status(package)
            for package in payload["packages"]
            if isinstance(package, dict)
        ]
    payload = compact_qa_candidates(payload)
    payload = truncate_long_text_fields(payload, limit=COMPACT_TEXT_LIMIT)
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def workflow_log_dir() -> Path:
    return WORKFLOW_LOG_DIR


def workflow_state_path(run_id: str) -> Path:
    return workflow_log_dir() / f"{run_id}.state.json"


def workflow_lock_path(state_path: Path) -> Path:
    return state_path.with_name(state_path.name + ".lock")


def workflow_run_id_from_state_path(path: Path) -> str:
    name = path.name
    if name.endswith(".state.json"):
        return name[: -len(".state.json")] or generate_workflow_run_id()
    return path.stem or generate_workflow_run_id()


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_workflow_state_lock(state_path: Path, logger: WorkflowRunLogger) -> Path | None:
    lock_path = workflow_lock_path(state_path)
    while True:
        try:
            ensure_parent(lock_path)
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = {
                    "pid": os.getpid(),
                    "run_id": logger.run_id,
                    "created_at": now_iso(),
                }
                os.write(fd, (json_dumps(payload, pretty=True) + "\n").encode("utf-8"))
            finally:
                os.close(fd)
            return lock_path
        except FileExistsError:
            pass
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = int(payload.get("pid") or 0)
        except Exception:
            pid = 0
        if process_is_alive(pid):
            logger.log(
                {
                    "step": "workflow-resume-locked",
                    "status": "locked",
                    "pid": pid,
                }
            )
            return None
        lock_path.unlink(missing_ok=True)


def release_workflow_state_lock(lock_path: Path | None) -> None:
    if lock_path is not None:
        lock_path.unlink(missing_ok=True)


def generate_workflow_run_id() -> str:
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{os.getpid()}-{secrets.token_hex(2)}"


class WorkflowRunLogger:
    def __init__(self, command: str, run_id: str | None = None, *, stdout_enabled: bool = True) -> None:
        self.command = command
        self.run_id = run_id or generate_workflow_run_id()
        self.stdout_enabled = stdout_enabled
        self.log_dir = workflow_log_dir()
        ensure_directory(self.log_dir)
        self.log_path = self.log_dir / f"{self.run_id}.jsonl"

    def _compose_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "ts": now_iso(),
            "run_id": self.run_id,
        }
        entry.update(payload)
        return entry

    def _append_entry(self, entry: dict[str, Any]) -> None:
        ensure_parent(self.log_path)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json_dumps(entry) + "\n")

    def log(self, payload: dict[str, Any], *, stdout: bool = False) -> dict[str, Any]:
        entry = self._compose_entry(payload)
        self._append_entry(entry)
        if stdout and self.stdout_enabled:
            print_json(compact_workflow_stdout(entry))
        return entry

    def log_stdout(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.log(payload, stdout=True)


def list_workflow_log_paths() -> list[Path]:
    log_dir = workflow_log_dir()
    if not log_dir.exists():
        return []
    paths = [path for path in log_dir.glob("*.jsonl") if path.is_file()]
    return sorted(paths, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)


def workflow_cleanup_run_id_from_path(path: Path) -> str | None:
    for suffix in WORKFLOW_LOG_CLEANUP_SUFFIXES:
        if path.name.endswith(suffix):
            run_id = path.name[: -len(suffix)]
            return run_id or None
    return None


def list_workflow_log_cleanup_groups() -> list[WorkflowLogCleanupGroup]:
    log_dir = workflow_log_dir()
    if not log_dir.exists():
        return []
    paths_by_run_id: dict[str, list[Path]] = {}
    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        run_id = workflow_cleanup_run_id_from_path(path)
        if run_id is None:
            continue
        paths_by_run_id.setdefault(run_id, []).append(path)
    groups = [
        WorkflowLogCleanupGroup(run_id=run_id, paths=sorted(paths, key=lambda item: item.name))
        for run_id, paths in paths_by_run_id.items()
    ]
    return sorted(groups, key=lambda group: (group.latest_mtime(), group.run_id), reverse=True)


def workflow_cleanup_lock_pid(lock_path: Path) -> int:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        return int(payload.get("pid") or 0)
    except Exception:
        return 0


def workflow_cleanup_group_is_locked(group: WorkflowLogCleanupGroup) -> bool:
    lock_path = group.lock_path()
    if lock_path is None:
        return False
    return process_is_alive(workflow_cleanup_lock_pid(lock_path))


def cleanup_workflow_logs(*, days: int, keep: int, dry_run: bool) -> dict[str, Any]:
    cutoff = time.time() - max(0, days) * 24 * 60 * 60
    keep_count = max(0, keep)
    groups = list_workflow_log_cleanup_groups()
    selected: list[WorkflowLogCleanupGroup] = []
    skipped_locked = 0
    for index, group in enumerate(groups):
        if index < keep_count or group.latest_mtime() >= cutoff:
            continue
        if workflow_cleanup_group_is_locked(group):
            skipped_locked += 1
            continue
        selected.append(group)

    run_count = len(selected)
    file_count = sum(len(group.paths) for group in selected)
    byte_count = sum(group.total_size() for group in selected)
    if not dry_run:
        for group in selected:
            for path in group.paths:
                path.unlink()

    key = "would_delete" if dry_run else "deleted"
    return {
        key: {
            "runs": run_count,
            "files": file_count,
            "bytes": byte_count,
        },
        "skipped_locked": skipped_locked,
    }


def cleanup_workflow_logs_silently() -> None:
    try:
        cleanup_workflow_logs(days=14, keep=50, dry_run=False)
    except Exception:
        pass


def latest_workflow_log_path() -> Path | None:
    paths = list_workflow_log_paths()
    return paths[0] if paths else None


def resolve_workflow_log_path(run_id: str | None) -> Path:
    if run_id:
        path = workflow_log_dir() / f"{run_id}.jsonl"
        if not path.exists():
            raise RuntimeError(f"Workflow log not found for run_id={run_id}")
        return path
    latest = latest_workflow_log_path()
    if latest is None:
        raise RuntimeError(f"No workflow logs found in {workflow_log_dir()}")
    return latest


def summarize_workflow_log(path: Path) -> dict[str, Any]:
    stat = path.stat()
    status = summarize_workflow_log_status(path)
    payload = {
        "run_id": path.stem,
        "status": status.get("status"),
        "stage": status.get("stage"),
        "error": status.get("error"),
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
        "size_bytes": stat.st_size,
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


COMPACT_WORKFLOW_EVENT_FIELDS = {
    "step",
    "stage",
    "status",
    "action",
    "query",
    "eta",
    "next",
    "target_module_names",
    "module_names",
    "test_id",
    "build",
    "release",
    "build_id",
    "build_ids_by_module",
    "build_id_binding",
    "create_build_response",
    "release_id",
    "module_name",
    "percentage",
    "description",
    "url",
    "conflicts",
    "release_check",
    "last_statuses",
    "blocked",
    "timeout",
}


def load_workflow_log_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def compact_workflow_event(entry: dict[str, Any]) -> dict[str, Any]:
    compact = {key: entry[key] for key in COMPACT_WORKFLOW_EVENT_FIELDS if key in entry}
    error_code = workflow_error_code(entry)
    if error_code:
        original_error = entry.get("error")
        compact["error"] = error_code
        if error_code == "auth_expired":
            compact["next"] = entry.get("next") or AUTH_REFRESH_NEXT
        if entry.get("step") == "workflow-failed" and original_error:
            compact["reason"] = original_error
        compact.pop("message", None)
        if error_code == "auth_expired":
            compact.pop("reason", None)
    if "target_module_names" in compact:
        compact["target_modules"] = compact.pop("target_module_names")
    if "module_names" in compact and "target_modules" not in compact:
        compact["target_modules"] = compact.pop("module_names")
    else:
        compact.pop("module_names", None)
    if "packages" in entry and isinstance(entry["packages"], list):
        compact["packages"] = [
            compact_release_package_status(package)
            for package in entry["packages"]
            if isinstance(package, dict)
        ]
    if "missing_module_names" in entry:
        compact["missing_module_names"] = entry["missing_module_names"]
    if "error" in entry and not error_code:
        compact["error"] = entry["error"]
    if "err" in entry:
        compact["err"] = entry["err"]
    if "resolved_modules" in entry:
        compact["resolved_modules"] = entry["resolved_modules"]
    if "module_candidates" in entry:
        compact["module_candidates"] = entry["module_candidates"]
    if "requirement_candidates" in entry:
        compact["requirement_candidates"] = entry["requirement_candidates"]
    if "qa_candidate_count" in entry:
        compact["qa_candidate_count"] = entry["qa_candidate_count"]
    if "qa_candidates" in entry:
        compact["qa_candidates"] = entry["qa_candidates"]
    compact = compact_qa_candidates(compact)
    compact = truncate_long_text_fields(compact, limit=COMPACT_TEXT_LIMIT)
    if compact.get("step") in {"auth-required", "workflow-started"} and "error" not in compact:
        return {}
    if compact.get("error") == "auth_expired":
        compact.pop("step", None)
    return {key: value for key, value in compact.items() if value is not None and value != ""}


def workflow_entry_error(entry: dict[str, Any]) -> str | None:
    error_code = workflow_error_code(entry)
    if error_code:
        return error_code
    if "error" not in entry:
        return None
    error = entry.get("error")
    if error is None or error == "":
        return "workflow_failed"
    error_text = str(error).lower()
    if "parameter" in error_text or "req_" in error_text or "mod_" in error_text:
        return "parameter_error"
    if "requirement" in error_text and ("ambiguous" in error_text or "not found" in error_text):
        return "parameter_error"
    if "module" in error_text and ("ambiguous" in error_text or "not found" in error_text):
        return "parameter_error"
    return str(error)


def summarize_workflow_log_status(path: Path) -> dict[str, Any]:
    entries = load_workflow_log_entries(path)
    last = entries[-1] if entries else {}
    last_stage = next((entry for entry in reversed(entries) if entry.get("stage")), {})
    specific_failure_steps = {
        "build-failed",
        "build-timeout",
        "release-failed",
        "release-timeout",
    }
    generic_failure_steps = {
        "workflow-failed",
        "workflow-parameter-failed",
        "workflow-blocked",
        "build-conflict",
        "release-conflict",
    }
    step_failure = next((
        entry
        for entry in reversed(entries)
        if entry.get("step") in specific_failure_steps
    ), {})
    if not step_failure:
        step_failure = next((
            entry
            for entry in reversed(entries)
            if entry.get("step") in generic_failure_steps
        ), {})
    error_failure = next((entry for entry in reversed(entries) if "error" in entry), {})
    failure = step_failure or error_failure
    done = next((entry for entry in reversed(entries) if entry.get("step") == "workflow-stage" and entry.get("stage") == "done"), {})
    status = "done" if done else "failed" if failure else "running"
    if failure:
        status = "failed"
    status_entry = failure or done or last
    payload = {
        "run_id": path.stem,
        "status": status,
        "stage": last_stage.get("stage") or status_entry.get("stage"),
        "eta": status_entry.get("eta") or last_stage.get("eta"),
        "error": workflow_entry_error(failure) if failure else None,
        "next": AUTH_REFRESH_NEXT if workflow_entry_error(failure) == "auth_expired" else status_entry.get("next"),
    }
    for key in ["target_module_names", "module_names", "test_id", "build_id", "release_id", "build_id_binding"]:
        value = next((entry.get(key) for entry in reversed(entries) if entry.get(key) is not None and entry.get(key) != ""), None)
        if value is not None and value != "":
            payload["target_modules" if key in {"target_module_names", "module_names"} else key] = value
    if failure:
        failure_payload = compact_workflow_event(failure)
        for key in [
            "err",
            "reason",
            "query",
            "module_name",
            "percentage",
            "description",
            "url",
            "conflicts",
            "release_check",
            "last_statuses",
            "packages",
            "resolved_modules",
            "module_candidates",
            "requirement_candidates",
            "qa_candidate_count",
            "qa_candidates",
            "qa_candidates_omitted",
        ]:
            value = failure_payload.get(key)
            if value is not None and value != "" and payload.get(key) != value:
                payload[key] = value
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def workflow_log_has_done(logger: WorkflowRunLogger) -> bool:
    if not logger.log_path.exists():
        return False
    return any(
        entry.get("step") == "workflow-stage" and entry.get("stage") == "done"
        for entry in load_workflow_log_entries(logger.log_path)
    )


def compact_workflow_events(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    waiting: dict[str, Any] | None = None
    for entry in entries:
        event = compact_workflow_event(entry)
        if not event:
            continue
        step = event.get("step")
        if step in {"build-waiting", "release-waiting"}:
            if waiting is not None and waiting.get("step") == step:
                waiting["count"] = int(waiting.get("count") or 1) + 1
                waiting["last_eta"] = event.get("eta")
                continue
            if waiting is not None:
                compacted.append(waiting)
            waiting = {
                "step": step,
                "stage": event.get("stage"),
                "count": 1,
                "first_eta": event.get("eta"),
                "last_eta": event.get("eta"),
            }
            continue
        if waiting is not None:
            compacted.append(waiting)
            waiting = None
        compacted.append(event)
    if waiting is not None:
        compacted.append(waiting)
    return compacted


def read_json_arg(value: str) -> Any:
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)


def load_metrics_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"builds": {}, "releases": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json_dumps(payload, pretty=True) + "\n", encoding="utf-8")


def workflow_resume_context_from_deploy_context(context: WorkflowDeployContext) -> WorkflowResumeContext:
    return WorkflowResumeContext(
        requirement_id=context.targets.requirement_id,
        modules=[
            {
                "name": module.get("name"),
                "scm_url": module.get("scm_url"),
                "release_type": module.get("release_type", "java"),
            }
            for module in context.targets.modules
        ],
        module_names=list(context.targets.module_names),
        businesses=list(context.targets.businesses),
        change_contents=list(context.targets.change_contents),
        baseline_build_id=context.preflight.baseline_build_id,
        build_seconds=context.expectations.build_seconds,
        release_seconds=context.expectations.release_seconds,
    )


def workflow_resume_context_to_json(context: WorkflowResumeContext) -> dict[str, Any]:
    return {
        "requirement_id": context.requirement_id,
        "modules": context.modules,
        "module_names": context.module_names,
        "businesses": context.businesses,
        "change_contents": context.change_contents,
        "baseline_build_id": context.baseline_build_id,
        "build_seconds": context.build_seconds,
        "release_seconds": context.release_seconds,
    }


def workflow_resume_context_from_json(payload: dict[str, Any]) -> WorkflowResumeContext:
    return WorkflowResumeContext(
        requirement_id=int(payload["requirement_id"]),
        modules=list(payload["modules"]),
        module_names=list(payload["module_names"]),
        businesses=list(payload["businesses"]),
        change_contents=list(payload["change_contents"]),
        baseline_build_id=int(payload["baseline_build_id"]),
        build_seconds=payload.get("build_seconds"),
        release_seconds=payload.get("release_seconds"),
    )


def workflow_args_to_json(args: argparse.Namespace) -> dict[str, Any]:
    keys = [
        "base_url",
        "storage_state",
        "auth_file",
        "metrics_file",
        "http_timeout",
        "git_branch",
        "build_timeout",
        "release_timeout",
        "min_poll_interval",
        "max_poll_interval",
    ]
    return {key: getattr(args, key, None) for key in keys}


def save_workflow_resume_state(
    path: Path,
    *,
    run_id: str,
    args: argparse.Namespace,
    context: WorkflowResumeContext,
    state: WorkflowExecutionState,
) -> None:
    write_json_file(
        path,
        {
            "run_id": run_id,
            "args": workflow_args_to_json(args),
            "context": workflow_resume_context_to_json(context),
            "state": workflow_execution_state_to_json(state),
        },
    )


def load_workflow_resume_state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def workflow_execution_state_to_json(state: WorkflowExecutionState) -> dict[str, Any]:
    return {
        "test_id": state.test_id,
        "build_results": state.build_results,
        "build_ids_by_module": state.build_ids_by_module,
        "build_id_binding": state.build_id_binding,
        "release_id": state.release_id,
        "release_started": state.release_started,
        "update_image_started": state.update_image_started,
        "image_updated": state.image_updated,
        "done": state.done,
    }


def workflow_execution_state_from_json(payload: dict[str, Any]) -> WorkflowExecutionState:
    return WorkflowExecutionState(
        test_id=payload.get("test_id"),
        build_results=payload.get("build_results") or {},
        build_ids_by_module={
            str(key): int(value)
            for key, value in (payload.get("build_ids_by_module") or {}).items()
            if value not in {None, ""}
        },
        build_id_binding=payload.get("build_id_binding"),
        release_id=payload.get("release_id"),
        release_started=bool(payload.get("release_started")),
        update_image_started=bool(payload.get("update_image_started")),
        image_updated=bool(payload.get("image_updated")),
        done=bool(payload.get("done")),
    )


def save_metrics_cache(path: Path, metrics: dict[str, Any]) -> None:
    write_json_file(path, metrics)


def milliseconds_to_seconds(value: Any) -> float | None:
    if value in {None, "", 0, "0"}:
        return None
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return None


def format_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    total = max(0, int(round(value)))
    minutes, seconds = divmod(total, 60)
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def update_metric_history(metrics: dict[str, Any], category: str, key: str, duration_seconds: float) -> None:
    bucket = metrics.setdefault(category, {})
    entry = bucket.setdefault(key, {"samples": [], "avg_seconds": None, "last_seconds": None, "updated_at": None})
    samples = entry.setdefault("samples", [])
    samples.append(round(duration_seconds, 3))
    del samples[:-10]
    entry["last_seconds"] = round(duration_seconds, 3)
    entry["avg_seconds"] = round(sum(samples) / len(samples), 3)
    entry["updated_at"] = now_iso()


def build_estimate_from_metrics(metrics: dict[str, Any], category: str, keys: list[str]) -> float | None:
    bucket = metrics.get(category, {})
    for key in keys:
        entry = bucket.get(key) or {}
        value = entry.get("avg_seconds") or entry.get("last_seconds")
        if value:
            return float(value)
    values = []
    for item in bucket.values():
        value = item.get("avg_seconds") or item.get("last_seconds")
        if value:
            values.append(float(value))
    return average(values)


def compute_poll_sleep(elapsed_seconds: float, expected_seconds: float | None, min_interval: int, max_interval: int) -> int:
    if expected_seconds is None:
        return max_interval
    remaining = expected_seconds - elapsed_seconds
    if remaining <= 0:
        return min_interval
    if remaining <= max_interval * 2:
        return min_interval
    if remaining <= max_interval * 4:
        return min(max_interval, max(min_interval, int(max_interval / 2)))
    return max_interval


def maybe_prompt_on_slow_step(
    *,
    step_name: str,
    elapsed_seconds: float,
    expected_seconds: float | None,
    prompted: bool,
    no_prompt: bool,
    logger: WorkflowRunLogger | None = None,
) -> bool:
    if prompted or expected_seconds is None:
        return prompted
    if elapsed_seconds < max(expected_seconds * 1.8, expected_seconds + 60):
        return prompted
    if no_prompt or not sys.stdin.isatty():
        payload = {
            "step": f"{step_name.lower()}-slow",
            "stage": step_name,
            "expected": format_seconds(expected_seconds),
            "eta": format_seconds(None if expected_seconds is None else max(0, expected_seconds - elapsed_seconds)),
            "auto_continue": True,
        }
        if logger is not None:
            logger.log(payload)
        else:
            print_json(payload)
        return True
    answer = input(
        f"{step_name} 已等待 {format_seconds(elapsed_seconds)}，超过平时的 {format_seconds(expected_seconds)}。是否继续等待？[Y/n] "
    ).strip().lower()
    if answer in {"n", "no"}:
        raise RuntimeError(f"{step_name} exceeded the usual duration and was stopped by the user")
    return True


class CrpClient:
    def __init__(
        self,
        base_url: str,
        storage_state_path: str | Path,
        auth_file_path: str | Path,
        timeout: float = 30.0,
        create_auth_template: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.storage_state_path = Path(storage_state_path)
        self.auth_file_path = Path(auth_file_path)
        self.timeout = timeout
        self.cookie_header = resolve_cookie_header(
            self.storage_state_path,
            self.auth_file_path,
            create_template=create_auth_template,
        )
        self.context = ssl.create_default_context()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        query: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> Any:
        url = self.base_url + path
        if query:
            clean_query = {key: value for key, value in query.items() if value is not None}
            url += "?" + urllib.parse.urlencode(clean_query)
        data, _, current_cookie_header = perform_json_request_with_response_meta(
            method,
            url,
            base_url=self.base_url,
            cookie_header=self.cookie_header,
            timeout=self.timeout,
            context=self.context,
            json_body=json_body,
            referer=referer,
        )
        self.cookie_header = current_cookie_header
        return data

    def list_assigned_requirements(self, *, offset: int, limit: int) -> Any:
        return self._request(
            "GET",
            "/api/my/assigned_requirements",
            query={"offset": offset, "limit": limit},
            referer=f"{self.base_url}/workbench",
        )

    def get_builds(self, requirement_id: int, *, page: int, pagesize: int) -> Any:
        return self._request(
            "GET",
            f"/api/requirements/{requirement_id}/builds",
            query={"page": page, "pagesize": pagesize},
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_requirement_tests(self, requirement_id: int) -> Any:
        return self._request(
            "GET",
            f"/api/requirements/{requirement_id}/tests",
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_test(self, test_id: int, *, requirement_id: int | None = None) -> Any:
        referer = None
        if requirement_id is not None:
            referer = f"{self.base_url}/requirement/detail/{requirement_id}"
        return self._request("GET", f"/api/tests/{test_id}", referer=referer)

    def get_requirement_releases(self, requirement_id: int) -> Any:
        return self._request(
            "GET",
            f"/api/requirements/{requirement_id}/releases",
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_release_calendar(self, requirement_id: int) -> Any:
        return self._request(
            "GET",
            "/api/onduty/calendar/list",
            query={"requirement_id": requirement_id},
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_requirement(self, requirement_id: int) -> Any:
        return self._request(
            "GET",
            f"/api/requirements/{requirement_id}",
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_projects(self, *, requirement_id: int | None = None) -> Any:
        referer = f"{self.base_url}/"
        if requirement_id is not None:
            referer = f"{self.base_url}/requirement/detail/{requirement_id}"
        return self._request("GET", "/api/projects", referer=referer)

    def get_project_modules(self, project_id: int) -> Any:
        return perform_json_request(
            "GET",
            CMDB_PROJECT_MODULES_URL_TEMPLATE.format(project_id=project_id),
            base_url=CMDB_BASE_URL,
            cookie_header="",
            timeout=self.timeout,
            context=self.context,
            referer=f"{self.base_url}/",
        )

    def create_build(self, requirement_id: int, payload: list[dict[str, Any]]) -> Any:
        return self._request(
            "POST",
            f"/api/requirements/{requirement_id}/build_module",
            json_body=payload,
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def get_repo(self, requirement_id: int, module_name: str, *, env: str) -> Any:
        return self._request(
            "GET",
            "/api/requirements/repo",
            query={
                "module_name": module_name,
                "env": env,
                "requirement_id": requirement_id,
            },
            referer=f"{self.base_url}/deploy/mission-form?requirement_id={requirement_id}&env={env}",
        )

    def create_test(self, requirement_id: int, payload: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            f"/api/requirements/{requirement_id}/tests",
            json_body=payload,
            referer=f"{self.base_url}/requirement/detail/{requirement_id}",
        )

    def create_release(self, test_id: int, payload: dict[str, Any], *, requirement_id: int | None = None, env: str = "test") -> Any:
        referer = None
        if requirement_id is not None:
            referer = f"{self.base_url}/deploy/mission-form?requirement_id={requirement_id}&env={env}"
        return self._request(
            "POST",
            f"/api/tests/{test_id}/releases",
            json_body=payload,
            referer=referer,
        )

    def get_release(self, release_id: int) -> Any:
        return self._request(
            "GET",
            f"/api/releases/{release_id}",
            referer=f"{self.base_url}/deploy/mission/{release_id}",
        )

    def update_image(self, payload: list[dict[str, Any]], *, release_id: int | None = None) -> Any:
        referer = None
        if release_id is not None:
            referer = f"{self.base_url}/deploy/mission/{release_id}"
        return self._request(
            "POST",
            "/api/k8s/update_image",
            json_body=payload,
            referer=referer,
        )


def build_client(
    args: argparse.Namespace,
) -> CrpClient:
    return CrpClient(
        args.base_url,
        args.storage_state,
        args.auth_file,
        timeout=args.http_timeout,
        create_auth_template=True,
    )


def validate_auth(client: CrpClient) -> None:
    client.list_assigned_requirements(offset=1, limit=1)


def is_auth_error(exc: Exception) -> bool:
    message = str(exc).lower()
    patterns = [
        "auth",
        "login",
        "cookie",
        "storage state not found",
        "no crp cookies",
    ]
    return any(pattern in message for pattern in patterns)


def emit_auth_required(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    logger = getattr(args, "workflow_run_logger", None)
    if logger is not None and getattr(args, "command", "") in {"workflow-deploy-test", "_workflow-deploy-test-resume"}:
        logger.log_stdout(payload)
        return
    print_json(payload)


def ensure_auth(args: argparse.Namespace) -> CrpClient:
    try:
        client = build_client(args)
        validate_auth(client)
        return client
    except Exception as exc:
        if not is_auth_error(exc):
            raise
        payload = build_auth_help_payload(
            base_url=args.base_url,
            auth_file=args.auth_file,
            reason=f"CRP auth invalid: {exc}",
        )
        emit_auth_required(args, payload)
        raise AuthRequiredError(payload) from exc


def emit_dry_run(*, method: str, path: str, base_url: str, query: dict[str, Any] | None = None, referer: str | None = None, json_body: Any = None) -> None:
    payload = {
        "method": method,
        "url": base_url.rstrip("/") + path,
        "query": query or {},
        "referer": referer,
        "json_body": json_body,
    }
    print_json(payload)


def unique_modules(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for module in modules:
        name = module.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(module)
    return result


def module_business_name(module_name: str) -> str:
    return module_name.rsplit("/", 1)[-1]


def has_module_namespace(module_name: str) -> bool:
    return "/" in str(module_name or "").strip()


def normalize_match_text(value: str) -> str:
    return re.sub(r"[\s_\-/]+", "", str(value or "")).casefold()


def normalize_module_name_part(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "")).casefold()


def normalized_full_module_parts(module_name: str) -> list[str]:
    text = str(module_name or "").strip()
    if "/" not in text:
        return []
    return [normalize_module_name_part(part) for part in text.split("/")]


def contains_match_candidates(query: str, candidates: list[str]) -> list[str]:
    wanted = normalize_match_text(query)
    exact_matches = [candidate for candidate in candidates if normalize_match_text(candidate) == wanted]
    if exact_matches:
        return exact_matches
    return [candidate for candidate in candidates if wanted in normalize_match_text(candidate)]


def parse_requirement_app_names(requirement: dict[str, Any]) -> list[str]:
    names: list[str] = []
    raw_apps = str(requirement.get("apps") or "")
    for item in raw_apps.split(","):
        name = item.strip()
        if name and name not in names:
            names.append(name)
    for field in ("backend_apps", "frontend_apps"):
        raw = str(requirement.get(field) or "")
        for item in raw.split(","):
            name = item.strip()
            if name and name not in names:
                names.append(name)
    return names


def parse_requirement_product_ids(requirement: dict[str, Any]) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for item in str(requirement.get("product_id") or "").split(","):
        text = item.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


def limited_candidate_names(values: list[str], *, max_length: int | None = None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        name = compact_text(text, max_length=max_length) if max_length is not None else text
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= PARAMETER_CANDIDATE_LIMIT:
            break
    return names


def summarize_requirement_parameter_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": compact_text(item.get("title") or item.get("name"), max_length=100),
        "apps": limited_candidate_names(parse_requirement_app_names(item), max_length=100),
    }


def build_requirement_parameter_payload(err: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "err": err,
        "requirement_candidates": [
            summarize_requirement_parameter_candidate(item)
            for item in candidates[:PARAMETER_CANDIDATE_LIMIT]
        ],
    }


def extract_cmdb_module_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def normalize_release_type(value: Any) -> str:
    text = str(value or "java").strip().lower()
    mapping = {
        "java": "java",
        "react": "react",
        "vue": "vue",
        "nodejs": "nodejs",
        "node": "nodejs",
        "go": "go",
    }
    return mapping.get(text, text or "java")


class RequirementModuleResolver:
    def __init__(self, client: CrpClient, requirement: dict[str, Any]) -> None:
        self.client = client
        self.requirement = requirement
        self.requirement_modules = unique_modules(requirement.get("modules") or [])
        self.requirement_module_by_name = {
            str(module.get("name")): module
            for module in self.requirement_modules
            if module.get("name")
        }
        self.app_names = parse_requirement_app_names(requirement)
        self.product_ids = parse_requirement_product_ids(requirement)
        self._test_module_names: list[str] | None = None
        self._cmdb_modules: list[dict[str, Any]] | None = None
        self._cmdb_module_by_name: dict[str, dict[str, Any]] | None = None

    def test_module_names(self) -> list[str]:
        if self._test_module_names is None:
            payload = self.client.get_requirement_tests(int(self.requirement["id"]))
            names: list[str] = []
            seen: set[str] = set()
            for item in extract_items(payload):
                for module in item.get("modules") or []:
                    name = str(module.get("name") or "").strip()
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)
            self._test_module_names = names
        return self._test_module_names

    def cmdb_modules(self) -> list[dict[str, Any]]:
        if self._cmdb_modules is None:
            modules: list[dict[str, Any]] = []
            seen: set[str] = set()
            for project_id in self.product_ids:
                payload = self.client.get_project_modules(project_id)
                for item in extract_cmdb_module_items(payload):
                    name = str(item.get("name") or "").strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    modules.append(item)
            self._cmdb_modules = modules
        if self._cmdb_module_by_name is None:
            self._cmdb_module_by_name = {
                str(item.get("name")): item
                for item in (self._cmdb_modules or [])
                if item.get("name")
            }
        return self._cmdb_modules

    def cmdb_module_by_name(self) -> dict[str, dict[str, Any]]:
        self.cmdb_modules()
        return self._cmdb_module_by_name or {}

    def query_variants(self, requested_name: str) -> list[str]:
        variants: list[str] = []
        seen: set[str] = set()
        for value in (requested_name, module_business_name(requested_name)):
            text = str(value or "").strip()
            normalized = normalize_match_text(text)
            if not text or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            variants.append(text)
        return variants

    def match_full_module_candidates(self, requested_name: str, candidates: list[str]) -> list[str]:
        requested_parts = normalized_full_module_parts(requested_name)
        if not requested_parts:
            return []
        return [
            candidate
            for candidate in candidates
            if normalized_full_module_parts(candidate) == requested_parts
        ]

    def match_candidates(
        self,
        requested_name: str,
        candidates: list[str],
        *,
        allow_business_fallback: bool = True,
    ) -> list[str]:
        full_matches = self.match_full_module_candidates(requested_name, candidates)
        if full_matches:
            return full_matches
        if has_module_namespace(requested_name) and not allow_business_fallback:
            return []

        matches: list[str] = []
        seen: set[str] = set()
        for query in self.query_variants(requested_name):
            for candidate in contains_match_candidates(query, candidates):
                if candidate in seen:
                    continue
                seen.add(candidate)
                matches.append(candidate)
        return matches

    def match_cmdb_modules_by_full_name(self, requested_name: str) -> list[str]:
        return self.match_full_module_candidates(
            requested_name,
            [str(item.get("name") or "") for item in self.cmdb_modules() if item.get("name")],
        )

    def match_cmdb_modules_by_business(self, requested_name: str) -> list[str]:
        wanted_values = [normalize_match_text(item) for item in self.query_variants(requested_name)]
        exact_matches: list[str] = []
        partial_matches: list[str] = []
        exact_seen: set[str] = set()
        partial_seen: set[str] = set()
        for item in self.cmdb_modules():
            full_name = str(item.get("name") or "").strip()
            if not full_name:
                continue
            business_name = module_business_name(full_name)
            normalized_business = normalize_match_text(business_name)
            if normalized_business in wanted_values:
                if full_name not in exact_seen:
                    exact_seen.add(full_name)
                    exact_matches.append(full_name)
                continue
            if any(value and value in normalized_business for value in wanted_values):
                if full_name not in partial_seen:
                    partial_seen.add(full_name)
                    partial_matches.append(full_name)
        return exact_matches or partial_matches

    def raise_module_parameter_error(
        self,
        err: str,
        requested_name: str,
        candidates: list[str],
        resolved_modules: list[ResolvedModule] | None,
    ) -> None:
        raise WorkflowParameterError(
            {
                "err": err,
                "resolved_modules": [item.full_name for item in (resolved_modules or [])],
                "module_candidates": {
                    str(requested_name): limited_candidate_names(candidates),
                },
            }
        )

    def build_resolved_module(
        self,
        *,
        requested_name: str,
        full_name: str,
        source: str,
        short_name: str,
        compact_errors: bool,
        resolved_modules: list[ResolvedModule] | None,
        meta_missing_candidates: list[str],
    ) -> ResolvedModule:
        try:
            module = self.build_module_payload(full_name)
        except RuntimeError:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_meta_missing",
                    requested_name,
                    meta_missing_candidates,
                    resolved_modules,
                )
            raise
        return ResolvedModule(
            requested_name=requested_name,
            full_name=full_name,
            source=source,
            short_name=short_name,
            module=module,
        )

    def build_module_payload(self, full_name: str) -> dict[str, Any]:
        requirement_module = self.requirement_module_by_name.get(full_name)
        if requirement_module is not None:
            module = dict(requirement_module)
            if not str(module.get("scm_url") or "").strip():
                raise RuntimeError(f"Resolved module {full_name} is missing scm_url metadata in requirement.modules")
            return module
        cmdb_module = self.cmdb_module_by_name().get(full_name)
        if cmdb_module is None:
            raise RuntimeError(f"Resolved module {full_name} has no metadata in requirement.modules or CMDB")
        scm_url = str(cmdb_module.get("git") or cmdb_module.get("scm_url") or "").strip()
        if not scm_url:
            raise RuntimeError(f"Resolved module {full_name} is missing git/scm metadata in CMDB")
        return {
            "name": full_name,
            "scm_url": scm_url,
            "release_type": normalize_release_type(cmdb_module.get("release_type")),
        }

    def resolve_one(
        self,
        requested_name: str,
        *,
        compact_errors: bool = False,
        resolved_modules: list[ResolvedModule] | None = None,
    ) -> ResolvedModule:
        requirement_matches = self.match_candidates(
            requested_name,
            [str(module.get("name") or "") for module in self.requirement_modules if module.get("name")],
            allow_business_fallback=False,
        )
        if len(requirement_matches) == 1:
            full_name = requirement_matches[0]
            return self.build_resolved_module(
                requested_name=requested_name,
                full_name=full_name,
                source="requirement-modules",
                short_name=module_business_name(full_name),
                compact_errors=compact_errors,
                resolved_modules=resolved_modules,
                meta_missing_candidates=[full_name],
            )
        if len(requirement_matches) > 1:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_ambiguous",
                    requested_name,
                    requirement_matches,
                    resolved_modules,
                )
            raise RuntimeError(
                f"Module parameter {requested_name} is ambiguous in requirement modules. "
                f"This is a parameter issue. Matches: {', '.join(requirement_matches)}"
            )

        test_matches = self.match_candidates(
            requested_name,
            self.test_module_names(),
            allow_business_fallback=False,
        )
        if len(test_matches) == 1:
            full_name = test_matches[0]
            return self.build_resolved_module(
                requested_name=requested_name,
                full_name=full_name,
                source="test-modules",
                short_name=module_business_name(full_name),
                compact_errors=compact_errors,
                resolved_modules=resolved_modules,
                meta_missing_candidates=[full_name],
            )
        if len(test_matches) > 1:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_ambiguous",
                    requested_name,
                    test_matches,
                    resolved_modules,
                )
            raise RuntimeError(
                f"Module parameter {requested_name} is ambiguous in existing test modules. "
                f"This is a parameter issue. Matches: {', '.join(test_matches)}"
            )

        if has_module_namespace(requested_name):
            app_matches = self.match_full_module_candidates(requested_name, self.app_names)
            if not app_matches:
                short_app_names = [name for name in self.app_names if not has_module_namespace(name)]
                requested_business = normalize_match_text(module_business_name(requested_name))
                app_matches = [
                    name
                    for name in short_app_names
                    if normalize_match_text(name) == requested_business
                ]
        else:
            app_matches = self.match_candidates(requested_name, self.app_names)
        if not app_matches:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_not_found",
                    requested_name,
                    self.app_names,
                    resolved_modules,
                )
            raise RuntimeError(
                f"Module parameter {requested_name} did not match this requirement. "
                "This is a parameter issue. You can pass a full module name, a business name, or a unique fragment. "
                f"Available apps: {', '.join(self.app_names) or '(empty)'}"
            )
        if len(app_matches) > 1:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_ambiguous",
                    requested_name,
                    app_matches,
                    resolved_modules,
                )
            raise RuntimeError(
                f"Module parameter {requested_name} is ambiguous in requirement apps. "
                f"This is a parameter issue. Matches: {', '.join(app_matches)}"
            )

        short_name = app_matches[0]
        cmdb_matches = self.match_cmdb_modules_by_full_name(requested_name)
        if not cmdb_matches and not has_module_namespace(requested_name):
            cmdb_matches = self.match_cmdb_modules_by_business(short_name)
        if not cmdb_matches:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_meta_missing",
                    requested_name,
                    [short_name],
                    resolved_modules,
                )
            raise RuntimeError(
                f"Requirement app {short_name} matched, but CRP could not resolve it to a full module name from CMDB. "
                f"This is usually a project/module metadata issue. Try: scripts/crp-deploy search-modules "
                f"--requirement-id {self.requirement['id']} --module-name {short_name}"
            )
        if len(cmdb_matches) > 1:
            if compact_errors:
                self.raise_module_parameter_error(
                    "mod_ambiguous",
                    requested_name,
                    cmdb_matches,
                    resolved_modules,
                )
            raise RuntimeError(
                f"Module parameter {requested_name} matched requirement app {short_name}, "
                f"but multiple CMDB modules are still possible. This is a parameter issue. "
                f"Matches: {', '.join(cmdb_matches)}"
            )
        full_name = cmdb_matches[0]
        return self.build_resolved_module(
            requested_name=requested_name,
            full_name=full_name,
            source="cmdb-project-modules",
            short_name=short_name,
            compact_errors=compact_errors,
            resolved_modules=resolved_modules,
            meta_missing_candidates=[short_name],
        )

    def resolve_many(
        self,
        requested_names: list[str],
        *,
        compact_errors: bool = False,
    ) -> list[ResolvedModule]:
        resolved: list[ResolvedModule] = []
        seen: set[str] = set()
        for requested_name in requested_names:
            item = self.resolve_one(
                requested_name,
                compact_errors=compact_errors,
                resolved_modules=resolved,
            )
            if item.full_name in seen:
                continue
            seen.add(item.full_name)
            resolved.append(item)
        return resolved


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "list", "rows", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_items(value)
            if nested:
                return nested
    return []


def compact_text(value: Any, *, max_length: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def command_result(args: argparse.Namespace, *, summary: Any, raw: Any) -> None:
    print_json(raw if getattr(args, "raw", False) else summary)


def summarize_assigned_requirements(payload: Any) -> dict[str, Any]:
    items = extract_items(payload)
    return {
        "items": [
            {
                "requirement_id": item.get("id") or item.get("requirement_id"),
                "title": compact_text(item.get("title") or item.get("name")),
                "apps": compact_text(item.get("apps"), max_length=200),
                "create_time": item.get("create_time"),
                "update_time": item.get("update_time"),
            }
            for item in items
        ],
        "count": len(items),
    }


def summarize_requirement(payload: dict[str, Any]) -> dict[str, Any]:
    modules = unique_modules(payload.get("modules") or [])
    return {
        "requirement_id": payload.get("id"),
        "title": compact_text(payload.get("title")),
        "status": payload.get("status"),
        "project_id": payload.get("project_id"),
        "module_count": len(modules),
        "modules": [
            {
                "name": module.get("name"),
                "scm_url": module.get("scm_url"),
                "release_type": module.get("release_type", "java"),
            }
            for module in modules
        ],
    }


def summarize_resolved_modules(items: list[ResolvedModule]) -> dict[str, Any]:
    return {
        "items": [
            {
                "requested_name": item.requested_name,
                "module_name": item.full_name,
                "app_name": item.short_name,
                "source": item.source,
                "scm_url": item.module.get("scm_url"),
                "release_type": item.module.get("release_type"),
            }
            for item in items
        ],
        "count": len(items),
    }


def summarize_builds(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("data") or []
    return {
        "items": [
            {
                "build_id": int(item["id"]),
                "module_name": item.get("module_name"),
                "branch": item.get("branch"),
                "status": item.get("status"),
                "build_number": item.get("build_number"),
                "duration": format_seconds(milliseconds_to_seconds(item.get("duration"))),
                "url": item.get("url"),
            }
            for item in items
        ],
        "count": len(items),
    }


def summarize_tests(payload: Any) -> dict[str, Any]:
    items = extract_items(payload)
    return {
        "items": [
            {
                "test_id": int(item["id"]),
                "name": item.get("name"),
                "status": item.get("status"),
                "assignee": item.get("assignee"),
                "module_names": [module.get("name") for module in (item.get("modules") or []) if module.get("name")],
            }
            for item in items
        ],
        "count": len(items),
    }


def summarize_test_detail(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_id": payload.get("id"),
        "name": payload.get("name"),
        "status": payload.get("status"),
        "assignee": payload.get("assignee"),
        "module_names": sorted(module_names_from_test_detail(payload)),
        "change_contents": [
            change.get("modified_content")
            for change in (payload.get("changes") or [])
            if change.get("modified_content")
        ],
    }


def summarize_releases(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") or {}
    return {
        env: [
            {
                "release_id": int(item["id"]),
                "status": item.get("status"),
                "name": item.get("name"),
                "created_at": item.get("created_at"),
            }
            for item in items
        ]
        for env, items in data.items()
        if isinstance(items, list)
    }


def summarize_calendar(payload: Any) -> dict[str, Any]:
    items = extract_items(payload)
    return {
        "items": [
            {
                "id": item.get("id"),
                "title": compact_text(item.get("title") or item.get("name")),
                "date": item.get("date") or item.get("release_date"),
                "status": item.get("status"),
            }
            for item in items
        ],
        "count": len(items),
    }


def summarize_repo(payload: dict[str, Any]) -> dict[str, Any]:
    tags = payload.get("tags") or []
    return {
        "module_name": payload.get("module_name"),
        "tag_count": len(tags),
        "tags": [
            {
                "build_id": tag.get("build_id"),
                "build_number": tag.get("build_number"),
                "url": tag.get("url"),
                "created_at": tag.get("created_at"),
            }
            for tag in tags[:10]
        ],
    }


def summarize_release_detail(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "release_id": payload.get("id"),
        "status": payload.get("status"),
        "packages": [
            {
                "package_id": package.get("id"),
                "business": package.get("business"),
                "release_type": package.get("release_type"),
                "zops_job_status": package.get("zops_job_status"),
                "release_url": package.get("release_url"),
                "duration": format_seconds(milliseconds_to_seconds(package.get("duration"))),
                "ali_url": package.get("ali_url"),
            }
            for package in (payload.get("packages") or [])
        ],
    }


def summarize_action_response(action: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"action": action, "result": payload}
    summary = {"action": action}
    for key in ("id", "test_id", "release_id", "build_id", "status", "message"):
        if key in payload:
            summary[key] = payload.get(key)
    if "data" in payload and isinstance(payload["data"], dict):
        for key in ("id", "test_id", "release_id", "build_id", "status", "message"):
            if key in payload["data"]:
                summary.setdefault(key, payload["data"].get(key))
    if len(summary) == 1:
        summary["keys"] = sorted(payload.keys())
    return summary


def iter_assigned_requirements(
    client: CrpClient,
    *,
    limit: int = 50,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for offset in range(1, max_pages + 1):
        payload = client.list_assigned_requirements(offset=offset, limit=limit)
        page_items = extract_items(payload)
        items.extend(page_items)
        if len(page_items) < limit:
            break
    return items


def resolve_assigned_requirement_item_by_name(client: CrpClient, requirement_name: str) -> dict[str, Any]:
    wanted = normalize_match_text(requirement_name)
    assigned = iter_assigned_requirements(client)
    matches = [
        item for item in assigned
        if wanted in normalize_match_text(str(item.get("title") or item.get("name") or ""))
    ]
    if not matches:
        raise WorkflowParameterError(build_requirement_parameter_payload("req_not_found", assigned))
    if len(matches) > 1:
        raise WorkflowParameterError(build_requirement_parameter_payload("req_ambiguous", matches))
    return matches[0]


def latest_build_id(builds: dict[str, Any]) -> int:
    items = builds.get("data") or []
    if not items:
        return 0
    return max(int(item["id"]) for item in items)


def build_release_detail_cache(
    client: CrpClient,
    releases: dict[str, Any],
    *,
    env: str,
) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    for item in (releases.get("data") or {}).get(env) or []:
        try:
            release_id = int(item["id"])
        except (TypeError, ValueError, KeyError):
            continue
        if release_id not in cache:
            cache[release_id] = client.get_release(release_id)
    return cache


def release_businesses(detail: dict[str, Any]) -> set[str]:
    return {
        str(package.get("business"))
        for package in (detail.get("packages") or [])
        if package.get("business")
    }


def build_release_duration_index(
    releases: dict[str, Any],
    release_detail_cache: dict[int, dict[str, Any]],
    *,
    env: str,
) -> dict[str, float]:
    duration_by_business: dict[str, float] = {}
    env_items = list((releases.get("data") or {}).get(env) or [])
    env_items.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
    for item in env_items:
        if str(item.get("status", "")).lower() not in {"released", "end"}:
            continue
        try:
            release_id = int(item["id"])
        except (TypeError, ValueError, KeyError):
            continue
        detail = release_detail_cache.get(release_id) or {}
        for package in detail.get("packages") or []:
            business = package.get("business")
            duration = milliseconds_to_seconds(package.get("duration"))
            if business and duration is not None and business not in duration_by_business:
                duration_by_business[str(business)] = duration
    return duration_by_business


def latest_success_build_for_module(builds: dict[str, Any], module_name: str, branch: str) -> dict[str, Any] | None:
    items = [
        item
        for item in (builds.get("data") or [])
        if item.get("module_name") == module_name
        and item.get("branch") == branch
        and item.get("status") == "success"
    ]
    if not items:
        return None
    items.sort(key=lambda item: int(item["id"]), reverse=True)
    return items[0]


def module_names_from_test_detail(test_detail: dict[str, Any]) -> set[str]:
    return {module.get("name") for module in (test_detail.get("modules") or []) if module.get("name")}


def test_module_payload(module: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "name": module["name"],
        "scm_url": module["scm_url"],
        "release_type": module.get("release_type", "java"),
    }
    app_version = module.get("app_version")
    if app_version not in {None, ""}:
        payload["app_version"] = str(app_version)
    return payload


def build_test_payload_for_modules(
    title: str,
    qa_assignee: str,
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "testing",
        "target_version": "",
        "name": "测试单",
        "assignee": [qa_assignee],
        "manager": "",
        "release_risk": "high",
        "release_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d 00:00:00"),
        "comment": "",
        "modules": [
            test_module_payload(module)
            for module in modules
        ],
        "changes": [
            {
                "modified_content": title,
                "test_key": "",
                "notes": "",
                "code_reviewer": "",
            },
            {},
        ],
        "perf_test": False,
        "perf_test_assignee": [],
        "sec_test": False,
        "sec_test_assignee": [],
        "email": "",
        "email_to": "",
        "build_module_id": "",
        "testcase": "",
    }


def extract_test_assignee_ids(test_detail: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in test_detail.get("assignee") or []:
        if isinstance(item, dict):
            assignee_id = str(item.get("id") or "").strip()
        else:
            assignee_id = str(item or "").strip()
        if assignee_id and assignee_id not in result:
            result.append(assignee_id)
    return result


def normalize_test_changes(test_detail: dict[str, Any], *, fallback_title: str) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for item in test_detail.get("changes") or []:
        if not isinstance(item, dict):
            continue
        change = {
            "modified_content": str(item.get("modified_content") or "").strip(),
            "test_key": str(item.get("test_key") or "").strip(),
            "notes": str(item.get("notes") or "").strip(),
            "code_reviewer": str(item.get("code_reviewer") or "").strip(),
        }
        if any(change.values()):
            changes.append(change)
    if changes:
        return changes
    return [
        {
            "modified_content": fallback_title,
            "test_key": "",
            "notes": "",
            "code_reviewer": "",
        }
    ]


def merge_test_modules(existing_test_detail: dict[str, Any], added_modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for module in list(existing_test_detail.get("modules") or []) + list(added_modules):
        if not isinstance(module, dict):
            continue
        name = str(module.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(test_module_payload(module))
    return merged


def build_updated_test_payload(
    test_detail: dict[str, Any],
    added_modules: list[dict[str, Any]],
    *,
    fallback_title: str,
) -> dict[str, Any]:
    test_id = str(test_detail.get("id") or "").strip()
    if not test_id:
        raise RuntimeError("Existing test detail is missing id")
    assignee_ids = extract_test_assignee_ids(test_detail)
    if not assignee_ids:
        raise RuntimeError(f"Existing test {test_id} has no assignee")
    return {
        "id": test_id,
        "status": str(test_detail.get("status") or "testing"),
        "target_version": str(test_detail.get("target_version") or ""),
        "name": str(test_detail.get("name") or "测试单"),
        "assignee": assignee_ids,
        "manager": str(test_detail.get("manager") or ""),
        "release_risk": str(test_detail.get("release_risk") or "high"),
        "release_date": str(test_detail.get("release_date") or ""),
        "comment": str(test_detail.get("comment") or ""),
        "modules": merge_test_modules(test_detail, added_modules),
        "changes": normalize_test_changes(test_detail, fallback_title=fallback_title),
        "perf_test": bool(test_detail.get("perf_test")),
        "perf_test_assignee": test_detail.get("perf_test_assignee") or [],
        "sec_test": bool(test_detail.get("sec_test")),
        "sec_test_assignee": test_detail.get("sec_test_assignee") or [],
        "email": str(test_detail.get("email") or ""),
        "email_to": str(test_detail.get("email_to") or ""),
        "build_module_id": str(test_detail.get("build_module_id") or ""),
        "testcase": str(test_detail.get("testcase") or ""),
    }


def resolve_release_url(client: CrpClient, requirement_id: int, module_name: str, build_id: int, env: str) -> str:
    repo = client.get_repo(requirement_id, module_name, env=env)
    for tag in repo.get("tags") or []:
        if str(tag.get("build_id")) == str(build_id):
            return tag["url"]
    raise RuntimeError(f"Could not resolve release url for build {build_id}")


def choose_existing_test(tests: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tests:
        return None
    tests.sort(key=lambda item: int(item["id"]), reverse=True)
    return tests[0]


def build_release_payload_for_packages(
    requirement_id: int,
    change_contents: list[str],
    packages: list[dict[str, Any]],
    *,
    status: str = "releasing",
    remarks: str = "",
    others: str = "",
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "status": status,
        "remarks": remarks,
        "change_contents": [{"content": content, "point": ""} for content in change_contents],
        "db_contents": [],
        "nginx_contents": [],
        "others": others,
        "packages": packages,
    }


def detect_active_builds(builds: dict[str, Any], module_names: set[str], branch: str) -> list[dict[str, Any]]:
    latest_by_module: dict[str, dict[str, Any]] = {}
    for item in builds.get("data") or []:
        module_name = item.get("module_name")
        if module_name not in module_names or item.get("branch") != branch:
            continue
        previous = latest_by_module.get(str(module_name))
        if previous is None or int(item.get("id") or 0) > int(previous.get("id") or 0):
            latest_by_module[str(module_name)] = item
    conflicts = [
        item
        for item in latest_by_module.values()
        if str(item.get("status", "")).lower() in ACTIVE_BUILD_STATUSES
    ]
    conflicts.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
    return conflicts


def detect_active_releases(
    releases: dict[str, Any],
    release_detail_cache: dict[int, dict[str, Any]],
    target_businesses: set[str],
    *,
    env: str,
) -> list[dict[str, Any]]:
    conflicts_by_release: dict[int, dict[str, Any]] = {}
    env_items = list((releases.get("data") or {}).get(env) or [])
    env_items.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
    unresolved = set(target_businesses)
    for item in env_items:
        if not unresolved:
            break
        try:
            release_id = int(item["id"])
        except (TypeError, ValueError, KeyError):
            continue
        detail = release_detail_cache.get(release_id)
        if detail is None:
            continue
        for package in (detail.get("packages") or []):
            business = package.get("business")
            if business not in unresolved:
                continue
            unresolved.remove(str(business))
            if str(package.get("zops_job_status", "")).lower() not in ACTIVE_RELEASE_STATUSES:
                continue
            conflict = conflicts_by_release.get(release_id)
            if conflict is None:
                conflict = {**detail, "packages": []}
                conflicts_by_release[release_id] = conflict
            conflict["packages"].append(package)
    conflicts = list(conflicts_by_release.values())
    conflicts.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
    return conflicts


def latest_release_duration_for_business(
    release_durations: dict[str, float],
    business: str,
) -> float | None:
    return release_durations.get(business)


def summarize_build_conflicts(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "step": "build-conflict",
        "message": "目标模块已有构建在进行中，工作流已停止。",
        "conflicts": [
            {
                "build_id": int(item["id"]),
                "module_name": item.get("module_name"),
                "status": item.get("status"),
                "build_number": item.get("build_number"),
            }
            for item in conflicts
        ],
    }


def summarize_release_conflicts(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "step": "release-conflict",
        "message": "目标模块已有测试环境部署在进行中，工作流已停止。",
        "conflicts": [
            {
                "release_id": int(item["id"]),
                "status": item.get("status"),
                "packages": [
                    {
                        "business": package.get("business"),
                        "zops_job_status": package.get("zops_job_status"),
                    }
                    for package in (item.get("packages") or [])
                ],
            }
            for item in conflicts
        ],
    }


def summarize_failed_build(build: dict[str, Any]) -> dict[str, Any]:
    description = str(build.get("description") or "").strip()
    payload = {
        "module_name": build.get("module_name"),
        "build_id": build.get("id"),
        "status": build.get("status"),
        "percentage": build.get("percentage"),
        "description": description,
        "url": build.get("url"),
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def summarize_release_package_status(package: dict[str, Any]) -> dict[str, Any]:
    result = str(package.get("result") or "").strip()
    payload = {
        "package_id": package.get("id"),
        "business": package.get("business"),
        "status": package.get("zops_job_status"),
        "result": result,
        "duration": package.get("duration"),
        "release_url": package.get("release_url"),
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def summarize_release_check(release: dict[str, Any]) -> str:
    release_check = release.get("release_check")
    if isinstance(release_check, dict):
        parts = [
            str(release_check.get("status") or "").strip(),
            str(release_check.get("msg") or release_check.get("message") or "").strip(),
        ]
        text = " ".join(part for part in parts if part)
        if text:
            return text
    if release_check not in {None, ""}:
        return str(release_check)
    return ""


def build_id_from_item(item: dict[str, Any]) -> int | None:
    value = item.get("build_id")
    if value in {None, ""}:
        value = item.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def module_name_from_build_item(item: dict[str, Any]) -> str | None:
    for key in ("module_name", "name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return None


def extract_build_response_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    items = [payload]
    for key in ("data", "items", "list", "rows", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            items.extend(extract_build_response_items(value))
    return items


def extract_created_build_ids_by_module(
    response: Any,
    target_module_names: list[str],
) -> dict[str, int]:
    module_names = set(target_module_names)
    result: dict[str, int] = {}
    for item in extract_build_response_items(response):
        build_id = build_id_from_item(item)
        if build_id is None:
            continue
        module_name = module_name_from_build_item(item)
        if module_name in module_names:
            result[str(module_name)] = build_id
            continue
        if module_name is None and len(target_module_names) == 1:
            result[target_module_names[0]] = build_id
    return result


def wait_for_new_success_builds(
    client: CrpClient,
    requirement_id: int,
    modules: list[dict[str, Any]],
    baseline_id: int,
    branch: str,
    timeout_seconds: int,
    min_interval: int,
    max_interval: int,
    expected_seconds: float | None,
    no_prompt_on_slow: bool,
    logger: WorkflowRunLogger | None = None,
    build_ids_by_module: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    module_names = {module["name"] for module in modules}
    expected_build_ids = build_ids_by_module or {}
    completed: dict[str, dict[str, Any]] = {}
    last_seen: dict[str, dict[str, Any]] = {}
    prompted = False
    last_report_at = 0.0
    query = f"scripts/crp-deploy list-builds --requirement-id {requirement_id} --page 1 --pagesize 20"
    while time.time() < deadline:
        builds = client.get_builds(requirement_id, page=1, pagesize=100)
        for build in builds.get("data") or []:
            build_id = int(build["id"])
            module_name = build.get("module_name")
            if module_name not in module_names:
                continue
            expected_build_id = expected_build_ids.get(str(module_name))
            if expected_build_id is not None:
                if build_id != expected_build_id:
                    continue
            elif build.get("branch") != branch or build_id <= baseline_id:
                continue
            previous = last_seen.get(module_name)
            if previous is None or build_id > int(previous.get("id", 0)):
                last_seen[module_name] = build
            status = str(build.get("status", "")).lower()
            if status in BUILD_SUCCESS_STATUSES:
                completed[module_name] = build
                continue
            if status in BUILD_FAILURE_STATUSES:
                summary = summarize_failed_build(build)
                payload = {
                    "step": "build-failed",
                    "stage": "build",
                    "message": "构建已进入失败状态。这通常是构建或代码问题，不是参数问题。",
                    "query": query,
                    **summary,
                }
                if logger is not None:
                    logger.log_stdout(payload)
                else:
                    print_json(payload)
                raise WorkflowReportedError(
                    f"workflow-deploy-test stopped in build stage: module {module_name} "
                    f"build_id={build_id} status={status} description={summary.get('description', '')} "
                    f"url={build.get('url')}. This is usually a build/code problem, not a parameter problem. "
                    f"Query current status with: {query}"
                )
        if len(completed) == len(module_names):
            return completed
        elapsed = timeout_seconds - max(0, deadline - time.time())
        if time.time() - last_report_at >= max_interval:
            payload = {
                "step": "build-waiting",
                "stage": "build",
                "expected": format_seconds(expected_seconds),
                "eta": format_seconds(None if expected_seconds is None else max(0, expected_seconds - elapsed)),
                "message": "waiting",
            }
            if logger is not None:
                logger.log(payload)
            else:
                print_json(payload)
            last_report_at = time.time()
        prompted = maybe_prompt_on_slow_step(
            step_name="build",
            elapsed_seconds=elapsed,
            expected_seconds=expected_seconds,
            prompted=prompted,
            no_prompt=no_prompt_on_slow,
            logger=logger,
        )
        remaining = deadline - time.time()
        if remaining <= 0:
            continue
        time.sleep(min(compute_poll_sleep(elapsed, expected_seconds, min_interval, max_interval), remaining))
    last_statuses = [summarize_failed_build(item) for item in last_seen.values()]
    payload = {
        "step": "build-timeout",
        "stage": "build",
        "message": (
            f"等待构建超过 {format_seconds(timeout_seconds)}，工作流已停止等待。"
            "CRP 上的构建可能仍在继续，可用 query 查看后续状态。"
        ),
        "query": query,
        "last_statuses": last_statuses,
    }
    if logger is not None:
        logger.log_stdout(payload)
    else:
        print_json(payload)
    raise WorkflowReportedError(
        f"workflow-deploy-test timed out in build stage after {format_seconds(timeout_seconds)}. "
        "The build may still be running in CRP. "
        f"Query current status with: {query}"
    )


def wait_for_release_with_progress(
    client: CrpClient,
    release_id: int,
    *,
    timeout_seconds: int,
    min_interval: int,
    max_interval: int,
    expected_seconds: float | None,
    no_prompt_on_slow: bool,
    logger: WorkflowRunLogger | None = None,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    prompted = False
    last_report_at = 0.0
    last_release: dict[str, Any] | None = None
    query = f"scripts/crp-deploy get-release --release-id {release_id}"
    while time.time() < deadline:
        release = client.get_release(release_id)
        last_release = release
        packages = release.get("packages") or []
        release_status = str(release.get("status", "")).lower()
        failed_packages = [
            package
            for package in packages
            if str(package.get("zops_job_status", "")).lower() in RELEASE_FAILURE_STATUSES
        ]
        if release_status in RELEASE_FAILURE_STATUSES or failed_packages:
            package_statuses = [summarize_release_package_status(package) for package in packages]
            release_check = summarize_release_check(release)
            payload = {
                "step": "release-failed",
                "stage": "release",
                "release_id": release_id,
                "status": release_status,
                "packages": package_statuses,
                "query": query,
            }
            if release_check:
                payload["release_check"] = release_check
            if logger is not None:
                logger.log_stdout(payload)
            else:
                print_json(payload)
            failed_statuses = [summarize_release_package_status(package) for package in failed_packages]
            reason = f" release_check={release_check}." if release_check else ""
            raise WorkflowReportedError(
                f"workflow-deploy-test stopped in release stage: release {release_id} status={release_status}."
                f"{reason} This is usually a release precondition or platform-state problem, not a module parameter problem. "
                f"failed_packages={failed_statuses}. Query current status with: {query}"
            )
        if release_status in RELEASE_SUCCESS_STATUSES:
            return release
        elapsed = timeout_seconds - max(0, deadline - time.time())
        if time.time() - last_report_at >= max_interval:
            payload = {
                "step": "release-waiting",
                "stage": "release",
                "expected": format_seconds(expected_seconds),
                "eta": format_seconds(None if expected_seconds is None else max(0, expected_seconds - elapsed)),
                "message": "waiting",
            }
            if logger is not None:
                logger.log(payload)
            else:
                print_json(payload)
            last_report_at = time.time()
        prompted = maybe_prompt_on_slow_step(
            step_name="release",
            elapsed_seconds=elapsed,
            expected_seconds=expected_seconds,
            prompted=prompted,
            no_prompt=no_prompt_on_slow,
            logger=logger,
        )
        remaining = deadline - time.time()
        if remaining <= 0:
            continue
        time.sleep(min(compute_poll_sleep(elapsed, expected_seconds, min_interval, max_interval), remaining))
    package_statuses = [
        summarize_release_package_status(package)
        for package in ((last_release or {}).get("packages") or [])
    ]
    payload = {
        "step": "release-timeout",
        "stage": "release",
        "release_id": release_id,
        "status": (last_release or {}).get("status"),
        "message": (
            f"等待部署超过 {format_seconds(timeout_seconds)}，工作流已停止等待。"
            "CRP 上的发布可能仍在继续，可用 query 查看后续状态。"
        ),
        "query": query,
        "packages": package_statuses,
    }
    if logger is not None:
        logger.log_stdout(payload)
    else:
        print_json(payload)
    raise WorkflowReportedError(
        f"workflow-deploy-test timed out in release stage for release {release_id} "
        f"after {format_seconds(timeout_seconds)}. The release may still be running in CRP. "
        f"Query current status with: {query}"
    )


def infer_build_expectation(
    *,
    builds: dict[str, Any],
    modules: list[dict[str, Any]],
    branch: str,
    metrics: dict[str, Any],
) -> float | None:
    module_estimates: list[float] = []
    for module in modules:
        recent = latest_success_build_for_module(builds, module["name"], branch)
        recent_duration = milliseconds_to_seconds((recent or {}).get("duration"))
        cached = build_estimate_from_metrics(metrics, "builds", [module["name"]])
        estimate = recent_duration or cached
        if estimate is not None:
            module_estimates.append(float(estimate))
    return max(module_estimates) if module_estimates else build_estimate_from_metrics(metrics, "builds", [])


def infer_release_expectation(
    *,
    release_durations: dict[str, float],
    businesses: list[str],
    metrics: dict[str, Any],
    env: str,
) -> float | None:
    estimates: list[float] = []
    for business in businesses:
        recent_duration = latest_release_duration_for_business(release_durations, business)
        cached = build_estimate_from_metrics(metrics, "releases", [f"{env}:{business}", business])
        estimate = recent_duration or cached
        if estimate is not None:
            estimates.append(float(estimate))
    return max(estimates) if estimates else build_estimate_from_metrics(metrics, "releases", [])


def command_list_assigned_requirements(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.list_assigned_requirements(offset=args.offset, limit=args.limit)
    command_result(args, summary=summarize_assigned_requirements(raw), raw=raw)


def command_get_requirement(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_requirement(args.requirement_id)
    command_result(args, summary=summarize_requirement(raw), raw=raw)


def command_search_modules(args: argparse.Namespace) -> None:
    client = build_client(args)
    requirement = client.get_requirement(args.requirement_id)
    resolver = RequirementModuleResolver(client, requirement)
    resolved = resolver.resolve_many(args.module_name)
    command_result(
        args,
        summary=summarize_resolved_modules(resolved),
        raw={
            "requirement_id": int(requirement["id"]),
            "items": [
                {
                    "requested_name": item.requested_name,
                    "module_name": item.full_name,
                    "app_name": item.short_name,
                    "source": item.source,
                    "module": item.module,
                }
                for item in resolved
            ],
        },
    )


def command_list_builds(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_builds(args.requirement_id, page=args.page, pagesize=args.pagesize)
    command_result(args, summary=summarize_builds(raw), raw=raw)


def command_list_tests(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_requirement_tests(args.requirement_id)
    command_result(args, summary=summarize_tests(raw), raw=raw)


def command_get_test(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_test(args.test_id, requirement_id=args.requirement_id)
    command_result(args, summary=summarize_test_detail(raw), raw=raw)


def command_list_releases(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_requirement_releases(args.requirement_id)
    command_result(args, summary=summarize_releases(raw), raw=raw)


def command_list_calendar(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_release_calendar(args.requirement_id)
    command_result(args, summary=summarize_calendar(raw), raw=raw)


def command_get_repo(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_repo(args.requirement_id, args.module_name, env=args.env)
    command_result(args, summary=summarize_repo(raw), raw=raw)


def build_modules_payload_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.payload_json:
        payload = read_json_arg(args.payload_json)
        if not isinstance(payload, list):
            raise RuntimeError("--payload-json for build-module must be a JSON array")
        return payload
    if args.module_json:
        payload = [read_json_arg(item) for item in args.module_json]
        if not all(isinstance(item, dict) for item in payload):
            raise RuntimeError("--module-json entries must be JSON objects")
        return payload
    required = ["module_name", "scm_url"]
    missing = [name for name in required if getattr(args, name) in {None, ""}]
    if missing:
        raise RuntimeError(
            "build-module requires either --payload-json/--module-json or "
            "--module-name + --scm-url"
        )
    return [
        {
            "name": args.module_name,
            "scm_url": args.scm_url,
            "gitbranch": args.git_branch,
            "env": args.env,
            "release_type": args.release_type,
        }
    ]


def command_build_module(args: argparse.Namespace) -> None:
    payload = build_modules_payload_from_args(args)
    referer = f"{args.base_url.rstrip('/')}/requirement/detail/{args.requirement_id}"
    if args.dry_run:
        emit_dry_run(
            method="POST",
            path=f"/api/requirements/{args.requirement_id}/build_module",
            base_url=args.base_url,
            referer=referer,
            json_body=payload,
        )
        return
    client = build_client(args)
    raw = client.create_build(args.requirement_id, payload)
    command_result(args, summary=summarize_action_response("build-module", raw), raw=raw)


def command_create_test(args: argparse.Namespace) -> None:
    if args.payload_json:
        payload = read_json_arg(args.payload_json)
    else:
        required = ["qa_assignee", "module_name", "scm_url"]
        missing = [name for name in required if getattr(args, name) in {None, ""}]
        if missing:
            raise RuntimeError(
                "create-test requires either --payload-json or "
                "--qa-assignee + --module-name + --scm-url"
            )
        payload = build_test_payload_for_modules(
            args.change_content or args.test_title,
            str(args.qa_assignee),
            [
                {
                    "name": args.module_name,
                    "scm_url": args.scm_url,
                    "release_type": args.release_type,
                }
            ],
        )
        if args.test_title:
            payload["name"] = args.test_title

    referer = f"{args.base_url.rstrip('/')}/requirement/detail/{args.requirement_id}"
    if args.dry_run:
        emit_dry_run(
            method="POST",
            path=f"/api/requirements/{args.requirement_id}/tests",
            base_url=args.base_url,
            referer=referer,
            json_body=payload,
        )
        return
    client = build_client(args)
    raw = client.create_test(args.requirement_id, payload)
    command_result(args, summary=summarize_action_response("create-test", raw), raw=raw)


def build_release_packages_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.package_json:
        packages = [read_json_arg(item) for item in args.package_json]
        if not all(isinstance(item, dict) for item in packages):
            raise RuntimeError("--package-json entries must be JSON objects")
        return packages
    required = ["business", "release_url"]
    missing = [name for name in required if getattr(args, name) in {None, ""}]
    if missing:
        raise RuntimeError(
            "create-release requires either --payload-json or "
            "--package-json or --business + --release-url"
        )
    return [
        {
            "business": args.business,
            "release_type": args.release_type,
            "env": args.env,
            "release_url": args.release_url,
            "is_wts": args.is_wts,
            "use_helm": args.use_helm,
        }
    ]


def build_release_create_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_json:
        payload = read_json_arg(args.payload_json)
        if not isinstance(payload, dict):
            raise RuntimeError("--payload-json for create-release must be a JSON object")
        return payload
    change_contents = [{"content": content, "point": ""} for content in (args.change_content or [])]
    if not change_contents:
        raise RuntimeError("create-release requires at least one --change-content when not using --payload-json")
    return {
        "requirement_id": args.requirement_id,
        "status": args.status,
        "remarks": args.remarks,
        "change_contents": change_contents,
        "db_contents": [],
        "nginx_contents": [],
        "others": args.others,
        "packages": build_release_packages_from_args(args),
    }


def command_create_release(args: argparse.Namespace) -> None:
    payload = build_release_create_payload(args)
    referer = (
        f"{args.base_url.rstrip('/')}/deploy/mission-form"
        f"?requirement_id={args.requirement_id}&env={args.env}"
    )
    if args.dry_run:
        emit_dry_run(
            method="POST",
            path=f"/api/tests/{args.test_id}/releases",
            base_url=args.base_url,
            referer=referer,
            json_body=payload,
        )
        return
    client = build_client(args)
    raw = client.create_release(
        args.test_id,
        payload,
        requirement_id=args.requirement_id,
        env=args.env,
    )
    command_result(args, summary=summarize_action_response("create-release", raw), raw=raw)


def command_get_release(args: argparse.Namespace) -> None:
    client = build_client(args)
    raw = client.get_release(args.release_id)
    command_result(args, summary=summarize_release_detail(raw), raw=raw)


def build_update_image_payload(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.payload_json:
        payload = read_json_arg(args.payload_json)
        if not isinstance(payload, list):
            raise RuntimeError("--payload-json for update-image must be a JSON array")
        return payload
    required = ["package_id", "svrname", "image_name"]
    missing = [name for name in required if getattr(args, name) in {None, ""}]
    if missing:
        raise RuntimeError(
            "update-image requires either --payload-json or "
            "--package-id + --svrname + --image-name"
        )
    return [
        {
            "release_id": args.release_id,
            "package_id": args.package_id,
            "svrname": args.svrname,
            "environ": args.environ,
            "image_name": args.image_name,
            "is_wts": str(args.is_wts),
            "env": args.env,
        }
    ]


def command_update_image(args: argparse.Namespace) -> None:
    payload = build_update_image_payload(args)
    referer = f"{args.base_url.rstrip('/')}/deploy/mission/{args.release_id}"
    if args.dry_run:
        emit_dry_run(
            method="POST",
            path="/api/k8s/update_image",
            base_url=args.base_url,
            referer=referer,
            json_body=payload,
        )
        return
    client = build_client(args)
    raw = client.update_image(payload, release_id=args.release_id)
    command_result(args, summary=summarize_action_response("update-image", raw), raw=raw)


def build_workflow_build_payload(modules: list[dict[str, Any]], git_branch: str) -> list[dict[str, Any]]:
    return [
        {
            "name": module["name"],
            "scm_url": module["scm_url"],
            "gitbranch": git_branch,
            "env": "test",
            "release_type": module.get("release_type", "java"),
        }
        for module in modules
    ]


def extract_project_qa_users(project_info: dict[str, Any]) -> list[dict[str, str]]:
    qa_users: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in (project_info.get("users") or {}).get("qa") or []:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("user_id") or "").strip()
        user_name = str(item.get("user_name") or item.get("name") or "").strip()
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        qa_users.append({"user_id": user_id, "user_name": user_name or user_id})
    return qa_users


def ensure_workflow_qa_assignee(
    client: CrpClient,
    requirement: dict[str, Any],
    args: argparse.Namespace,
    *,
    logger: WorkflowRunLogger | None = None,
) -> str:
    if args.qa_assignee:
        return str(args.qa_assignee)

    project_id_str = str(requirement.get("project_id", ""))
    if not project_id_str:
        raise RuntimeError(
            "The workflow needs to create a new test order, but the requirement has no project_id, "
            "so QA candidates cannot be loaded. Pass --qa-assignee explicitly."
        )
    requirement_id = requirement.get("id")
    requirement_id_int = int(requirement_id) if requirement_id not in {None, ""} else None
    projects_data = client.get_projects(requirement_id=requirement_id_int)
    projects_list = projects_data if isinstance(projects_data, list) else projects_data.get("data", [])
    project_info = next((p for p in projects_list if str(p.get("id")) == project_id_str), None)
    if not project_info:
        raise RuntimeError(
            f"The workflow needs to create a new test order, but project {project_id_str} "
            "was not found in /api/projects. Pass --qa-assignee explicitly or fix the project metadata."
        )
    qa_list = extract_project_qa_users(project_info)
    if not qa_list:
        raise RuntimeError(
            "The workflow needs to create a new test order, but the project has no available QA users. "
            "Configure QA in CRP or pass --qa-assignee explicitly."
        )

    if len(qa_list) == 1:
        args.qa_assignee = qa_list[0]["user_id"]
        payload = {
            "step": "auto-select-qa",
            "stage": "test",
            "qa": qa_list[0]["user_name"],
            "qa_user_id": args.qa_assignee,
        }
        if logger is not None:
            logger.log_stdout(payload)
        else:
            print_json(compact_workflow_stdout(payload))
        return str(args.qa_assignee)

    raise WorkflowParameterError(
        {
            "err": "qa_assignee_required",
            "qa_candidate_count": len(qa_list),
            "qa_candidates": qa_list,
            "next": "Pass --qa-assignee with one qa_candidates[].user_id, then rerun workflow-deploy-test.",
        }
    )


def combine_expected_seconds(*values: float | None) -> float | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return sum(known)


def emit_workflow_stage(
    stage: str,
    *,
    expected_seconds: float | None = None,
    eta_seconds: float | None = None,
    logger: WorkflowRunLogger | None = None,
    stdout: bool = True,
) -> None:
    if eta_seconds is None:
        eta_seconds = expected_seconds
    payload = {
        "step": "workflow-stage",
        "stage": stage,
        "expected": format_seconds(expected_seconds),
        "eta": format_seconds(eta_seconds),
    }
    if logger is not None:
        logger.log(payload, stdout=stdout)
    elif stdout:
        print_json(payload)
    else:
        return


def emit_workflow_blocker(
    stage: str,
    *,
    message: str,
    conflicts: list[dict[str, Any]],
    logger: WorkflowRunLogger | None = None,
) -> None:
    payload = {
        "step": "workflow-blocked",
        "stage": stage,
        "message": message,
        "conflicts": conflicts,
    }
    if logger is not None:
        logger.log_stdout(payload)
    else:
        print_json(payload)


def emit_workflow_started(logger: WorkflowRunLogger) -> None:
    logger.log_stdout({"step": "workflow-started"})


def emit_workflow_failed(
    args: argparse.Namespace,
    error: str,
    *,
    logger: WorkflowRunLogger | None = None,
) -> None:
    payload = {
        "step": "workflow-failed",
        "command": args.command,
        "error": error,
    }
    if logger is not None:
        logger.log_stdout(payload)
    else:
        print_json(payload)


def emit_workflow_test_action(
    action: str,
    *,
    test_id: int,
    target_module_names: list[str],
    logger: WorkflowRunLogger | None = None,
    missing_module_names: list[str] | None = None,
) -> None:
    payload = {
        "step": "workflow-test",
        "action": action,
        "test_id": test_id,
        "target_module_names": target_module_names,
    }
    if missing_module_names:
        payload["missing_module_names"] = missing_module_names
    if logger is not None:
        logger.log_stdout(payload)
    else:
        print_json(payload)


def emit_workflow_build_created(
    *,
    build_ids_by_module: dict[str, int],
    build_id_binding: str | None,
    create_build_response: Any,
    logger: WorkflowRunLogger | None = None,
) -> None:
    payload = {
        "step": "workflow-build",
        "stage": "build",
        "build_id_binding": build_id_binding,
        "build_ids_by_module": build_ids_by_module,
        "create_build_response": summarize_action_response("build-module", create_build_response),
    }
    if logger is not None:
        logger.log(payload)
    else:
        print_json(payload)


def resolve_workflow_targets(client: CrpClient, args: argparse.Namespace, requirement: dict[str, Any]) -> WorkflowTargets:
    requirement_id = int(requirement["id"])
    resolver = RequirementModuleResolver(client, requirement)
    resolved = resolver.resolve_many(args.module_name, compact_errors=True)
    modules = [item.module for item in resolved]
    override_scm_url = getattr(args, "scm_url", None)
    override_release_type = getattr(args, "release_type", None)
    if override_scm_url or override_release_type:
        if len(modules) != 1:
            raise RuntimeError("--scm-url/--release-type overrides only support a single target module")
        module = dict(modules[0])
        if override_scm_url:
            module["scm_url"] = override_scm_url
        if override_release_type:
            module["release_type"] = override_release_type
        modules = [module]
    return WorkflowTargets(
        requirement=requirement,
        requirement_id=requirement_id,
        modules=modules,
        module_names=[module["name"] for module in modules],
        businesses=[module["name"].split("/")[-1] for module in modules],
        change_contents=args.change_content or [requirement["title"]],
    )


def preflight_workflow_targets(
    client: CrpClient,
    args: argparse.Namespace,
    targets: WorkflowTargets,
    *,
    logger: WorkflowRunLogger | None = None,
) -> tuple[WorkflowPreflight, dict[str, Any], dict[str, Any], dict[int, dict[str, Any]]]:
    builds_before = client.get_builds(targets.requirement_id, page=1, pagesize=100)
    active_builds = detect_active_builds(builds_before, set(targets.module_names), args.git_branch)
    if active_builds:
        emit_workflow_blocker(
            "build",
            message="目标模块已有构建在进行中。这是平台状态阻断，不是参数问题。请等待现有 build 结束后重试。",
            conflicts=summarize_build_conflicts(active_builds)["conflicts"],
            logger=logger,
        )
        raise WorkflowReportedError(
            "workflow-deploy-test blocked before build: one or more target modules already have an active build. "
            "Wait for the existing build to finish and retry."
        )

    releases = client.get_requirement_releases(targets.requirement_id)
    release_detail_cache = build_release_detail_cache(client, releases, env="test")
    active_releases = detect_active_releases(
        releases,
        release_detail_cache,
        set(targets.businesses),
        env="test",
    )
    if active_releases:
        emit_workflow_blocker(
            "release",
            message="目标模块已有测试环境部署在进行中。这是平台状态阻断，不是参数问题。请等待现有 release 结束后重试。",
            conflicts=summarize_release_conflicts(active_releases)["conflicts"],
            logger=logger,
        )
        raise WorkflowReportedError(
            "workflow-deploy-test blocked before release: one or more target modules already have an active test release. "
            "Wait for the existing release to finish and retry."
        )

    tests = extract_items(client.get_requirement_tests(targets.requirement_id))
    chosen_test = choose_existing_test(tests)
    chosen_test_detail = None
    missing_test_modules: list[str] = []
    if chosen_test:
        chosen_test_detail = client.get_test(int(chosen_test["id"]), requirement_id=targets.requirement_id)
        existing_module_names = module_names_from_test_detail(chosen_test_detail)
        missing_test_modules = [name for name in targets.module_names if name not in existing_module_names]

    return (
        WorkflowPreflight(
            baseline_build_id=latest_build_id(builds_before),
            chosen_test=chosen_test,
            chosen_test_detail=chosen_test_detail,
            build_payload=build_workflow_build_payload(targets.modules, args.git_branch),
            missing_test_modules=missing_test_modules,
        ),
        builds_before,
        releases,
        release_detail_cache,
    )


def estimate_workflow_expectations(
    args: argparse.Namespace,
    metrics: dict[str, Any],
    targets: WorkflowTargets,
    *,
    builds_before: dict[str, Any],
    releases: dict[str, Any],
    release_detail_cache: dict[int, dict[str, Any]],
) -> WorkflowExpectations:
    build_expectation = infer_build_expectation(
        builds=builds_before,
        modules=targets.modules,
        branch=args.git_branch,
        metrics=metrics,
    )
    release_duration_index = build_release_duration_index(releases, release_detail_cache, env="test")
    release_expectation = infer_release_expectation(
        release_durations=release_duration_index,
        businesses=targets.businesses,
        metrics=metrics,
        env="test",
    )
    return WorkflowExpectations(build_seconds=build_expectation, release_seconds=release_expectation)


def collect_workflow_deploy_context(
    client: CrpClient,
    args: argparse.Namespace,
    metrics: dict[str, Any],
    *,
    logger: WorkflowRunLogger | None = None,
) -> WorkflowDeployContext:
    assigned_item = resolve_assigned_requirement_item_by_name(client, args.requirement_name)
    requirement = client.get_requirement(int(assigned_item["id"]))
    targets = resolve_workflow_targets(client, args, requirement)
    preflight, builds_before, releases, release_detail_cache = preflight_workflow_targets(
        client,
        args,
        targets,
        logger=logger,
    )
    expectations = estimate_workflow_expectations(
        args,
        metrics,
        targets,
        builds_before=builds_before,
        releases=releases,
        release_detail_cache=release_detail_cache,
    )
    return WorkflowDeployContext(
        targets=targets,
        expectations=expectations,
        preflight=preflight,
    )


def emit_workflow_plan(
    context: WorkflowDeployContext,
    args: argparse.Namespace,
    *,
    logger: WorkflowRunLogger | None = None,
) -> None:
    del args
    emit_workflow_stage(
        "preflight",
        expected_seconds=combine_expected_seconds(
            context.expectations.build_seconds,
            context.expectations.release_seconds,
        ),
        logger=logger,
    )


def ensure_workflow_test_id(
    client: CrpClient,
    context: WorkflowDeployContext,
    args: argparse.Namespace,
    *,
    logger: WorkflowRunLogger | None = None,
) -> int:
    chosen_test = context.preflight.chosen_test
    if chosen_test and not context.preflight.missing_test_modules:
        test_id = int(chosen_test["id"])
        emit_workflow_test_action(
            "reuse",
            test_id=test_id,
            target_module_names=context.targets.module_names,
            logger=logger,
        )
        return test_id
    if chosen_test and context.preflight.chosen_test_detail is not None:
        payload = build_updated_test_payload(
            context.preflight.chosen_test_detail,
            context.targets.modules,
            fallback_title=context.targets.requirement["title"],
        )
        response = client.create_test(context.targets.requirement_id, payload)
        test_id = int(response.get("test_id") or response.get("id") or chosen_test["id"])
        emit_workflow_test_action(
            "update-modules",
            test_id=test_id,
            target_module_names=context.targets.module_names,
            missing_module_names=context.preflight.missing_test_modules,
            logger=logger,
        )
        return test_id
    qa_assignee = ensure_workflow_qa_assignee(client, context.targets.requirement, args, logger=logger)
    test_payload = build_test_payload_for_modules(
        context.targets.requirement["title"],
        qa_assignee,
        context.targets.modules,
    )
    response = client.create_test(context.targets.requirement_id, test_payload)
    test_id = int(response["test_id"])
    emit_workflow_test_action(
        "create",
        test_id=test_id,
        target_module_names=context.targets.module_names,
        logger=logger,
    )
    return test_id


def preview_workflow_test_action(
    client: CrpClient,
    context: WorkflowDeployContext,
    args: argparse.Namespace,
    *,
    logger: WorkflowRunLogger | None = None,
) -> None:
    chosen_test = context.preflight.chosen_test
    if chosen_test and not context.preflight.missing_test_modules:
        emit_workflow_test_action(
            "reuse",
            test_id=int(chosen_test["id"]),
            target_module_names=context.targets.module_names,
            logger=logger,
        )
        return
    if chosen_test and context.preflight.chosen_test_detail is not None:
        emit_workflow_test_action(
            "update-modules",
            test_id=int(chosen_test["id"]),
            target_module_names=context.targets.module_names,
            missing_module_names=context.preflight.missing_test_modules,
            logger=logger,
        )
        return
    ensure_workflow_qa_assignee(client, context.targets.requirement, args, logger=logger)
    emit_workflow_test_action(
        "create",
        test_id=0,
        target_module_names=context.targets.module_names,
        logger=logger,
    )


def build_release_packages_for_workflow(
    client: CrpClient,
    context: WorkflowResumeContext,
    build_results: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for module in context.modules:
        module_name = module["name"]
        build = build_results[module_name]
        packages.append(
            {
                "business": module_name.split("/")[-1],
                "release_type": module.get("release_type", "java"),
                "env": "test",
                "release_url": resolve_release_url(
                    client,
                    context.requirement_id,
                    module_name,
                    int(build["id"]),
                    "test",
                ),
                "is_wts": 0,
                "use_helm": 0,
            }
        )
    return packages


def emit_workflow_release_created(
    *,
    release_id: int,
    logger: WorkflowRunLogger | None = None,
) -> None:
    payload = {
        "step": "workflow-release",
        "stage": "release",
        "release_id": release_id,
    }
    if logger is not None:
        logger.log(payload)
    else:
        print_json(payload)


def run_workflow_after_build_trigger(
    client: CrpClient,
    context: WorkflowResumeContext,
    args: argparse.Namespace,
    *,
    logger: WorkflowRunLogger,
    state_path: Path | None = None,
    state: WorkflowExecutionState | None = None,
) -> None:
    metrics_path = Path(args.metrics_file)
    metrics = load_metrics_cache(metrics_path)
    state = state or WorkflowExecutionState(test_id=int(args.workflow_test_id))
    if state.test_id is None:
        state.test_id = int(args.workflow_test_id)
    if state.done:
        if not workflow_log_has_done(logger):
            emit_workflow_stage("done", expected_seconds=0, eta_seconds=0, logger=logger)
        return

    def save_state() -> None:
        if state_path is not None:
            save_workflow_resume_state(
                state_path,
                run_id=logger.run_id,
                args=args,
                context=context,
                state=state,
            )

    if not state.build_results:
        state.build_results = wait_for_new_success_builds(
            client,
            context.requirement_id,
            context.modules,
            context.baseline_build_id,
            args.git_branch,
            args.build_timeout,
            args.min_poll_interval,
            args.max_poll_interval,
            context.build_seconds,
            True,
            logger=logger,
            build_ids_by_module=state.build_ids_by_module,
        )
        save_state()
        for module_name, build in state.build_results.items():
            duration_seconds = milliseconds_to_seconds(build.get("duration"))
            if duration_seconds is not None:
                update_metric_history(metrics, "builds", module_name, duration_seconds)
        save_metrics_cache(metrics_path, metrics)

    resolved_packages: list[dict[str, Any]] | None = None
    if state.release_id is None:
        if state.release_started:
            reason = (
                "workflow-deploy-test stopped before retrying create_release: previous create_release request was sent "
                "but release_id was not persisted. Check CRP requirement releases before resuming to avoid duplicate release."
            )
            emit_workflow_failed(args, reason, logger=logger)
            raise WorkflowReportedError(reason)
        resolved_packages = build_release_packages_for_workflow(client, context, state.build_results)
        release_payload = build_release_payload_for_packages(
            context.requirement_id,
            context.change_contents,
            resolved_packages,
        )
        state.release_started = True
        save_state()
        release_response = client.create_release(
            state.test_id,
            release_payload,
            requirement_id=context.requirement_id,
            env="test",
        )
        state.release_id = int(release_response["id"])
        emit_workflow_release_created(release_id=state.release_id, logger=logger)
        save_state()

    if resolved_packages is None:
        resolved_packages = build_release_packages_for_workflow(client, context, state.build_results)
    release_id = int(state.release_id)
    release_detail = client.get_release(release_id)
    packages = release_detail.get("packages") or []
    if not packages:
        raise RuntimeError(f"Release {release_id} has no packages")

    if not state.image_updated:
        if state.update_image_started:
            package_statuses = {
                str(package.get("zops_job_status") or package.get("status") or "").lower()
                for package in packages
            }
            release_status = str(release_detail.get("status") or "").lower()
            active_or_done = bool(
                (package_statuses & (ACTIVE_RELEASE_STATUSES | RELEASE_SUCCESS_STATUSES))
                or release_status in ACTIVE_RELEASE_STATUSES
                or release_status in RELEASE_SUCCESS_STATUSES
            )
            if active_or_done:
                state.image_updated = True
                save_state()
            else:
                reason = (
                    "workflow-deploy-test stopped before retrying update_image: previous update_image request was sent "
                    "but completion was not persisted, and release status does not prove it started. "
                    f"release_id={release_id}"
                )
                emit_workflow_failed(args, reason, logger=logger)
                raise WorkflowReportedError(reason)
        if state.image_updated:
            emit_workflow_stage("release", expected_seconds=context.release_seconds, logger=logger)
        else:
            state.update_image_started = True
            save_state()
            packages_by_business = {package["business"]: package for package in packages}
            update_payload = []
            for resolved in resolved_packages:
                business = resolved["business"]
                package = packages_by_business.get(business)
                if package is None:
                    raise RuntimeError(f"Release {release_id} missing package for business {business}")
                update_payload.append(
                    {
                        "release_id": release_id,
                        "package_id": package["id"],
                        "svrname": package["business"],
                        "environ": package["release_type"],
                        "image_name": package["release_url"],
                        "is_wts": str(package.get("is_wts", "0")),
                        "env": "test",
                    }
                )
            client.update_image(update_payload, release_id=release_id)
            state.image_updated = True
            save_state()

    emit_workflow_stage("release", expected_seconds=context.release_seconds, logger=logger)

    final_release = wait_for_release_with_progress(
        client,
        release_id,
        timeout_seconds=args.release_timeout,
        min_interval=args.min_poll_interval,
        max_interval=args.max_poll_interval,
        expected_seconds=context.release_seconds,
        no_prompt_on_slow=True,
        logger=logger,
    )
    for package in final_release.get("packages") or []:
        duration_seconds = milliseconds_to_seconds(package.get("duration"))
        if duration_seconds is not None:
            update_metric_history(metrics, "releases", f"test:{package['business']}", duration_seconds)
    save_metrics_cache(metrics_path, metrics)
    emit_workflow_stage("done", expected_seconds=0, eta_seconds=0, logger=logger)
    state.done = True
    save_state()


def start_workflow_resume_process(args: argparse.Namespace, state_path: Path) -> None:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--base-url",
        args.base_url,
        "--storage-state",
        str(args.storage_state),
        "--auth-file",
        str(args.auth_file),
        "--metrics-file",
        str(args.metrics_file),
        "--http-timeout",
        str(args.http_timeout),
        "_workflow-deploy-test-resume",
        "--state-file",
        str(state_path),
    ]
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def command_workflow_deploy_test(args: argparse.Namespace) -> None:
    cleanup_workflow_logs_silently()
    run_logger = WorkflowRunLogger(args.command)
    setattr(args, "workflow_run_logger", run_logger)
    emit_workflow_started(run_logger)

    metrics_path = Path(args.metrics_file)
    metrics = load_metrics_cache(metrics_path)
    client = ensure_auth(args)
    context = collect_workflow_deploy_context(client, args, metrics, logger=run_logger)
    emit_workflow_plan(context, args, logger=run_logger)
    if args.dry_run:
        preview_workflow_test_action(client, context, args, logger=run_logger)
        return

    state = WorkflowExecutionState()
    state.test_id = ensure_workflow_test_id(client, context, args, logger=run_logger)
    setattr(args, "workflow_test_id", state.test_id)

    state.create_build_response = client.create_build(context.targets.requirement_id, context.preflight.build_payload)
    state.build_ids_by_module = extract_created_build_ids_by_module(
        state.create_build_response,
        context.targets.module_names,
    )
    if len(state.build_ids_by_module) == len(context.targets.module_names):
        state.build_id_binding = "exact"
    elif state.build_ids_by_module:
        state.build_id_binding = "partial"
    else:
        state.build_id_binding = "baseline_fallback"
    emit_workflow_build_created(
        build_ids_by_module=state.build_ids_by_module,
        build_id_binding=state.build_id_binding,
        create_build_response=state.create_build_response,
        logger=run_logger,
    )
    emit_workflow_stage("build", expected_seconds=context.expectations.build_seconds, logger=run_logger)

    resume_context = workflow_resume_context_from_deploy_context(context)
    state_path = workflow_state_path(run_logger.run_id)
    save_workflow_resume_state(
        state_path,
        run_id=run_logger.run_id,
        args=args,
        context=resume_context,
        state=state,
    )
    if not args.wait:
        save_metrics_cache(metrics_path, metrics)
        start_workflow_resume_process(args, state_path)
        return

    run_workflow_after_build_trigger(
        client,
        resume_context,
        args,
        logger=run_logger,
        state_path=state_path,
        state=state,
    )


def command_workflow_deploy_test_resume(args: argparse.Namespace) -> None:
    state_path = Path(args.state_file)
    run_logger = WorkflowRunLogger(
        "workflow-deploy-test",
        run_id=workflow_run_id_from_state_path(state_path),
        stdout_enabled=False,
    )
    setattr(args, "workflow_run_logger", run_logger)
    lock_path = acquire_workflow_state_lock(state_path, run_logger)
    if lock_path is None:
        return
    try:
        payload = load_workflow_resume_state(state_path)
        saved_args = payload.get("args") or {}
        for key, value in saved_args.items():
            setattr(args, key, value)
        state = workflow_execution_state_from_json(payload.get("state") or {})
        setattr(args, "workflow_test_id", state.test_id)
        client = ensure_auth(args)
        context = workflow_resume_context_from_json(payload["context"])
        run_workflow_after_build_trigger(
            client,
            context,
            args,
            logger=run_logger,
            state_path=state_path,
            state=state,
        )
    finally:
        release_workflow_state_lock(lock_path)


def command_list_workflow_logs(args: argparse.Namespace) -> None:
    paths = list_workflow_log_paths()
    limit = max(0, int(args.limit))
    if limit:
        paths = paths[:limit]
    print_json(
        {
            "items": [summarize_workflow_log(path) for path in paths],
            "count": len(paths),
        }
    )


def command_show_workflow_log(args: argparse.Namespace) -> None:
    path = resolve_workflow_log_path(args.run_id)
    entries = load_workflow_log_entries(path)
    tail = max(0, int(args.tail))
    if args.raw:
        selected = entries[-tail:] if tail else entries
        print_json(
            {
                "run_id": path.stem,
                "line_count": len(selected),
                "events": selected,
            }
        )
        return
    if tail:
        selected = entries[-tail:]
        print_json(
            {
                "run_id": path.stem,
                "events": compact_workflow_events(selected),
            }
        )
        return
    print_json(summarize_workflow_log_status(path))


def command_cleanup_workflow_logs(args: argparse.Namespace) -> None:
    print_json(
        cleanup_workflow_logs(
            days=int(args.days),
            keep=int(args.keep),
            dry_run=bool(args.dry_run),
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CRP CLI."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--storage-state", default=str(DEFAULT_STORAGE_STATE))
    parser.add_argument("--auth-file", default=str(DEFAULT_AUTH_FILE))
    parser.add_argument("--metrics-file", default=str(DEFAULT_METRICS_FILE))
    parser.add_argument("--http-timeout", type=float, default=30.0)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output instead of compact JSON.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    assigned = subparsers.add_parser(
        "list-assigned-requirements",
        help="List assigned requirements.",
    )
    assigned.add_argument("--offset", type=int, default=1)
    assigned.add_argument("--limit", type=int, default=10)
    assigned.add_argument("--raw", action="store_true")
    assigned.set_defaults(func=command_list_assigned_requirements)

    requirement = subparsers.add_parser("get-requirement", help="Get requirement.")
    requirement.add_argument("--requirement-id", type=int, required=True)
    requirement.add_argument("--raw", action="store_true")
    requirement.set_defaults(func=command_get_requirement)

    search_modules = subparsers.add_parser(
        "search-modules",
        help="Resolve module names.",
    )
    search_modules.add_argument("--requirement-id", type=int, required=True)
    search_modules.add_argument("--module-name", action="append", required=True)
    search_modules.add_argument("--raw", action="store_true")
    search_modules.set_defaults(func=command_search_modules)

    builds = subparsers.add_parser("list-builds", help="List builds.")
    builds.add_argument("--requirement-id", type=int, required=True)
    builds.add_argument("--page", type=int, default=1)
    builds.add_argument("--pagesize", type=int, default=30)
    builds.add_argument("--raw", action="store_true")
    builds.set_defaults(func=command_list_builds)

    tests = subparsers.add_parser("list-tests", help="List tests.")
    tests.add_argument("--requirement-id", type=int, required=True)
    tests.add_argument("--raw", action="store_true")
    tests.set_defaults(func=command_list_tests)

    test_detail = subparsers.add_parser("get-test", help="Get test.")
    test_detail.add_argument("--test-id", type=int, required=True)
    test_detail.add_argument("--requirement-id", type=int)
    test_detail.add_argument("--raw", action="store_true")
    test_detail.set_defaults(func=command_get_test)

    releases = subparsers.add_parser(
        "list-releases",
        help="List releases.",
    )
    releases.add_argument("--requirement-id", type=int, required=True)
    releases.add_argument("--raw", action="store_true")
    releases.set_defaults(func=command_list_releases)

    calendar = subparsers.add_parser(
        "list-calendar",
        help="List release calendar.",
    )
    calendar.add_argument("--requirement-id", type=int, required=True)
    calendar.add_argument("--raw", action="store_true")
    calendar.set_defaults(func=command_list_calendar)

    repo = subparsers.add_parser(
        "get-repo",
        help="Get repo tags and image info.",
    )
    repo.add_argument("--requirement-id", type=int, required=True)
    repo.add_argument("--module-name", required=True)
    repo.add_argument("--env", default="test")
    repo.add_argument("--raw", action="store_true")
    repo.set_defaults(func=command_get_repo)

    build_module = subparsers.add_parser(
        "build-module",
        help="Trigger build.",
    )
    build_module.add_argument("--requirement-id", type=int, required=True)
    build_module.add_argument("--payload-json", help="JSON array or @file containing the full payload.")
    build_module.add_argument("--module-json", action="append", help="Repeatable JSON object for one module.")
    build_module.add_argument("--module-name")
    build_module.add_argument("--scm-url")
    build_module.add_argument("--git-branch", default="test")
    build_module.add_argument("--env", default="test")
    build_module.add_argument("--release-type", default="java")
    build_module.add_argument("--dry-run", action="store_true")
    build_module.add_argument("--raw", action="store_true")
    build_module.set_defaults(func=command_build_module)

    create_test = subparsers.add_parser(
        "create-test",
        help="Create or update test.",
    )
    create_test.add_argument("--requirement-id", type=int, required=True)
    create_test.add_argument(
        "--payload-json",
        help="JSON object or @file containing the full payload. Include id to update an existing test.",
    )
    create_test.add_argument("--qa-assignee", help="QA user_id for the test order assignee.")
    create_test.add_argument("--test-title", default="测试单")
    create_test.add_argument("--change-content")
    create_test.add_argument("--module-name")
    create_test.add_argument("--scm-url")
    create_test.add_argument("--release-type", default="java")
    create_test.add_argument("--dry-run", action="store_true")
    create_test.add_argument("--raw", action="store_true")
    create_test.set_defaults(func=command_create_test)

    create_release = subparsers.add_parser(
        "create-release",
        help="Create release.",
    )
    create_release.add_argument("--test-id", type=int, required=True)
    create_release.add_argument("--requirement-id", type=int, required=True)
    create_release.add_argument("--payload-json", help="JSON object or @file containing the full payload.")
    create_release.add_argument("--change-content", action="append", help="Repeatable change content.")
    create_release.add_argument("--status", default="releasing")
    create_release.add_argument("--remarks", default="")
    create_release.add_argument("--others", default="")
    create_release.add_argument("--package-json", action="append", help="Repeatable JSON object for one package.")
    create_release.add_argument("--business")
    create_release.add_argument("--release-type", default="java")
    create_release.add_argument("--env", default="test")
    create_release.add_argument("--release-url")
    create_release.add_argument("--is-wts", type=int, default=0)
    create_release.add_argument("--use-helm", type=int, default=0)
    create_release.add_argument("--dry-run", action="store_true")
    create_release.add_argument("--raw", action="store_true")
    create_release.set_defaults(func=command_create_release)

    release = subparsers.add_parser("get-release", help="Get release.")
    release.add_argument("--release-id", type=int, required=True)
    release.add_argument("--raw", action="store_true")
    release.set_defaults(func=command_get_release)

    update_image = subparsers.add_parser(
        "update-image",
        help="Update release image.",
    )
    update_image.add_argument("--release-id", type=int, required=True)
    update_image.add_argument("--payload-json", help="JSON array or @file containing the full payload.")
    update_image.add_argument("--package-id")
    update_image.add_argument("--svrname")
    update_image.add_argument("--environ", default="java")
    update_image.add_argument("--image-name")
    update_image.add_argument("--is-wts", default="0")
    update_image.add_argument("--env", default="test")
    update_image.add_argument("--dry-run", action="store_true")
    update_image.add_argument("--raw", action="store_true")
    update_image.set_defaults(func=command_update_image)

    workflow_logs = subparsers.add_parser(
        "list-workflow-logs",
        help="List workflow logs.",
    )
    workflow_logs.add_argument("--limit", type=int, default=10)
    workflow_logs.set_defaults(func=command_list_workflow_logs)

    workflow_log = subparsers.add_parser(
        "show-workflow-log",
        help="Show workflow log.",
    )
    workflow_log.add_argument("--run-id")
    workflow_log.add_argument(
        "--tail",
        type=int,
        default=0,
        help="Show compact last N events. Defaults to a compact status summary.",
    )
    workflow_log.add_argument("--raw", action="store_true", help="Return full raw events instead of compact output.")
    workflow_log.set_defaults(func=command_show_workflow_log)

    workflow_log_cleanup = subparsers.add_parser(
        "cleanup-workflow-logs",
        help="Clean old one-command workflow logs.",
    )
    workflow_log_cleanup.add_argument("--days", type=int, default=14)
    workflow_log_cleanup.add_argument("--keep", type=int, default=50)
    workflow_log_cleanup.add_argument("--dry-run", action="store_true")
    workflow_log_cleanup.set_defaults(func=command_cleanup_workflow_logs)

    workflow = subparsers.add_parser(
        "workflow-deploy-test",
        help="Deploy requirement modules to test, reusing or updating the latest existing test order when possible.",
    )
    workflow.add_argument("--requirement-name", required=True)
    workflow.add_argument("--module-name", action="append", required=True, help="Repeat to deploy multiple modules.")
    workflow.add_argument("--qa-assignee", help="QA user_id used only when the workflow must create a new test order.")
    workflow.add_argument("--git-branch", default="test", help="Git branch to build. Defaults to test.")
    workflow.add_argument("--change-content", action="append", help="Repeatable change summary used in the release order.")
    workflow.add_argument("--build-timeout", type=int, default=600, help="Fail if build waiting exceeds this many seconds.")
    workflow.add_argument("--release-timeout", type=int, default=600, help="Fail if release waiting exceeds this many seconds.")
    workflow.add_argument("--min-poll-interval", type=int, default=5, help="Minimum polling interval in seconds near expected completion.")
    workflow.add_argument("--max-poll-interval", type=int, default=20, help="Maximum polling interval in seconds while still far from expected completion.")
    workflow.add_argument("--wait", action="store_true", help="Wait synchronously until deployment succeeds, fails, or times out.")
    workflow.add_argument("--dry-run", action="store_true", help="Run the full preflight and plan output without any write operation.")
    workflow.set_defaults(func=command_workflow_deploy_test)

    workflow_resume = subparsers.add_parser(
        "_workflow-deploy-test-resume",
        help=argparse.SUPPRESS,
    )
    workflow_resume.add_argument("--state-file", required=True)
    workflow_resume.set_defaults(func=command_workflow_deploy_test_resume)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    global JSON_PRETTY
    JSON_PRETTY = bool(getattr(args, "pretty", False))
    is_workflow = getattr(args, "command", "") in {"workflow-deploy-test", "_workflow-deploy-test-resume"}
    try:
        args.func(args)
    except AuthRequiredError as exc:
        del exc
        sys.exit(2)
    except WorkflowReportedError:
        sys.exit(1)
    except WorkflowParameterError as exc:
        if is_workflow:
            logger = getattr(args, "workflow_run_logger", None)
            payload = {"step": "workflow-parameter-failed", **exc.payload}
            if logger is not None:
                logger.log(payload)
            print_json(compact_workflow_stdout(payload))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        if is_workflow:
            emit_workflow_failed(
                args,
                str(exc),
                logger=getattr(args, "workflow_run_logger", None),
            )
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
