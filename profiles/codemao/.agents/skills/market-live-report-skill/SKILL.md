---
name: market-live-report-skill
description: Parse Chinese live-report text into DingTalk spreadsheet rows and calendar duty events, and run the daily live-duty document workflow. Use this when the user invokes the skill to collect 15/20/30 minute stats, capture Grafana screenshots, generate a duty document, or when they provide a standard live-report message for spreadsheet/calendar scheduling.
---

# Market Live Report Skill

Use this skill when the input is a fixed-format live-report message and the goal is to turn it into structured records for a DingTalk spreadsheet.

Prefer the bundled parser script over ad hoc extraction. The script gives deterministic field mapping and validation, while the model handles edge cases and the final write step.

## Default intent routing

When the user only invokes this skill, or says to run/use `market-live-report-skill` without adding a new live-report block, treat the request as the daily duty-document workflow:

1. read today's live rows from the default DingTalk spreadsheet and validate the live-stream API cookie with the first available `直播ID`;
2. if the cookie is missing or expired, open `https://internal-account.codemao.cn/login`, wait for browser login, save the refreshed cookie locally, close the browser, and validate again;
3. collect or schedule 15 / 20 / 30 minute live statistics;
4. capture or backfill Grafana monitor dashboard screenshots;
5. generate the daily `YYYY-MM-DD 直播值班记录` document;
6. schedule a T+120 minute backfill that writes each live's final `totalCount` into the DingTalk spreadsheet `实际人数` column.

When the user includes live-duty report text or explicit duty scheduling information (`日期` / `开播时间` / `直播ID` / `值班后端` / `保障等级`), additionally perform the scheduling workflow:

1. write rows to the DingTalk spreadsheet;
2. create the DingTalk calendar duty event.

If both meanings are possible, prefer doing the duty-document workflow first and then the spreadsheet/calendar workflow from the same parsed report.

## Prerequisites for MCP writing

- `node` available locally
- `mcporter` installed and available in `PATH`
- a DingTalk MCP target available as a registered `mcporter` name

## Default 钉钉表格（本机约定）

长期默认写入的文档节点见 `references/default-table-node.local.json` 中的 `node_id`。用户未指定其它文档时，使用其中 URL 作为 `process_live_report.js` / `write_dingtalk_spreadsheet.js` 的 `--node-id`。

## Default 直播值班文档目录（2026）

每日一篇文档，标题 `YYYY-MM-DD 直播值班记录`。目录见 `references/duty-docs-folder.local.json`：

`https://alidocs.dingtalk.com/i/nodes/a9E05BDRVQ6AaedDFp9D6klbJ63zgkYA`

正文含各场 15 / 20 / 30 分钟 `观看总人数`、`在线人数`（来自营销后台 API + 本地缓存）。详见 `references/duty-document.md`。

自动创建文档使用 **钉钉文档 MCP（mcpId=9629）**，不是表格 MCP。配置见 `references/dingtalk-doc-mcp.md`（能力中心实例示例：`instanceId=686514`）。

## Supported workflow

1. Accept a fixed-format Chinese message containing shared metadata and one or more live-report blocks.
2. Run `scripts/parse_live_report.js` to extract structured JSON, full table rows, and spreadsheet-style sparse rows.
3. Review parser warnings before writing any data.
4. Validate the live DingTalk MCP schema with `scripts/check_dingtalk_spreadsheet_mcp.js`.
5. Use `scripts/write_dingtalk_spreadsheet.js` to create a sheet and write screenshot-style seven-column rows with the real DingTalk MCP tools: `create_sheet`, `update_range`, or `append_rows`.
6. Use `scripts/build_schedule_payload.js` to generate a schedule-notification payload from the same report input.
7. Use `scripts/create_dingtalk_schedule.js` with the DingTalk calendar MCP to create the real calendar event and add attendees.
8. At T+15 / T+20 / T+30 after each live starts, run `scripts/collect_live_stats.js` or `scripts/collect_live_stats_batch.js` to cache API snapshots under `references/live-stats-cache/YYYY-MM-DD.json`.
9. If monitor evidence is needed, run `scripts/schedule_monitor_dashboard_screenshots.js` before the live starts. It opens `https://grafana.codemao.cn/d/SpSQKcpMl13/ying-xiao-zhi-bo-overviews?orgId=1&refresh=30s` directly, captures screenshots at T+15 / T+20 / T+30 under `output/duty-docs/assets/YYYY-MM-DD/`, then closes the browser.
10. Use `scripts/build_duty_document.js` or `scripts/publish_duty_document.js` to render the daily duty document body (title + 分时段观看人数). When publishing to DingTalk with monitor screenshots, pass `--dingtalk-doc --include-monitor-screenshots`; the script uploads local screenshots to the DingTalk document folder and inserts DingTalk file links into the online document.
11. Use `scripts/schedule_actual_count_update.js` to update the spreadsheet `实际人数` column at T+120 after each live starts. The value is the live API `data.totalCount`.
12. Prefer `scripts/process_live_report.js` when the user wants one-step execution for spreadsheet writing, calendar creation, and/or duty document output.

