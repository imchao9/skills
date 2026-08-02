#!/usr/bin/env python3
"""Stream a Xiaoqiumi media URL without persisting its query or credentials."""

from __future__ import annotations

import argparse
from collections import deque
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


MIB = 1024 * 1024


class DownloadHealthError(RuntimeError):
    """Raised when a live transfer violates its bounded health policy."""

    def __init__(self, reason: str, snapshot: dict) -> None:
        super().__init__(reason)
        self.reason = reason
        self.snapshot = snapshot


class DownloadSourceChangedError(RuntimeError):
    """Raised when retained chunks no longer match the remote object."""


class DownloadNeedsAttentionError(RuntimeError):
    """Raised after automatic retries are exhausted with chunks preserved."""

    def __init__(self, payload: dict) -> None:
        super().__init__(str(payload.get("reason") or "download needs attention"))
        self.payload = payload


class TransferControl:
    """Allow the monitor to stop active urllib responses from another thread."""

    def __init__(self) -> None:
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._responses: set[object] = set()

    def register(self, response: object) -> None:
        with self._lock:
            if self.cancelled.is_set():
                response.close()
                raise RuntimeError("download cancelled by health monitor")
            self._responses.add(response)

    def unregister(self, response: object) -> None:
        with self._lock:
            self._responses.discard(response)

    def cancel(self) -> None:
        self.cancelled.set()
        with self._lock:
            responses = list(self._responses)
        for response in responses:
            try:
                response.close()
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url-env", default="XQM_DOWNLOAD_URL")
    parser.add_argument("--url-stdin", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--user-agent", default="Mozilla/5.0")
    parser.add_argument("--probe-only", action="store_true", help="Report remote size without downloading media.")
    parser.add_argument("--connections", type=int, default=1, help="Parallel byte-range connections.")
    parser.add_argument("--health-report", type=Path, help="Write resumable transfer heartbeat state here.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Initial attempt plus bounded automatic resumes.")
    parser.add_argument("--retry-backoff-seconds", type=float, default=5)
    parser.add_argument("--heartbeat-seconds", type=float, default=10)
    parser.add_argument("--stall-seconds", type=float, default=90)
    parser.add_argument("--slow-window-seconds", type=float, default=300)
    parser.add_argument("--min-speed-mib", type=float, default=1.0)
    parser.add_argument("--health-grace-seconds", type=float, default=120)
    parser.add_argument("--max-eta-seconds", type=float, default=3600)
    parser.add_argument("--eta-grace-seconds", type=float, default=600)
    return parser.parse_args()


def sanitized(url: str) -> str:
    value = urlsplit(url)
    return urlunsplit((value.scheme, value.netloc, value.path, "", ""))


def write_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def probe_remote(url: str, user_agent: str) -> dict:
    headers = {"User-Agent": user_agent}
    request = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 405):
            raise
        headers["Range"] = "bytes=0-0"
        request = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(request, timeout=60)
    with response:
        content_range = response.headers.get("Content-Range", "")
        total = content_range.rsplit("/", 1)[-1] if "/" in content_range else ""
        size = int(total) if total.isdigit() else int(response.headers.get("Content-Length", "0") or 0)
        if size <= 0:
            raise RuntimeError("remote media size is unavailable")
        return {
            "status": "probed",
            "source": sanitized(url),
            "bytes": size,
            "etag": response.headers.get("ETag"),
            "accept_ranges": response.headers.get("Accept-Ranges"),
        }


def split_ranges(size: int, count: int) -> list[tuple[int, int]]:
    count = max(1, min(count, size))
    chunk_size = (size + count - 1) // count
    return [
        (start, min(size - 1, start + chunk_size - 1))
        for start in range(0, size, chunk_size)
    ]


def chunk_progress(paths: list[Path], ranges: list[tuple[int, int]]) -> int:
    """Count only bytes that belong to the current deterministic range layout."""
    total = 0
    for path, (start, end) in zip(paths, ranges):
        expected = end - start + 1
        if path.is_file() and path.stat().st_size == expected:
            total += expected
            continue
        temporary = path.with_name(path.name + ".part")
        if temporary.is_file():
            total += min(temporary.stat().st_size, expected)
    return total


