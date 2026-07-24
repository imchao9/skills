#!/usr/bin/env python3
"""Resolve, download, and verify an authorized WeChat Channels share link."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from probe_public_parser import choose_video_url, inspect_url, parser_request


CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow HTTPS redirects only to the expected WeChat video CDN."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_video_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def fail(reason: str, **details: object) -> int:
    emit({"status": "fail", "reason": reason, **details})
    return 1


def validate_share_url(share_url: str) -> None:
    parsed = urllib.parse.urlsplit(share_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "weixin.qq.com"
        or not parsed.path.startswith("/sph/")
    ):
        raise ValueError("unsupported_share_url")


def validate_video_url(video_url: str) -> None:
    parsed = urllib.parse.urlsplit(video_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "finder.video.qq.com" or host.endswith(".video.qq.com")
    ):
        raise ValueError("unexpected_video_host")


def normalize_output_path(raw_path: Path) -> Path:
    output = raw_path.expanduser()
    if not output.suffix:
        output = output.with_suffix(".mp4")
    if output.suffix.lower() != ".mp4":
        raise ValueError("output_must_use_mp4_extension")

    name = output.name
    if (
        not name
        or name.endswith((" ", "."))
        or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
        or name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
    ):
        raise ValueError("output_name_is_not_windows_compatible")

    if not output.is_absolute():
        output = Path.cwd() / output
    return output.resolve()


def parse_content_length(headers: Any) -> int | None:
    raw_length = headers.get("Content-Length")
    if not raw_length:
        return None
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        return None
    return length if length >= 0 else None


def download_to_temp(
    video_url: str,
    temp_path: Path,
    *,
    max_bytes: int,
    timeout: float,
) -> dict[str, object]:
    validate_video_url(video_url)
    request = urllib.request.Request(
        video_url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="GET",
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    digest = hashlib.sha256()
    total = 0
    leading_bytes = bytearray()

    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl()
        validate_video_url(final_url)
        expected_bytes = parse_content_length(response.headers)
        if expected_bytes is not None and expected_bytes > max_bytes:
            raise ValueError("content_length_exceeds_limit")

        content_type = response.headers.get_content_type()
        with temp_path.open("xb") as output:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("download_exceeds_limit")
                if len(leading_bytes) < 32:
                    remaining = 32 - len(leading_bytes)
                    leading_bytes.extend(chunk[:remaining])
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())

    if total <= 0:
        raise ValueError("empty_download")
    if expected_bytes is not None and total != expected_bytes:
        raise ValueError("content_length_mismatch")
    if len(leading_bytes) < 12 or leading_bytes[4:8] != b"ftyp":
        raise ValueError("mp4_signature_missing")

    return {
        "bytes_written": total,
        "content_type": content_type,
        "sha256": digest.hexdigest(),
        "mp4_signature": "pass",
    }


def run_ffprobe(path: Path, timeout: float) -> dict[str, object]:
    executable = shutil.which("ffprobe")
    if not executable:
        return {
            "status": "skipped",
            "reason": "ffprobe_not_found",
        }

    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fail", "reason": "ffprobe_timeout"}

    if completed.returncode != 0:
        return {
            "status": "fail",
            "reason": "ffprobe_failed",
            "returncode": completed.returncode,
        }

    try:
        result = json.loads(completed.stdout)
        duration = float((result.get("format") or {}).get("duration") or 0)
        video_streams = [
            stream
            for stream in result.get("streams") or []
            if stream.get("codec_type") == "video"
        ]
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return {"status": "fail", "reason": "ffprobe_invalid_output"}

    if duration <= 0 or not video_streams:
        return {"status": "fail", "reason": "ffprobe_video_validation_failed"}

    first_stream = video_streams[0]
    return {
        "status": "pass",
        "duration_seconds": round(duration, 3),
        "codec": first_stream.get("codec_name"),
        "width": first_stream.get("width"),
        "height": first_stream.get("height"),
        "format_name": (result.get("format") or {}).get("format_name"),
    }


def resolve_video_url(share_url: str) -> tuple[str, str, dict[str, object]]:
    result = parser_request(share_url)
    data = result.get("data")
    feed_info = data.get("feedInfo") if isinstance(data, dict) else None
    if not isinstance(feed_info, dict):
        raise ValueError("parser_did_not_return_feed_info")

    source, video_url = choose_video_url(feed_info)
    if not source or not video_url:
        raise ValueError("parser_did_not_return_video_url")
    validate_video_url(video_url)
    return source, video_url, inspect_url(source, video_url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve a WeChat Channels share link through the upstream public parser, "
            "then download and verify the MP4 without exposing its signed URL."
        )
    )
    parser.add_argument("share_url", help="A https://weixin.qq.com/sph/... share URL")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination .mp4 path",
    )
    parser.add_argument(
        "--allow-external-parser",
        action="store_true",
        help="Confirm that sending the share URL to the public parser is allowed.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Atomically replace an existing output file.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="Maximum allowed download size in bytes (default: 2 GiB).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Network and ffprobe timeout in seconds (default: 60).",
    )
    args = parser.parse_args()

    if not args.allow_external_parser:
        return fail(
            "explicit_external_parser_approval_required",
            hint="Rerun with --allow-external-parser after user approval.",
        )
    if args.max_bytes <= 0:
        return fail("max_bytes_must_be_positive")
    if args.timeout <= 0:
        return fail("timeout_must_be_positive")

    try:
        validate_share_url(args.share_url)
        output_path = normalize_output_path(args.output)
    except ValueError as error:
        return fail(str(error))

    if output_path.exists() and not args.overwrite:
        return fail("output_already_exists", output_path=str(output_path))
    if output_path.exists() and not output_path.is_file():
        return fail("output_is_not_a_file", output_path=str(output_path))

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return fail("output_directory_unavailable", error_type=type(error).__name__)

    temp_path = output_path.with_name(
        f".{output_path.stem}.{os.getpid()}.part{output_path.suffix}"
    )
    if temp_path.exists():
        return fail("temporary_path_already_exists", temp_path=str(temp_path))

    try:
        source, video_url, url_metadata = resolve_video_url(args.share_url)
        download_result = download_to_temp(
            video_url,
            temp_path,
            max_bytes=args.max_bytes,
            timeout=args.timeout,
        )
        probe_result = run_ffprobe(temp_path, args.timeout)
        if probe_result.get("status") == "fail":
            return fail(
                "downloaded_file_failed_ffprobe",
                output_path=str(output_path),
                ffprobe=probe_result,
            )
        os.replace(temp_path, output_path)
    except urllib.error.HTTPError as error:
        return fail(
            "http_error",
            http_status=error.code,
            error_type=type(error).__name__,
        )
    except (urllib.error.URLError, TimeoutError) as error:
        return fail("network_error", error_type=type(error).__name__)
    except (ValueError, json.JSONDecodeError) as error:
        return fail(str(error))
    except OSError as error:
        return fail("filesystem_error", error_type=type(error).__name__)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    emit(
        {
            "status": "pass",
            "output_path": str(output_path),
            "video_url_source": source,
            "video_host": url_metadata.get("video_host"),
            "video_url_sha256": url_metadata.get("video_url_sha256"),
            "download": download_result,
            "ffprobe": probe_result,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