## Sheet routing rule

By default you may still pass `--sheet-name` manually.

If you use `--auto-sheet`, the writer derives the target sheet from the parsed live date using the user's chosen rule:

- use natural Monday-to-Sunday weeks
- sheet name format is `M{month}W{weekOfMonth}`
- example: `2026-05-05` and `2026-05-08` both map to `M5W1`
- if a week crosses months, group it under the month of that week's Monday
- when a new weekly sheet is created, copy formats from `M6W5` by default, then repeat `M6W5!A2:G5` data-row formats over later data rows; use `--style-template-sheet <sheetNameOrId>` / `DINGTALK_STYLE_TEMPLATE_SHEET` or `--style-data-range <A1Range>` / `DINGTALK_STYLE_DATA_RANGE` to override, or `--no-copy-template-style` to skip

## Input contract

Preferred format:

```text
日期：2026-05-05
星期：周二
保障等级：A
值班后端：胡露

【机器人创想】编程猫开学第一课
开播时间：05-05 18:55
直播ID：1541
商品ID：无
覆盖人数：1960
预约人数：180
预估参与：500
```

`预约人数` 用于生成值班文档；未填写时仍会生成文档，但该字段留空并产生 warning。

The parser also tolerates these optional noise lines and ignores them:

- `申请事项`
- `事项详情`
- `当日直播日程如下：`
- separator lines such as `====`

## Commands

Parse from a file:

```bash
node scripts/parse_live_report.js input.txt
```

Parse from stdin and pretty-print JSON:

```bash
pbpaste | node scripts/parse_live_report.js --pretty
```

Infer the year when the header omits `日期`:

```bash
node scripts/parse_live_report.js --year 2026 input.txt
```

Build a schedule payload from the same report:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/build_schedule_payload.js \
  --raw input.txt \
  --duration-minutes 60 \
  --reminder-minutes 30 \
  --pretty
```

Create the real DingTalk calendar event from a prepared payload:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/create_dingtalk_schedule.js \
  --payload schedule.json \
  --target "钉钉日历" \
  --pretty
```

One-step preview for both spreadsheet and calendar:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/process_live_report.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --dry-run \
  --pretty
```

One-step real execution for both spreadsheet and calendar:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/process_live_report.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --pretty
```

Validate that the configured DingTalk spreadsheet MCP exposes the expected tools:

```bash
PATH=/Users/cm/.n/bin:$PATH \
DINGTALK_MCP_TARGET="钉钉表格" \
node scripts/check_dingtalk_spreadsheet_mcp.js --target "$DINGTALK_MCP_TARGET" --pretty
```

Preview the rows that would be written to the spreadsheet:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/write_dingtalk_spreadsheet.js \
  --raw input.txt \
  --sheet-name M5W1 \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --target "钉钉表格" \
  --mode update-range \
  --include-header \
  --dry-run \
  --pretty
```

Create a new sheet and write header plus rows into `A1:G{n}`:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/write_dingtalk_spreadsheet.js \
  --raw input.txt \
  --sheet-name M5W2 \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --target "钉钉表格" \
  --create-sheet \
  --start-row 1 \
  --mode update-range \
  --include-header \
  --pretty
```

Newly created sheets copy the current table style from `M6W5` by default, using `copy_range pasteType=formats` over `A1:G200`. If actual data has more rows than the template data block, the writer repeats `M6W5!A2:G5` formats onto later data rows before merging date/duty columns. Override the template sheet when needed:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/write_dingtalk_spreadsheet.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --target "钉钉表格" \
  --auto-sheet \
  --style-template-sheet M6W5 \
  --pretty
```

Append rows to an existing sheet without rewriting the header:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/write_dingtalk_spreadsheet.js \
  --raw input.txt \
  --sheet-name M5W1 \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --target "钉钉表格" \
  --mode append-rows \
  --pretty
```

Append rows with automatic natural-week sheet selection:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/write_dingtalk_spreadsheet.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --target "钉钉表格" \
  --auto-sheet \
  --mode append-rows \
  --pretty
