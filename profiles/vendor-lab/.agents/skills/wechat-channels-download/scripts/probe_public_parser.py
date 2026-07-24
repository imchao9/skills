#!/usr/bin/env python3
"""Probe the upstream public parser without printing a signed video URL."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


PARSER_URL = "https://sph.litao.workers.dev/api/fetch_video_profile"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def parser_request(share_url: str) -> dict[str, object]:
    body = json.dumps({"url": share_url}).encode("utf-8")
    request = urllib.request.Request(
        PARSER_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "wechat-channels-download-skill/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("parser response exceeds the safety limit")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("parser response is not a JSON object")
    return parsed


def choose_video_url(feed_info: dict[str, object]) -> tuple[str | None, str | None]:
    candidates = (
        ("h264VideoInfo.videoUrl", feed_info.get("h264VideoInfo")),
        ("h265VideoInfo.videoUrl", feed_info.get("h265VideoInfo")),
    )
    for source, value in candidates:
        if isinstance(value, dict):
            url = value.get("videoUrl")
            if isinstance(url, str) and url:
                return source, url

    fallback = feed_info.get("videoUrl")
    if isinstance(fallback, str) and fallback:
        return "videoUrl", fallback
    return None, None


def inspect_url(source: str, video_url: str) -> dict[str, object]:
    parsed = urllib.parse.urlsplit(video_url)
    query_keys = sorted(
        set(urllib.parse.parse_qs(parsed.query, keep_blank_values=True).keys())
    )
    return {
        "video_url_present": True,
        "video_url_source": source,
        "video_scheme": parsed.scheme,
        "video_host": parsed.hostname,
        "query_parameter_names": query_keys,
        "has_encfilekey_parameter": "encfilekey" in query_keys,
        "has_token_parameter": any(
            key.lower() in {"token", "authkey", "sign", "signature"}
            for key in query_keys
        ),
        "video_url_sha256": hashlib.sha256(video_url.encode("utf-8")).hexdigest(),
    }


def check_url(video_url: str) -> dict[str, object]:
    request = urllib.request.Request(
        video_url,
        headers={"Range": "bytes=0-0", "User-Agent": "Mozilla/5.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read(1)
            return {
                "reachable": True,
                "http_status": response.status,
                "content_type": response.headers.get_content_type(),
                "content_length": response.headers.get("Content-Length"),
                "content_range": response.headers.get("Content-Range"),
            }
    except urllib.error.HTTPError as error:
        return {
            "reachable": False,
            "http_status": error.code,
            "error_type": type(error).__name__,
        }
    except (urllib.error.URLError, TimeoutError) as error:
        return {"reachable": False, "error_type": type(error).__name__}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Use the upstream public parser and report only redacted URL metadata."
    )
    parser.add_argument("share_url", help="A https://weixin.qq.com/sph/... share URL")
    parser.add_argument(
        "--allow-external-parser",
        action="store_true",
        help="Confirm that sending the share URL to the public parser is allowed.",
    )
    parser.add_argument(
        "--check-url",
        action="store_true",
        help="Read at most one byte from the returned video URL.",
    )
    args = parser.parse_args()

    if not args.allow_external_parser:
        emit(
            {
                "status": "blocked",
                "reason": "explicit --allow-external-parser approval is required",
            }
        )
        return 2

    parsed_share_url = urllib.parse.urlsplit(args.share_url)
    if (
        parsed_share_url.scheme != "https"
        or parsed_share_url.hostname != "weixin.qq.com"
        or not parsed_share_url.path.startswith("/sph/")
    ):
        emit({"status": "invalid_input", "reason": "unsupported share URL"})
        return 2

    try:
        result = parser_request(args.share_url)
    except urllib.error.HTTPError as error:
        emit(
            {
                "status": "parser_error",
                "http_status": error.code,
                "error_type": type(error).__name__,
            }
        )
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        emit({"status": "parser_error", "error_type": type(error).__name__})
        return 1

    data = result.get("data")
    feed_info = data.get("feedInfo") if isinstance(data, dict) else None
    if not isinstance(feed_info, dict):
        emit(
            {
                "status": "no_video_url",
                "parser_error_present": bool(result.get("error")),
                "parser_err_code": result.get("errCode"),
            }
        )
        return 1

    source, video_url = choose_video_url(feed_info)
    if not source or not video_url:
        emit({"status": "no_video_url", "feed_info_present": True})
        return 1

    output = {"status": "video_url_found", **inspect_url(source, video_url)}
    if args.check_url:
        output["url_check"] = check_url(video_url)
    emit(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