def health_snapshot(
    *,
    now: float,
    started: float,
    downloaded: int,
    total: int,
    last_progress_at: float,
    samples: list[tuple[float, int]],
    attempt: int,
    max_attempts: int,
    connections: int,
) -> dict:
    window_started, window_bytes = samples[0]
    window_seconds = max(0.0, now - window_started)
    speed_bps = max(0.0, downloaded - window_bytes) / window_seconds if window_seconds else 0.0
    remaining = max(0, total - downloaded)
    eta_seconds = remaining / speed_bps if speed_bps > 0 else None
    return {
        "status": "running",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "connections": connections,
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "progress_percent": round(downloaded * 100 / total, 3) if total else 0.0,
        "elapsed_seconds": round(now - started, 3),
        "window_seconds": round(window_seconds, 3),
        "speed_bytes_per_second": round(speed_bps, 3),
        "speed_mib_per_second": round(speed_bps / MIB, 3),
        "eta_seconds": round(eta_seconds, 3) if eta_seconds is not None else None,
        "last_progress_seconds_ago": round(now - last_progress_at, 3),
        "chunks_preserved": True,
    }


def health_failure_reason(
    snapshot: dict,
    *,
    stall_seconds: float,
    slow_window_seconds: float,
    min_speed_mib: float,
    health_grace_seconds: float,
    max_eta_seconds: float,
    eta_grace_seconds: float,
) -> str | None:
    if float(snapshot["elapsed_seconds"]) < health_grace_seconds:
        return None
    if float(snapshot["last_progress_seconds_ago"]) >= stall_seconds:
        return "no_progress"
    if (
        float(snapshot["window_seconds"]) >= slow_window_seconds
        and float(snapshot["speed_mib_per_second"]) < min_speed_mib
    ):
        return "sustained_low_throughput"
    eta = snapshot.get("eta_seconds")
    if (
        float(snapshot["elapsed_seconds"]) >= eta_grace_seconds
        and eta is not None
        and float(eta) > max_eta_seconds
    ):
        return "eta_budget_exceeded"
    return None


def download_range(
    url: str,
    user_agent: str,
    path: Path,
    start: int,
    end: int,
    control: TransferControl | None = None,
) -> int:
    expected = end - start + 1
    if path.is_file() and path.stat().st_size == expected:
        return expected
    temporary = path.with_name(path.name + ".part")
    existing = temporary.stat().st_size if temporary.exists() else 0
    if existing > expected:
        temporary.unlink()
        existing = 0
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Range": f"bytes={start + existing}-{end}",
        },
    )
    response = urllib.request.urlopen(request, timeout=60)
    if control is not None:
        control.register(response)
    status = getattr(response, "status", response.getcode())
    if status != 206:
        if control is not None:
            control.unregister(response)
        response.close()
        raise RuntimeError(f"range request returned HTTP {status}, expected 206")
    mode = "ab" if existing else "wb"
    try:
        with response, temporary.open(mode) as handle:
            while True:
                if control is not None and control.cancelled.is_set():
                    raise RuntimeError("download cancelled by health monitor")
                block = response.read(256 * 1024)
                if not block:
                    break
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if control is not None:
            control.unregister(response)
    actual = temporary.stat().st_size
    if actual != expected:
        raise RuntimeError(f"range size mismatch: expected {expected}, got {actual}")
    os.replace(temporary, path)
    return actual