```

Configure live stream API cookie (never commit):

```bash
cp references/live-stream-api.local.example.json references/live-stream-api.local.json
```

For one-off runs, pass the copied Cookie header value directly. Quote the value because it usually contains semicolons:

```bash
node scripts/collect_live_stats_batch.js \
  --raw input.txt \
  --milestone 15 \
  --cookie 'PASTE_COOKIE_VALUE'
```

When the user only provides a cookie and no live-report text, use the simple entrypoint. By default it reads today's rows from the DingTalk spreadsheet `https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr`, auto-selecting the natural-week sheet such as `M5W4`. If today's rows include a `直播ID` column, it validates the cookie against the first live API and starts the automatic collector. If no today's live is found, it saves the cookie locally without failing. If rows exist but no `直播ID` column is present, it saves the cookie and reports that validation/collection was skipped.

```bash
node scripts/run_with_cookie.js --cookie 'PASTE_COOKIE_VALUE' --pretty
```

When no cookie is passed, `run_with_cookie.js` reads the local config cookie first. If a live ID is available, it validates that cookie before collecting. If the cookie is missing or expired, it opens `https://internal-account.codemao.cn/login`; after the user finishes login, `scripts/login_live_stream_cookie.js` extracts Codemao cookies from the browser debugging session, saves them to `references/live-stream-api.local.json`, closes the browser, validates again, and then continues.

```bash
node scripts/run_with_cookie.js --pretty
```

Disable browser login fallback:

```bash
node scripts/run_with_cookie.js --no-login-if-expired --pretty
```

Safer stdin form:

```bash
pbpaste | node scripts/run_with_cookie.js --stdin --pretty
```

Override the spreadsheet source when needed:

```bash
node scripts/run_with_cookie.js \
  --cookie 'PASTE_COOKIE_VALUE' \
  --table-node-id 'https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr' \
  --pretty
```

Write the copied Cookie header value into the local config without putting it in shell history:

```bash
pbpaste | node scripts/set_live_stream_cookie.js --stdin --pretty
```

Collect stats at milestone (repeat at 15 / 20 / 30 minutes):

```bash
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 15
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 20
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 30
```

Or start an automatic collector before the lives begin:

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --pretty
```

`schedule_live_stats_collection.js` also validates the cookie before scheduling. It uses the first live ID in the parsed report and opens the browser login flow automatically when the saved cookie is missing or expired.

Or start the automatic collector with a temporary cookie:

```bash
node scripts/schedule_live_stats_collection.js \
  --raw input.txt \
  --cookie 'PASTE_COOKIE_VALUE' \
  --pretty
```

Preview the collection plan:

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --dry-run --pretty
```

Preview the T+120 actual-count update plan:

```bash
node scripts/schedule_actual_count_update.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --dry-run \
  --pretty
```

Start the automatic T+120 update. It finds rows by `直播ID` and writes `data.totalCount` into `实际人数` only:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/schedule_actual_count_update.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --pretty
```

`schedule_actual_count_update.js` uses the same cookie validation and browser-login fallback before waiting for T+120. Disable the fallback only when explicitly requested:

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --no-login-if-expired --pretty
node scripts/schedule_actual_count_update.js --raw input.txt --no-login-if-expired --pretty
```

Schedule monitor dashboard screenshots:

```bash
node scripts/schedule_monitor_dashboard_screenshots.js \
  --raw input.txt \
  --pretty
```

By default screenshot URLs use absolute Grafana time ranges (`from=live start`, `to=milestone time`) so historical backfills do not capture the current `Last 30 minutes`. Use `--current-time-range` only when a live dashboard-relative screenshot is intended.
After all requested screenshots are captured, or if dashboard initialization fails, the screenshot script closes the browser it opened.

Each milestone captures three viewport screenshots by default:
- `overview`: top Ingress / microservice / Pod summary area;
- `microservice-pod-curves`: the lower microservice and Pod resource curve area;
- `database-overviews`: the RDS / MongoDB / Redis overview area.

Use `--screenshot-sections overview,microservice-pod-curves,database-overviews` to choose sections, or `--single-screenshot` for the legacy top-only screenshot.

Preview monitor screenshot jobs:

```bash
node scripts/schedule_monitor_dashboard_screenshots.js \
  --raw input.txt \
  --dry-run \
  --pretty
```

Generate duty document with cached stats:

```bash
node scripts/build_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache
```

Generate Markdown table duty document:

```bash
node scripts/publish_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --format markdown \
  --include-monitor-screenshots \
  --pretty
```

Publish Markdown with monitor screenshots to DingTalk without writing a local duty-document body/meta file. This uploads matching local screenshots under `output/duty-docs/assets/YYYY-MM-DD/` before creating/updating the online document:

