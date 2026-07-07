# 钉钉文档 MCP（mcpId=9629）

用于在知识库/文件夹下**创建在线文档**并写入 Markdown，对应值班记录场景。

官方入口：

- 能力中心实例：`https://aihub.dingtalk.com/#/detail?instanceId=686514&detailType=instanceMcpDetail&mcpId=9629`
- MCP 广场：`https://mcp.dingtalk.com/#/detail?mcpId=9629`

## 与「钉钉表格」MCP 的区别

| MCP | 用途 |
|-----|------|
| 钉钉表格（你已在用） | 电子表格 `create_sheet` / `update_range` |
| **钉钉文档（9629）** | 在线文档 `create_document` / `update_document` |

值班文档应使用 **9629 文档 MCP**，不要用表格 MCP 代替。

## 配置 Cursor

1. 打开上述 AI 能力中心链接（需登录钉钉）。
2. 复制实例详情里的 **StreamableHttp URL**（形如 `https://mcp-gw.dingtalk.com/server/...?key=...`）。
3. 写入 `~/.cursor/mcp.json`：

```json
"钉钉文档": {
  "type": "streamable-http",
  "url": "PASTE_YOUR_STREAMABLE_HTTP_URL_HERE"
}
```

4. 重启 Cursor 或重载 MCP。

## 配置 mcporter（脚本调用）

```bash
mcporter config add dingtalk-docs --url "PASTE_YOUR_STREAMABLE_HTTP_URL_HERE"
```

脚本默认 `--target 钉钉文档`，也可用环境变量 `DINGTALK_DOC_MCP_TARGET`。

## 核心工具

- `create_document` — `name`、`folderId`、初始 `markdown`
- `update_document` — 已有文档 `nodeId`，`mode=overwrite|append`
- `search_documents` — 按标题关键字查找是否已存在当日文档

## 本 skill 中的脚本

```bash
node scripts/check_dingtalk_doc_mcp.js --target "钉钉文档"
node scripts/create_dingtalk_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --target "钉钉文档"
```

`publish_duty_document.js --dingtalk-doc` 会在生成本地 txt 后尝试调用文档 MCP 创建。
