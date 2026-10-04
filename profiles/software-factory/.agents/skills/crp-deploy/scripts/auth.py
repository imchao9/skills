#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import ssl
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://crp.codemao.cn"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = SKILL_ROOT / "output"
DEFAULT_STORAGE_STATE = OUTPUT_DIR / "auth-storage-state.json"
DEFAULT_AUTH_FILE = OUTPUT_DIR / "auth-cookie.txt"
AUTH_DOC_PATH = SKILL_ROOT / "references" / "auth.md"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
REQUIRED_AUTH_COOKIE_NAMES = {"internal_account_token", "admin-authorization"}
JSON_PRETTY = False
TRANSIENT_HTTP_STATUS_CODES = {429, 502, 503, 504}
RETRYABLE_HTTP_METHODS = {"GET"}
REQUEST_MAX_ATTEMPTS = 3
REQUEST_RETRY_BASE_SECONDS = 0.5
BOOTSTRAP_COOKIE_NAMES = {"user_name", "display_name"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def json_dumps(payload: Any, *, pretty: bool | None = None) -> str:
    use_pretty = JSON_PRETTY if pretty is None else pretty
    if use_pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def print_json(payload: Any) -> None:
    print(json_dumps(payload), flush=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_cookie_file_template(auth_file_path: Path, *, base_url: str) -> None:
    if auth_file_path.exists():
        return
    ensure_parent(auth_file_path)
    auth_file_path.write_text(
        "\n".join(
            [
                "# auth cookie file",
                f"# base_url: {base_url.rstrip('/')}",
                "# 直接把浏览器开发者工具里复制出的完整 Cookie 粘贴到本文件最后一行。",
                "# 文件最后一行必须是完整 cookie 字符串，不要保留占位文本。",
                "# cookie 失效后可以重新粘贴，或执行: node scripts/auth-login.js",
                "",
            ]
        ),
        encoding="utf-8",
    )


def maybe_load_json_text(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def load_storage_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Storage state not found: {path}. Read {AUTH_DOC_PATH}.")
    return json.loads(path.read_text(encoding="utf-8"))


def filter_crp_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for cookie in cookies:
        domain = str(cookie.get("domain") or "")
        if domain == "crp.codemao.cn" or domain.endswith(".codemao.cn"):
            filtered.append(cookie)
    return filtered


def extract_crp_cookies(storage_state_path: Path) -> list[dict[str, Any]]:
    state = load_storage_state(storage_state_path)
    return filter_crp_cookies([cookie for cookie in state.get("cookies", []) if isinstance(cookie, dict)])


def build_cookie_header_from_storage_state(storage_state_path: Path) -> str:
    cookies = extract_crp_cookies(storage_state_path)
    if not cookies:
        raise RuntimeError(f"No CRP cookies found in {storage_state_path}")
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)


def load_cookie_header_from_auth_file(auth_file_path: Path) -> str | None:
    if not auth_file_path.exists():
        return None
    text = auth_file_path.read_text(encoding="utf-8")
    data = maybe_load_json_text(text)
    if isinstance(data, dict):
        cookie_header = str(data.get("cookie_header") or "").strip()
        return cookie_header or None
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("cookie="):
            stripped = stripped.split("=", 1)[1].strip()
        return stripped or None
    return None


def cookie_names_from_header(cookie_header: str) -> list[str]:
    names: list[str] = []
    for item in cookie_header.split(";"):
        part = item.strip()
        if not part or "=" not in part:
            continue
        name = part.split("=", 1)[0].strip()
        if name:
            names.append(name)
    return names


def missing_required_auth_cookie_names(cookie_names: list[str]) -> list[str]:
    return sorted(REQUIRED_AUTH_COOKIE_NAMES.difference(cookie_names))


def ensure_required_auth_cookie_names(cookie_names: list[str], *, source: str) -> None:
    missing = missing_required_auth_cookie_names(cookie_names)
    if missing:
        raise RuntimeError(f"{source} does not contain the required CRP auth cookies yet: {', '.join(missing)}")


def build_cookie_header_from_cookies(cookies: list[dict[str, Any]]) -> str:
    crp_cookies = filter_crp_cookies(cookies)
    ensure_required_auth_cookie_names(
        [str(cookie.get("name") or "") for cookie in crp_cookies],
        source="Playwright cookies",
    )
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in crp_cookies)


def build_storage_state_from_cookies(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    return {"cookies": cookies, "origins": []}


def write_json_file(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json_dumps(payload, pretty=True) + "\n", encoding="utf-8")


def build_auth_summary_payload(
    *,
    cookie_header: str,
    storage_state_path: Path,
    auth_file_path: Path,
    base_url: str,
    source: str,
) -> dict[str, Any]:
    cookie_names = cookie_names_from_header(cookie_header)
    missing_required = missing_required_auth_cookie_names(cookie_names)
    return {
        "base_url": base_url.rstrip("/"),
        "generated_at": now_iso(),
        "source": source,
        "storage_state_path": str(storage_state_path),
        "auth_file_path": str(auth_file_path),
        "cookie_count": len(cookie_names),
        "cookie_names": cookie_names,
        "has_required_auth_cookies": not missing_required,
        "missing_required_auth_cookies": missing_required,
    }


def write_auth_cookie_file(
    *,
    cookie_header: str,
    storage_state_path: Path,
    auth_file_path: Path,
    base_url: str,
    source: str,
) -> dict[str, Any]:
    ensure_parent(auth_file_path)
    ensure_required_auth_cookie_names(cookie_names_from_header(cookie_header), source=str(auth_file_path))
    summary = build_auth_summary_payload(
        cookie_header=cookie_header,
        storage_state_path=storage_state_path,
        auth_file_path=auth_file_path,
        base_url=base_url,
        source=source,
    )
    auth_file_path.write_text(
        "\n".join(
            [
                "# auth cookie file",
                f"# base_url: {summary['base_url']}",
                f"# generated_at: {summary['generated_at']}",
                f"# source: {summary['source']}",
                f"# storage_state_path: {summary['storage_state_path']}",
                f"# cookie_names: {', '.join(summary['cookie_names']) or '(empty)'}",
                "# 直接覆盖最后一行即可更新 cookie。",
                cookie_header.strip(),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def save_auth_from_cookies(
    *,
    cookies: list[dict[str, Any]],
    storage_state_path: Path,
    auth_file_path: Path,
    base_url: str,
    source: str,
) -> dict[str, Any]:
    crp_cookies = filter_crp_cookies(cookies)
    ensure_required_auth_cookie_names(
        [str(cookie.get("name") or "") for cookie in crp_cookies],
        source=source,
    )
    write_json_file(storage_state_path, build_storage_state_from_cookies(crp_cookies))
    return write_auth_cookie_file(
        cookie_header=build_cookie_header_from_cookies(crp_cookies),
        storage_state_path=storage_state_path,
        auth_file_path=auth_file_path,
        base_url=base_url,
        source=source,
    )


def resolve_cookie_header(
    storage_state_path: Path,
    auth_file_path: Path,
    *,
    create_template: bool = True,
) -> str:
    for candidate in [auth_file_path, storage_state_path]:
        if candidate == storage_state_path:
            try:
                return build_cookie_header_from_storage_state(storage_state_path)
            except Exception:
                continue
        cookie_header = load_cookie_header_from_auth_file(candidate)
        if cookie_header:
            return cookie_header
    if create_template:
        ensure_cookie_file_template(auth_file_path, base_url=DEFAULT_BASE_URL)
    raise RuntimeError(
        f"No auth cookies found. Read {AUTH_DOC_PATH} and either paste the full cookie into {auth_file_path} or run `node scripts/auth-login.js`."
    )


def format_network_error(exc: urllib.error.URLError, *, url: str) -> str:
    reason = getattr(exc, "reason", exc)
    reason_text = str(reason)
    if isinstance(reason, OSError) and getattr(reason, "errno", None) == 8:
        return f"{url} 无法解析域名。当前运行环境的 DNS/网络不可用，请在沙箱外重新执行该命令。"
    if "nodename nor servname provided" in reason_text or "name or service not known" in reason_text:
        return f"{url} 无法解析域名。当前运行环境的 DNS/网络不可用，请在沙箱外重新执行该命令。"
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


def perform_json_request_with_response_meta(
    method: str,
    url: str,
    *,
    base_url: str,
    cookie_header: str,
    timeout: float,
    context: ssl.SSLContext,
    referer: str | None = None,
) -> tuple[Any, Any, str]:
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Cookie": cookie_header,
        "User-Agent": BROWSER_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }
    if referer:
        headers["Referer"] = referer
    current_cookie_header = cookie_header
    bootstrap_applied = False
    method_upper = method.upper()
    for attempt in range(1, REQUEST_MAX_ATTEMPTS + 1):
        headers["Cookie"] = current_cookie_header
        request = urllib.request.Request(url, headers=headers, method=method)
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
                return json.loads(raw_text), response.headers, current_cookie_header
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


def perform_json_request(
    method: str,
    url: str,
    *,
    base_url: str,
    cookie_header: str,
    timeout: float,
    context: ssl.SSLContext,
    referer: str | None = None,
) -> Any:
    data, _, _ = perform_json_request_with_response_meta(
        method,
        url,
        base_url=base_url,
        cookie_header=cookie_header,
        timeout=timeout,
        context=context,
        referer=referer,
    )
    return data


def validate_auth_cookie_header(base_url: str, cookie_header: str, *, timeout: float) -> None:
    base_url = base_url.rstrip("/")
    perform_json_request(
        "GET",
        f"{base_url}/api/my/assigned_requirements?offset=1&limit=1",
        base_url=base_url,
        cookie_header=cookie_header,
        timeout=timeout,
        context=ssl.create_default_context(),
        referer=f"{base_url}/workbench",
    )


def resolve_playwright_library_path() -> Path:
    candidates = sorted(
        Path.home().glob(".npm/_npx/*/node_modules/playwright/package.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0].parent
    raise RuntimeError("Playwright library package not found. Install it first, or use manual cookie mode.")


def can_use_playwright() -> bool:
    if shutil.which("node") is None:
        return False
    try:
        resolve_playwright_library_path()
    except Exception:
        return False
    return True


def build_auth_help_payload(
    *,
    base_url: str,
    auth_file: str | Path,
    reason: str,
    create_template: bool = True,
) -> dict[str, Any]:
    auth_file_path = Path(auth_file)
    if create_template:
        ensure_cookie_file_template(auth_file_path, base_url=base_url)
    del reason
    return {
        "error": "auth_expired",
        "next": "run `node scripts/auth-login.js` in skill root, or read references/auth.md; then rerun previous command",
    }


def command_validate(args: argparse.Namespace) -> None:
    storage_state_path = Path(args.storage_state)
    auth_file_path = Path(args.auth_file)
    try:
        validate_auth_cookie_header(args.base_url, resolve_cookie_header(storage_state_path, auth_file_path), timeout=args.http_timeout)
        payload = {"validate_ok": True}
    except Exception:
        payload = {"validate_ok": False, "error": "auth_invalid"}
    print_json(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auth", description="Auth.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--storage-state", default=str(DEFAULT_STORAGE_STATE))
    parser.add_argument("--auth-file", default=str(DEFAULT_AUTH_FILE))
    parser.add_argument("--http-timeout", type=float, default=30.0)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate auth.")
    validate.set_defaults(func=command_validate)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    global JSON_PRETTY
    JSON_PRETTY = False
    try:
        args.func(args)
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
