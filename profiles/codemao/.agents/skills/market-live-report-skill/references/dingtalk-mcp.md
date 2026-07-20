# DingTalk Spreadsheet MCP Notes

This skill is aligned to the real DingTalk spreadsheet MCP schema discovered from the user's server.

## Core tools

- `create_sheet`
- `get_all_sheets`
- `get_sheet`
- `update_range`
- `append_rows`
- `copy_range`

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

## Style behavior

When a new weekly sheet is created, the writer copies the current duty-table style from `M6W5` by default:

- source range: `A1:G200`
- destination: `A1` in the new sheet
- paste type: `formats`
- data row style range: `A2:G5`; repeated onto later data rows when the new sheet has more rows than the template data block

Pass `--style-template-sheet <sheetNameOrId>` to override the source sheet, `--style-data-range <A1Range>` to override the repeated data-row style block, set `DINGTALK_STYLE_TEMPLATE_SHEET` / `DINGTALK_STYLE_DATA_RANGE`, or pass `--no-copy-template-style` to skip format copying.

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
