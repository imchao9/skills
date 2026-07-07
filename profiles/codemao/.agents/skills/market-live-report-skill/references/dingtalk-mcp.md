# DingTalk Spreadsheet MCP Notes

This skill is aligned to the real DingTalk spreadsheet MCP schema discovered from the user's server.

## Core tools

- `create_sheet`
- `get_all_sheets`
- `get_sheet`
- `update_range`
- `append_rows`

These names are used by the default adapter in this skill.

## Required runtime inputs

- `DINGTALK_MCP_TARGET`: registered `mcporter` target name, for example `钉钉表格`
- `DINGTALK_TABLE_ID` or `DINGTALK_NODE_ID`: DingTalk table URL or nodeId
- `DINGTALK_SHEET_NAME`: target worksheet name

## Writing strategy used by this skill

The parser produces screenshot-style seven-column rows:

- `日期`
- `直播ID`
- `事项`
- `时间`
- `预计人数/覆盖人数`
- `实际人数`
- `值班安排`

The writer uses `sheet_rows_sparse` and `sheet_matrix_sparse`:

- first row contains `日期` and `值班安排`
- subsequent rows leave those two columns empty
- `直播ID` is filled on every live row

## Supported write modes

- `append-rows`: append rows to the end of an existing worksheet
- `update-range`: overwrite a fixed A1 range such as `A1:G5`

## First-version limitation

This skill does not attempt to:

- merge cells
- copy existing cell styles
- auto-detect section boundaries in the current sheet

Those actions depend on whether the target MCP exposes formatting tools. If needed later, add them through a custom adapter after verifying the actual tool schema from `mcporter list <target> --schema`.

## Example local MCP config

```json
{
  "mcpServers": {
    "钉钉表格": {
      "type": "streamable-http",
      "url": "https://mcp-gw.dingtalk.com/server/..."
    }
  }
}
```

When this config is present locally, pass `--target "钉钉表格"` to the helper scripts.
