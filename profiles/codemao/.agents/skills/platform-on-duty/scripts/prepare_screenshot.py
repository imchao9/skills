#!/usr/bin/env python3
"""为峰值秒生成整分钟、秒级柱状图查询计划。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import tomllib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from prepare_run import (
    DEFAULT_CONFIG,
    PlanError,
    build_query_url,
    extract_search_expression,
    load_config,
)


def build_screenshot_query(search_expression: str, limit: int) -> str:
    return (
        f"{search_expression} | select "
        "date_format(from_unixtime(__time__), '%Y-%m-%d %H:%i:%s') "
        "as request_second, count(*) as request_count "
        "group by request_second order by request_second asc "
        f"limit {limit}"
    )


def prepare_screenshot_plan(
    config: dict[str, Any],
    service_name: str,
    peak_epoch: int,
    request_count: int,
) -> dict[str, Any]:
    service = next(
        (item for item in config["services"] if item["name"] == service_name),
        None,
    )
    if service is None:
        raise PlanError("UNKNOWN_SERVICE", f"未知服务：{service_name}")
    if peak_epoch <= 0:
        raise PlanError("INVALID_PEAK_EPOCH", "peak_epoch 必须大于 0")
    if request_count <= 0:
        raise PlanError("INVALID_REQUEST_COUNT", "request_count 必须大于 0")

    screenshot = config["screenshot"]
    window_seconds = int(screenshot["window_seconds"])
    result_limit = int(screenshot["result_limit"])
    minute_start_epoch = peak_epoch - peak_epoch % window_seconds
    minute_end_epoch = minute_start_epoch + window_seconds

    try:
        timezone = ZoneInfo(config["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise PlanError(
            "INVALID_TIMEZONE",
            f"未知时区：{config['timezone']}",
        ) from exc

    search_expression = extract_search_expression(service["query"])
    screenshot_query = build_screenshot_query(search_expression, result_limit)
    filter_info = config["sls"].get(
        "filter_info",
        {"fjcode": "()", "fq": ""},
    )

    def format_epoch(value: int) -> str:
        return datetime.fromtimestamp(value, timezone).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    return {
        "service": service_name,
        "peak_epoch": peak_epoch,
        "peak_time": format_epoch(peak_epoch),
        "request_count": request_count,
        "expected_tooltip": {
            "time": format_epoch(peak_epoch),
            "count": request_count,
        },
        "minute_start": format_epoch(minute_start_epoch),
        "minute_end": format_epoch(minute_end_epoch),
        "minute_start_epoch": minute_start_epoch,
        "minute_end_epoch": minute_end_epoch,
        "peak_offset_seconds": peak_epoch - minute_start_epoch,
        "hover_retry_count": int(screenshot["hover_retry_count"]),
        "capture_retry_count": int(screenshot["capture_retry_count"]),
        "search_expression": search_expression,
        "screenshot_query": screenshot_query,
        "query_url": build_query_url(
            config["sls"]["url"],
            screenshot_query,
            filter_info,
            minute_start_epoch,
            minute_end_epoch,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 platform-on-duty 的分钟级截图计划"
    )
    parser.add_argument("--service", required=True, help="config.toml 中的服务名")
    parser.add_argument("--peak-epoch", required=True, type=int, help="峰值秒时间戳")
    parser.add_argument("--request-count", required=True, type=int, help="峰值请求次数")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        plan = prepare_screenshot_plan(
            config,
            args.service,
            args.peak_epoch,
            args.request_count,
        )
    except (OSError, tomllib.TOMLDecodeError, PlanError) as exc:
        code = exc.code if isinstance(exc, PlanError) else "CONFIG_READ_ERROR"
        print(
            json.dumps(
                {"ok": False, "code": code, "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    print(json.dumps({"ok": True, "plan": plan}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
