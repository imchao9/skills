#!/usr/bin/env python3

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_run import (
    DEFAULT_CONFIG,
    PlanError,
    RunInputs,
    build_grafana_url,
    build_peak_query,
    extract_search_expression,
    load_config,
    prepare_plan,
    validate_config,
)
from prepare_screenshot import (
    build_screenshot_query,
    prepare_screenshot_plan,
)


class PrepareRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(Path(DEFAULT_CONFIG))
        cls.timezone = ZoneInfo("Asia/Shanghai")

    def test_default_today_clips_end_to_now(self) -> None:
        now = datetime(2026, 7, 23, 19, 40, 0, tzinfo=self.timezone)
        plan = prepare_plan(self.config, RunInputs("林纬达"), now)
        self.assertEqual(plan["actual_start"], "2026-07-23 18:30:00")
        self.assertEqual(plan["actual_end"], "2026-07-23 19:40:00")
        self.assertEqual(plan["date"], "2026-07-23")
        self.assertEqual(plan["grafana"]["start_epoch_ms"], 1784802600000)
        self.assertEqual(plan["grafana"]["end_epoch_ms"], 1784806800000)
        self.assertEqual(plan["grafana"]["screenshot_offset"], 4)
        self.assertIn("from=1784802600000", plan["grafana"]["query_url"])
        self.assertIn("to=1784806800000", plan["grafana"]["query_url"])

    def test_custom_active_window_clips_end_to_now(self) -> None:
        now = datetime(2026, 7, 23, 19, 40, 0, tzinfo=self.timezone)
        plan = prepare_plan(
            self.config,
            RunInputs("林纬达", "今天", "19:00", "21:00"),
            now,
        )
        self.assertEqual(plan["actual_start"], "2026-07-23 19:00:00")
        self.assertEqual(plan["actual_end"], "2026-07-23 19:40:00")

    def test_future_start_is_rejected(self) -> None:
        now = datetime(2026, 7, 23, 19, 40, 0, tzinfo=self.timezone)
        with self.assertRaisesRegex(PlanError, "未来时间") as caught:
            prepare_plan(
                self.config,
                RunInputs("林纬达", "今天", "21:00", "22:00"),
                now,
            )
        self.assertEqual(caught.exception.code, "FUTURE_START")

    def test_yesterday_uses_full_default_window(self) -> None:
        now = datetime(2026, 7, 23, 10, 0, 0, tzinfo=self.timezone)
        plan = prepare_plan(
            self.config,
            RunInputs("林纬达", "昨天"),
            now,
        )
        self.assertEqual(plan["actual_start"], "2026-07-22 18:30:00")
        self.assertEqual(plan["actual_end"], "2026-07-22 20:00:00")

    def test_original_query_stays_single_line_and_runtime_query_changes_grouping(self) -> None:
        original = self.config["services"][0]["query"]
        search = extract_search_expression(original)
        runtime = build_peak_query(search, 100)
        self.assertIn("url_extract_path", original)
        self.assertNotIn("url_extract_path", runtime)
        self.assertIn("group by peak_second", runtime)
        self.assertTrue(runtime.endswith("limit 100"))
        self.assertNotIn("\n", original)

    def test_text_review_query_without_pipe_is_preserved_as_search(self) -> None:
        original = self.config["services"][3]["query"]
        self.assertEqual(extract_search_expression(original), original)

    def test_screenshot_plan_uses_peak_minute_and_readable_seconds(self) -> None:
        plan = prepare_screenshot_plan(
            self.config,
            "auth-service",
            1784779270,
            19000,
        )
        self.assertEqual(plan["peak_time"], "2026-07-23 12:01:10")
        self.assertEqual(plan["minute_start"], "2026-07-23 12:01:00")
        self.assertEqual(plan["minute_end"], "2026-07-23 12:02:00")
        self.assertEqual(plan["peak_offset_seconds"], 10)
        self.assertEqual(plan["request_count"], 19000)
        self.assertEqual(
            plan["expected_tooltip"],
            {"time": "2026-07-23 12:01:10", "count": 19000},
        )
        self.assertEqual(plan["hover_retry_count"], 2)
        self.assertEqual(plan["capture_retry_count"], 2)
        self.assertIn("request_second", plan["screenshot_query"])
        self.assertIn("order by request_second asc", plan["screenshot_query"])
        self.assertTrue(plan["screenshot_query"].endswith("limit 100"))
        self.assertIn("startTime%3D1784779260", plan["query_url"])
        self.assertIn("endTime%3D1784779320", plan["query_url"])

    def test_screenshot_query_remains_single_line(self) -> None:
        query = build_screenshot_query("__tag__:_container_name_: auth-service", 100)
        self.assertNotIn("\n", query)
        self.assertIn("%Y-%m-%d %H:%i:%s", query)

    def test_grafana_url_replaces_relative_time_and_preserves_containers(self) -> None:
        url = build_grafana_url(
            self.config["grafana"]["url"],
            1784793000,
            1784797200,
        )
        self.assertNotIn("now-1h", url)
        self.assertIn("from=1784793000000", url)
        self.assertIn("to=1784797200000", url)
        self.assertEqual(url.count("var-Container="), 2)
        self.assertIn("var-Container=platform-account", url)
        self.assertIn("var-Container=auth-service", url)
        self.assertIn("var-NameSpace=pt-external", url)

    def test_screenshot_plan_rejects_unknown_service(self) -> None:
        with self.assertRaisesRegex(PlanError, "未知服务") as caught:
            prepare_screenshot_plan(
                self.config,
                "missing-service",
                1784779270,
                19000,
            )
        self.assertEqual(caught.exception.code, "UNKNOWN_SERVICE")

    def test_screenshot_plan_rejects_non_positive_count(self) -> None:
        with self.assertRaisesRegex(PlanError, "request_count 必须大于 0") as caught:
            prepare_screenshot_plan(
                self.config,
                "auth-service",
                1784779270,
                0,
            )
        self.assertEqual(caught.exception.code, "INVALID_REQUEST_COUNT")

    def test_text_review_screenshot_query_keeps_url_filter(self) -> None:
        plan = prepare_screenshot_plan(
            self.config,
            "文本审核",
            1784779270,
            19000,
        )
        self.assertIn('url: "/rpc/text/review"', plan["screenshot_query"])
        self.assertIn("group by request_second", plan["screenshot_query"])

    def test_capture_retry_count_cannot_be_negative(self) -> None:
        config = deepcopy(self.config)
        config["screenshot"]["capture_retry_count"] = -1
        with self.assertRaisesRegex(
            PlanError,
            "capture_retry_count 不能小于 0",
        ):
            validate_config(config)

    def test_grafana_capture_retry_count_cannot_be_negative(self) -> None:
        config = deepcopy(self.config)
        config["grafana"]["capture_retry_count"] = -1
        with self.assertRaisesRegex(
            PlanError,
            "grafana.capture_retry_count 不能小于 0",
        ):
            validate_config(config)


if __name__ == "__main__":
    unittest.main()
