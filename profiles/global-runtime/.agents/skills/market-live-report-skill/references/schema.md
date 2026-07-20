# Schema And Mapping

## Parser output

The parser returns JSON with this shape:

```json
{
  "meta": {
    "date": "2026-05-05",
    "weekday": "周二",
    "level": "A",
    "duty": "胡露"
  },
  "items": [
    {
      "title": "【机器人创想】编程猫开学第一课",
      "time": "18:55",
      "live_date": "2026-05-05",
      "live_id": "1541",
      "product_id": "无",
      "coverage": 1960,
      "estimated": 500,
      "actual": null
    }
  ],
  "table_rows": [
    {
      "日期": "周二05-05",
      "事项": "【机器人创想】编程猫开学第一课",
      "时间": "（18:55）",
      "预计人数/覆盖人数": "500/1960",
      "实际人数": "",
      "值班安排": "胡露",
      "直播ID": "1541",
      "商品ID": "无",
      "保障等级": "A"
    }
  ],
  "sheet_rows_sparse": [
    {
      "日期": "周二05-05",
      "直播ID": "1541",
      "事项": "【机器人创想】编程猫开学第一课",
      "时间": "（18:55）",
      "预计人数/覆盖人数": "500/1960",
      "实际人数": "",
      "值班安排": "胡露"
    },
    {
      "日期": "",
      "直播ID": "1542",
      "事项": "【编程新起点】编程猫开学第一课",
      "时间": "（18:55）",
      "预计人数/覆盖人数": "2800/11563",
      "实际人数": "",
      "值班安排": ""
    }
  ],
  "sheet_matrix_sparse": [
    ["周二05-05", "1541", "【机器人创想】编程猫开学第一课", "（18:55）", "500/1960", "", "胡露"],
    ["", "1542", "【编程新起点】编程猫开学第一课", "（18:55）", "2800/11563", "", ""]
  ],
  "warnings": [],
  "errors": []
}
```

## Field mapping

Shared metadata:

- `日期` header -> `meta.date`
- `星期` header -> `meta.weekday`
- `保障等级` header -> `meta.level`
- `值班后端` or `值班安排` -> `meta.duty`

Per-item fields:

- title line -> `item.title`
- `开播时间` -> `item.time` and `item.live_date`
- `直播ID` -> `item.live_id`
- `商品ID` -> `item.product_id`
- `覆盖人数` -> `item.coverage`
- `预约人数` or `预约` -> `item.reserved`
- `预估参与` or `预计参与` or `预计人数` -> `item.estimated`
- `实际人数` -> `item.actual`

Table row columns:

- `日期` -> `weekday + MM-DD`, for example `周二05-05`
- `直播ID` -> `item.live_id`
- `事项` -> `item.title`
- `时间` -> `（HH:MM）`
- `预计人数/覆盖人数` -> `estimated/coverage`, or `/coverage` if `estimated` is empty
- `实际人数` -> empty string when unknown
- `值班安排` -> `meta.duty`

Recommended extension columns:

- `商品ID`
- `保障等级`

Spreadsheet-oriented rows:

- `sheet_rows_sparse` -> first row keeps `日期` and `值班安排`, subsequent rows blank them
- `sheet_rows_full` -> every row repeats all seven visible spreadsheet columns
- `sheet_matrix_sparse` -> two-dimensional array aligned with A:G for MCP write operations
- `sheet_matrix_full` -> two-dimensional array aligned with A:G with repeated date and duty

## Validation

Hard errors:

- no live items found
- missing live title
- missing time
- missing live ID
- missing coverage
- cannot determine final date

Warnings:

- weekday omitted and auto-computed
- reserved (预约人数) value missing
- estimated value missing
- actual value missing
- product ID missing

## DingTalk write contract

The writer layer should accept:

- `table_rows` for record-style writes with extension metadata
- `sheet_rows_sparse` or `sheet_matrix_sparse` for spreadsheet A:G writes

Recommended contract:

```json
{
  "document_id": "your-target-id",
  "sheet_id": "optional-sheet-id",
  "rows": [
    {
      "日期": "周二05-05",
      "直播ID": "1541",
      "事项": "【机器人创想】编程猫开学第一课",
      "时间": "（18:55）",
      "预计人数/覆盖人数": "500/1960",
      "实际人数": "",
      "值班安排": "胡露"
    }
  ]
}
```

The writer should implement:

- column existence checks
- duplicate detection by `日期 + 直播ID` when extension columns exist
- batch write with per-row error reporting
- dry-run preview before final commit

## DingTalk calendar contract

Calendar payloads are built from the same parsed report and use:

- title -> `直播值班（保障等级+直播版本）`
- attendees -> `值班后端 + 固定胡露 + 额外通知人`
- duration -> default `60` minutes from the first live start time

Participant mapping notes:

- keep the local name-to-id map in `references/user-id-map.local.json`
- the current DingTalk calendar MCP accepts numeric uid values for participant operations
- if your local map stores values like `userId_192674073`, the calendar writer normalizes them to `192674073` before calling MCP