```bash
node scripts/publish_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --format markdown \
  --include-monitor-screenshots \
  --dingtalk-doc \
  --skip-local-output \
  --doc-target "钉钉文档" \
  --pretty
```

Publish local files and create DingTalk doc (mcpId=9629):

```bash
node scripts/publish_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --dingtalk-doc \
  --doc-target "钉钉文档" \
  --pretty
```

Create doc only:

```bash
node scripts/create_dingtalk_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --target "钉钉文档" \
  --pretty
```

Validate doc MCP tools:

```bash
node scripts/check_dingtalk_doc_mcp.js --target "钉钉文档" --pretty
```

Probe API for one live:

```bash
node scripts/fetch_live_user_statistics.js --live-id 952 --pretty
```

One-step processing including duty document:

```bash
PATH=/Users/cm/.n/bin:$PATH \
node scripts/process_live_report.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --duty-doc \
  --duty-doc-dingtalk \
  --duty-doc-skip-local-output \
  --duty-doc-include-monitor-screenshots \
  --skip-sheet \
  --skip-calendar \
  --pretty
```

Format details: `references/duty-document.md`.

## Validation rules

- Require at least one live item.
- Require each item to contain `title`, `time`, `live_id`, and `coverage`.
- Compute `weekday` from `date` when absent.
- If `date` is absent, infer it from the first `开播时间` using `--year` or the current year.
- Preserve optional fields such as `product_id`, `reserved`, `estimated`, and `actual`.

If the parser returns errors, do not write to DingTalk. Ask for corrected input or fix the format first.

## Writing guidance

Read `references/schema.md` and `references/dingtalk-mcp.md` before wiring a DingTalk writer. Use the parser output instead of re-parsing the raw text in the final write step.

Visible spreadsheet columns:

- `日期`
- `直播ID`
- `事项`
- `时间`
- `预计人数/覆盖人数`
- `实际人数`
- `值班安排`

If the DingTalk MCP is unavailable, stop after producing:

- `parsed.meta`
- `parsed.items`
- `parsed.table_rows`
- `parsed.sheet_rows_sparse`
- `parsed.sheet_matrix_sparse`
- `schedule_payload`

## Working style

- Keep the raw input unchanged in the conversation or a temp file for traceability.
- Show a short preview of rows before writing.
- Prefer deterministic row generation from the script.
- Only let the model fill missing values when the user explicitly confirms the assumption.
- For spreadsheet writes, use `sheet_rows_sparse` unless the user explicitly asks to repeat the date and duty columns on every row.
- When creating a new sheet from scratch, prefer `--include-header` and `--mode update-range`.
- Use `--auto-sheet` when the user wants natural-week routing such as `M5W1`, `M5W2`, and so on.
- If the auto-routed weekly sheet does not exist yet, the writer will create it and seed the header plus merged date/duty cells automatically.
- When creating a weekly sheet, copy formats from `M6W5` by default and repeat the `A2:G5` data-row style block for additional rows. Use `--style-template-sheet` / `DINGTALK_STYLE_TEMPLATE_SHEET` or `--style-data-range` / `DINGTALK_STYLE_DATA_RANGE` to choose different sources.
- When appending rows to an existing sheet, merge `日期` and `值班安排` by contiguous same-day blocks. If the appended report date already exists immediately above, extend the existing day block (for example merge all 05-28 rows together) instead of creating a separate merge block for the new append.
- For schedule payloads, default the end time to `start + 60 minutes`.
- For schedule payloads, default attendees to `值班后端 + 固定胡露`, then append any extra notify targets found in the text.
- For schedule payloads, default the title to `直播值班（保障等级+直播版本）` when those fields exist.
- If `直播版本` is missing, infer it from `申请事项` when possible:
  `新版 -> 稳定版`, `IM/IM版/IM版本 -> IM版`.
- Keep the attendee name to `userId` mapping in `references/user-id-map.local.json` so the calendar writer can add real participants.
- When the user asks for a single action such as “处理下面报备，并同步写表和创建日程”, prefer `scripts/process_live_report.js`.
- When the user asks to “生成值班文档” / “写值班记录”, use `collect_live_stats_*` during the live, then `publish_duty_document.js` after caches exist.
- API cookie may be passed with `--cookie` for a one-off run, or stored in `references/live-stream-api.local.json` / `LIVE_STREAM_COOKIE`; never store cookies in skill source or commits.
- Wire 钉钉文档 MCP (mcpId=9629) in `~/.cursor/mcp.json`, then use `create_dingtalk_duty_document.js` or `publish_duty_document.js --dingtalk-doc`. Add `--include-monitor-screenshots --skip-local-output` when screenshots should be uploaded and embedded in the online document instead of writing a local duty-document body.