def download_parallel(
    url: str,
    user_agent: str,
    output: Path,
    part: Path,
    connections: int,
    *,
    health_report: Path | None,
    attempt: int,
    max_attempts: int,
    heartbeat_seconds: float,
    stall_seconds: float,
    slow_window_seconds: float,
    min_speed_mib: float,
    health_grace_seconds: float,
    max_eta_seconds: float,
    eta_grace_seconds: float,
) -> dict:
    remote = probe_remote(url, user_agent)
    size = int(remote["bytes"])
    ranges = split_ranges(size, connections)
    chunk_dir = output.with_name(output.name + ".chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    manifest = chunk_dir / "manifest.json"
    contract = {
        "source": sanitized(url),
        "bytes": size,
        "etag": remote.get("etag"),
        "connections": len(ranges),
    }
    if manifest.is_file():
        existing_contract = json.loads(manifest.read_text(encoding="utf-8"))
        if existing_contract != contract:
            raise DownloadSourceChangedError(
                "remote object or range layout changed; retained chunks require inspection"
            )
    else:
        write_report(manifest, contract)
    chunk_paths = [chunk_dir / f"{index:04d}.part" for index in range(len(ranges))]
    control = TransferControl()
    started = time.monotonic()
    downloaded = chunk_progress(chunk_paths, ranges)
    last_downloaded = downloaded
    last_progress_at = started
    samples: deque[tuple[float, int]] = deque([(started, downloaded)])
    base_health = {
        "source": sanitized(url),
        "output": str(output),
        "health_report": str(health_report) if health_report else None,
    }
    initial = health_snapshot(
        now=started,
        started=started,
        downloaded=downloaded,
        total=size,
        last_progress_at=last_progress_at,
        samples=list(samples),
        attempt=attempt,
        max_attempts=max_attempts,
        connections=len(ranges),
    )
    write_report(health_report, {**base_health, **initial})
    with ThreadPoolExecutor(max_workers=len(ranges), thread_name_prefix="xqm-range") as pool:
        futures = {
            pool.submit(download_range, url, user_agent, path, start, end, control): index
            for index, (path, (start, end)) in enumerate(zip(chunk_paths, ranges))
        }
        pending = set(futures)
        try:
            while pending:
                done, pending = wait(
                    pending,
                    timeout=max(0.1, heartbeat_seconds),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    future.result()
                now = time.monotonic()
                downloaded = chunk_progress(chunk_paths, ranges)
                if downloaded > last_downloaded:
                    last_progress_at = now
                    last_downloaded = downloaded
                samples.append((now, downloaded))
                while len(samples) > 1 and samples[1][0] <= now - slow_window_seconds:
                    samples.popleft()
                snapshot = health_snapshot(
                    now=now,
                    started=started,
                    downloaded=downloaded,
                    total=size,
                    last_progress_at=last_progress_at,
                    samples=list(samples),
                    attempt=attempt,
                    max_attempts=max_attempts,
                    connections=len(ranges),
                )
                write_report(health_report, {**base_health, **snapshot})
                reason = health_failure_reason(
                    snapshot,
                    stall_seconds=stall_seconds,
                    slow_window_seconds=slow_window_seconds,
                    min_speed_mib=min_speed_mib,
                    health_grace_seconds=health_grace_seconds,
                    max_eta_seconds=max_eta_seconds,
                    eta_grace_seconds=eta_grace_seconds,
                )
                if reason:
                    control.cancel()
                    for future in pending:
                        future.cancel()
                    failed = {**base_health, **snapshot, "status": "unhealthy", "reason": reason}
                    write_report(health_report, failed)
                    raise DownloadHealthError(reason, failed)
        except Exception:
            control.cancel()
            raise
    with part.open("wb") as destination:
        for path in chunk_paths:
            with path.open("rb") as source:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    destination.write(block)
        destination.flush()
        os.fsync(destination.fileno())
    actual = part.stat().st_size
    if actual != size:
        raise RuntimeError(f"assembled size mismatch: expected {size}, got {actual}")
    os.replace(part, output)
    for path in chunk_paths:
        path.unlink()
    manifest.unlink()
    chunk_dir.rmdir()
    payload = {
        "status": "complete",
        "source": sanitized(url),
        "output": str(output),
        "bytes": actual,
        "etag": remote.get("etag"),
        "range_supported": True,
        "connections": len(ranges),
    }
    complete_health = {
        **base_health,
        "status": "complete",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "connections": len(ranges),
        "downloaded_bytes": actual,
        "total_bytes": size,
        "progress_percent": 100.0,
        "chunks_preserved": False,
    }
    write_report(health_report, complete_health)
    return payload


def download_parallel_with_retries(
    url: str,
    user_agent: str,
    output: Path,
    part: Path,
    connections: int,
    *,
    health_report: Path | None,
    max_attempts: int,
    retry_backoff_seconds: float,
    heartbeat_seconds: float,
    stall_seconds: float,
    slow_window_seconds: float,
    min_speed_mib: float,
    health_grace_seconds: float,
    max_eta_seconds: float,
    eta_grace_seconds: float,
) -> dict:
    failures: list[dict] = []
    max_attempts = max(1, max_attempts)
    for attempt in range(1, max_attempts + 1):
        try:
            payload = download_parallel(
                url,
                user_agent,
                output,
                part,
                connections,
                health_report=health_report,
                attempt=attempt,
                max_attempts=max_attempts,
                heartbeat_seconds=heartbeat_seconds,
                stall_seconds=stall_seconds,
                slow_window_seconds=slow_window_seconds,
                min_speed_mib=min_speed_mib,
                health_grace_seconds=health_grace_seconds,
                max_eta_seconds=max_eta_seconds,
                eta_grace_seconds=eta_grace_seconds,
            )
            payload["attempts"] = attempt
            return payload
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            message = str(exc).replace(url, sanitized(url))
            reason = exc.reason if isinstance(exc, DownloadHealthError) else type(exc).__name__
            retryable = not isinstance(exc, DownloadSourceChangedError)
            failure = {
                "attempt": attempt,
                "reason": reason,
                "error": message,
                "retryable": retryable,
            }
            failures.append(failure)
            existing = exc.snapshot if isinstance(exc, DownloadHealthError) else {}
            if retryable and attempt < max_attempts:
                retrying = {
                    **existing,
                    "status": "retrying",
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "source": sanitized(url),
                    "output": str(output),
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "reason": reason,
                    "retry_in_seconds": retry_backoff_seconds,
                    "chunks_preserved": True,
                    "failures": failures,
                }
                write_report(health_report, retrying)
                time.sleep(max(0.0, retry_backoff_seconds))
                continue
            needs_attention = {
                **existing,
                "status": "needs_attention",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "source": sanitized(url),
                "output": str(output),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "reason": reason,
                "error": message,
                "chunks_preserved": True,
                "resume_uses_existing_chunks": True,
                "retryable": retryable,
                "health_report": str(health_report) if health_report else None,
                "failures": failures,
            }
            write_report(health_report, needs_attention)
            raise DownloadNeedsAttentionError(needs_attention) from exc
    raise AssertionError("unreachable retry state")


def main() -> int:
    args = parse_args()
    url = sys.stdin.readline().strip() if args.url_stdin else os.environ.get(args.url_env, "").strip()
    if not url:
        raise SystemExit(f"download URL missing; set {args.url_env} or use --url-stdin")

    if args.probe_only:
        try:
            payload = probe_remote(url, args.user_agent)
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            payload = {"status": "failed", "source": sanitized(url), "error": str(exc)}
            write_report(args.report, payload)
            raise SystemExit(str(exc)) from exc

    output = args.output.resolve()
    part = output.with_name(output.name + ".part")
    output.parent.mkdir(parents=True, exist_ok=True)
    health_report = (
        args.health_report.resolve()
        if args.health_report
        else (
            args.report.with_name(f"{args.report.stem}-health.json").resolve()
            if args.report
            else output.with_name(output.name + ".download-health.json")
        )
    )
    if args.connections > 1:
        try:
            payload = download_parallel_with_retries(
                url,
                args.user_agent,
                output,
                part,
                args.connections,
                health_report=health_report,
                max_attempts=args.max_attempts,
                retry_backoff_seconds=args.retry_backoff_seconds,
                heartbeat_seconds=args.heartbeat_seconds,
                stall_seconds=args.stall_seconds,
                slow_window_seconds=args.slow_window_seconds,
                min_speed_mib=args.min_speed_mib,
                health_grace_seconds=args.health_grace_seconds,
                max_eta_seconds=args.max_eta_seconds,
                eta_grace_seconds=args.eta_grace_seconds,
            )
            payload["health_report"] = str(health_report)
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        except DownloadNeedsAttentionError as exc:
            payload = exc.payload
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 3
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            message = str(exc).replace(url, sanitized(url))
            payload = {
                "status": "failed",
                "source": sanitized(url),
                "output": str(output),
                "health_report": str(health_report),
                "error": message,
            }
            write_report(args.report, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
            return 1

    existing = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": args.user_agent}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(url, headers=headers)
    payload = {
        "status": "running",
        "source": sanitized(url),
        "output": str(output),
        "part": str(part),
        "resumed_from": existing,
    }
    write_report(args.report, payload)

    try:
        response = urllib.request.urlopen(request, timeout=60)
        status = getattr(response, "status", response.getcode())
        append = existing > 0 and status == 206
        if existing and not append:
            existing = 0
        content_length = int(response.headers.get("Content-Length", "0") or 0)
        expected = existing + content_length if content_length else None
        mode = "ab" if append else "wb"
        with response, part.open(mode) as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        actual = part.stat().st_size
        if expected is not None and actual != expected:
            raise RuntimeError(f"size mismatch: expected {expected}, got {actual}")
        os.replace(part, output)
        payload.update({
            "status": "complete",
            "bytes": actual,
            "etag": response.headers.get("ETag"),
            "range_supported": status == 206,
        })
        write_report(args.report, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        payload.update({"status": "failed", "error": str(exc)})
        write_report(args.report, payload)
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    sys.exit(main())
