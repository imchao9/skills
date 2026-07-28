#!/usr/bin/env python3
"""规范化值班统计时间，并生成每个服务的 SLS 秒级峰值查询 URL。"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sys
import tomllib
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.toml"


class PlanError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RunInputs:
    attendant: str
    date_text: str | None = None
    start_text: str | None = None
    end_text: str | None = None
    limit: int | None = None


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        config = tomllib.load(handle)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    for section in (
        "defaults",
        "sls",
        "screenshot",
        "grafana",
        "sheet",
        "services",
        "timezone",
    ):
        if section not in config:
            raise PlanError("CONFIG_MISSING", f"配置缺少 {section}")

    services = config["services"]
    if not isinstance(services, list) or not services:
        raise PlanError("CONFIG_SERVICES", "services 必须是非空列表")

    seen_names: set[str] = set()
    seen_headers: set[str] = set()
    for index, service in enumerate(services):
        for field in ("name", "header_keyword", "query"):
            value = service.get(field)
            if not isinstance(value, str) or not value.strip():
                raise PlanError(
                    "CONFIG_SERVICE_FIELD",
                    f"services[{index}].{field} 不能为空",
                )
        if "\n" in service["query"] or "\r" in service["query"]:
            raise PlanError(
                "CONFIG_QUERY_MULTILINE",
                f"{service['name']} 的 query 必须保持单行",
            )
        normalized_name = service["name"].strip().casefold()
        normalized_header = normalize_header(service["header_keyword"])
        if normalized_name in seen_names:
            raise PlanError("CONFIG_DUPLICATE_NAME", f"服务名重复：{service['name']}")
        if normalized_header in seen_headers:
            raise PlanError(
                "CONFIG_DUPLICATE_HEADER",
                f"表头关键字重复：{service['header_keyword']}",
            )
        seen_names.add(normalized_name)
        seen_headers.add(normalized_header)

    sls = config["sls"]
    for field in ("url", "initial_limit", "max_tie_limit", "retry_count"):
        if field not in sls:
            raise PlanError("CONFIG_SLS", f"sls 缺少 {field}")
    if int(sls["initial_limit"]) <= 0:
        raise PlanError("CONFIG_LIMIT", "initial_limit 必须大于 0")
    if int(sls["max_tie_limit"]) < int(sls["initial_limit"]):
        raise PlanError("CONFIG_LIMIT", "max_tie_limit 不能小于 initial_limit")

    screenshot = config["screenshot"]
    for field in (
        "window_seconds",
        "result_limit",
        "hover_retry_count",
        "capture_retry_count",
    ):
        if field not in screenshot:
            raise PlanError("CONFIG_SCREENSHOT", f"screenshot 缺少 {field}")
    if int(screenshot["window_seconds"]) != 60:
        raise PlanError(
            "CONFIG_SCREENSHOT",
            "window_seconds 必须为 60，以整分钟生成秒级柱状图",
        )
    if int(screenshot["result_limit"]) < 60:
        raise PlanError(
            "CONFIG_SCREENSHOT",
            "result_limit 不能小于 60",
        )
    if int(screenshot["hover_retry_count"]) < 0:
        raise PlanError(
            "CONFIG_SCREENSHOT",
            "hover_retry_count 不能小于 0",
        )
    if int(screenshot["capture_retry_count"]) < 0:
        raise PlanError(
            "CONFIG_SCREENSHOT",
            "capture_retry_count 不能小于 0",
        )

    grafana = config["grafana"]
    for field in ("url", "section_title", "capture_retry_count"):
        value = grafana.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise PlanError("CONFIG_GRAFANA", f"grafana 缺少 {field}")
    if int(grafana["capture_retry_count"]) < 0:
        raise PlanError(
            "CONFIG_GRAFANA",
            "grafana.capture_retry_count 不能小于 0",
        )

    sheet = config["sheet"]
    for field in (
        "url",
        "name",
        "date_header",
        "attendant_header",
        "screenshot_start_header",
        "image_row_height",
    ):
        if field not in sheet:
            raise PlanError("CONFIG_SHEET", f"sheet 缺少 {field}")


def normalize_header(value: str) -> str:
    return "".join(
        character
        for character in value.casefold()
        if not character.isspace() and character not in "-_"
    )


def parse_date(value: str | None, today: date) -> date:
    if value is None or not value.strip() or value.strip() in {"今天", "today"}:
        return today
    text = value.strip()
    if text in {"昨天", "yesterday"}:
        return today - timedelta(days=1)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise PlanError(
            "INVALID_DATE",
            "日期仅支持 今天、昨天 或 YYYY-MM-DD",
        ) from exc


def parse_clock(value: str, field: str) -> time:
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value.strip(), pattern).time()
        except ValueError:
            continue
    raise PlanError("INVALID_TIME", f"{field} 必须是 HH:MM 或 HH:MM:SS")


def parse_now(value: str | None, timezone: ZoneInfo) -> datetime:
    if value is None:
        return datetime.now(timezone).replace(microsecond=0)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PlanError("INVALID_NOW", "--now 必须是 ISO 8601 时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone).replace(microsecond=0)


def extract_search_expression(original_query: str) -> str:
    search_expression = original_query.split("|", 1)[0].strip()
    if not search_expression:
        raise PlanError("EMPTY_SEARCH", "原始查询缺少检索条件")
    return search_expression


def build_peak_query(search_expression: str, limit: int) -> str:
    return (
        f"{search_expression} | select __time__ as peak_second, "
        "count(*) as request_count group by peak_second "
        "order by request_count desc, peak_second asc "
        f"limit {limit}"
    )


def build_query_url(
    sls_url: str,
    query: str,
    filter_info: dict[str, Any],
    start_epoch: int,
    end_epoch: int,
) -> str:
    query_base64 = base64.b64encode(query.encode("utf-8")).decode("ascii")
    filter_base64 = base64.b64encode(
        json.dumps(filter_info, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).decode("ascii")
    inner = (
        f"encode=base64&queryString={query_base64}"
        f"&filterInfo={filter_base64}&queryTimeType=99"
        f"&startTime={start_epoch}&endTime={end_epoch}"
    )
    return f"{sls_url}?{quote(inner, safe='')}"


def build_grafana_url(
    dashboard_url: str,
    start_epoch: int,
    end_epoch: int,
) -> str:
    parts = urlsplit(dashboard_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"from", "to"}
    ]
    query.extend(
        [
            ("from", str(start_epoch * 1000)),
            ("to", str(end_epoch * 1000)),
        ]
    )
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def prepare_plan(
    config: dict[str, Any],
    inputs: RunInputs,
    now: datetime,
) -> dict[str, Any]:
    attendant = inputs.attendant.strip()
    if not attendant:
        raise PlanError("MISSING_ATTENDANT", "必须提供值班人")

    timezone_name = config["timezone"]
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise PlanError("INVALID_TIMEZONE", f"未知时区：{timezone_name}") from exc
    now = now.astimezone(timezone).replace(microsecond=0)

    run_date = parse_date(inputs.date_text, now.date())
    start_value = inputs.start_text or config["defaults"]["start"]
    end_value = inputs.end_text or config["defaults"]["end"]
    requested_start = datetime.combine(
        run_date,
        parse_clock(start_value, "开始时间"),
        tzinfo=timezone,
    )
    requested_end = datetime.combine(
        run_date,
        parse_clock(end_value, "结束时间"),
        tzinfo=timezone,
    )

    if requested_end <= requested_start:
        raise PlanError("CROSS_DAY_OR_REVERSED", "结束时间必须晚于开始时间，且不能跨天")
    if requested_start >= now:
        raise PlanError("FUTURE_START", "开始时间是未来时间，不执行")

    actual_end = min(requested_end, now)
    if actual_end <= requested_start:
        raise PlanError("EMPTY_WINDOW", "实际查询时间段为空")

    sls = config["sls"]
    limit = inputs.limit or int(sls["initial_limit"])
    if limit <= 0 or limit > int(sls["max_tie_limit"]):
        raise PlanError(
            "INVALID_LIMIT",
            f"limit 必须在 1 到 {sls['max_tie_limit']} 之间",
        )

    start_epoch = int(requested_start.timestamp())
    end_epoch = int(actual_end.timestamp())
    filter_info = sls.get("filter_info", {"fjcode": "()", "fq": ""})
    service_plans: list[dict[str, Any]] = []
    for screenshot_index, service in enumerate(config["services"]):
        original_query = service["query"]
        search_expression = extract_search_expression(original_query)
        peak_query = build_peak_query(search_expression, limit)
        service_plans.append(
            {
                "name": service["name"],
                "header_keyword": service["header_keyword"],
                "original_query": original_query,
                "search_expression": search_expression,
                "peak_query": peak_query,
                "query_url": build_query_url(
                    sls["url"],
                    peak_query,
                    filter_info,
                    start_epoch,
                    end_epoch,
                ),
                "screenshot_offset": screenshot_index,
            }
        )

    grafana = config["grafana"]
    return {
        "attendant": attendant,
        "timezone": timezone_name,
        "date": run_date.isoformat(),
        "requested_start": requested_start.strftime("%Y-%m-%d %H:%M:%S"),
        "requested_end": requested_end.strftime("%Y-%m-%d %H:%M:%S"),
        "actual_start": requested_start.strftime("%Y-%m-%d %H:%M:%S"),
        "actual_end": actual_end.strftime("%Y-%m-%d %H:%M:%S"),
        "start_epoch": start_epoch,
        "end_epoch": end_epoch,
        "limit": limit,
        "max_tie_limit": int(sls["max_tie_limit"]),
        "retry_count": int(sls["retry_count"]),
        "sheet": config["sheet"],
        "services": service_plans,
        "grafana": {
            "query_url": build_grafana_url(
                grafana["url"],
                start_epoch,
                end_epoch,
            ),
            "section_title": grafana["section_title"],
            "capture_retry_count": int(grafana["capture_retry_count"]),
            "start_epoch_ms": start_epoch * 1000,
            "end_epoch_ms": end_epoch * 1000,
            "screenshot_offset": len(service_plans),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 platform-on-duty 的确定性运行计划"
    )
    parser.add_argument("--attendant", required=True, help="值班人，必填")
    parser.add_argument("--date", dest="date_text", help="今天、昨天或 YYYY-MM-DD")
    parser.add_argument("--start", dest="start_text", help="HH:MM 或 HH:MM:SS")
    parser.add_argument("--end", dest="end_text", help="HH:MM 或 HH:MM:SS")
    parser.add_argument("--limit", type=int, help="本次秒级聚合返回上限")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--now", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        timezone = ZoneInfo(config["timezone"])
        now = parse_now(args.now, timezone)
        plan = prepare_plan(
            config,
            RunInputs(
                attendant=args.attendant,
                date_text=args.date_text,
                start_text=args.start_text,
                end_text=args.end_text,
                limit=args.limit,
            ),
            now,
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
