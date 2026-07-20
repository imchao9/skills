# market-live-report-skill

将固定格式的中文「直播报备」文本解析为结构化 JSON，并写入钉钉表格、创建钉钉日历日程。既可作为 [Cursor Agent Skill](https://cursor.com/docs/agent/skills) 使用，也可在本仓库用 Node 脚本独立运行。

**本仓库为唯一源码目录。** 日常开发与修改请直接在本项目（`/Users/cm/IdeaProjects/dingtalk-live-report-table`）进行；`~/.cursor/skills/` 与 `~/.codex/skills/` 下同名目录已软链到此仓库，Cursor / Codex 会自动加载最新内容。

详细命令与输入格式见 [SKILL.md](./SKILL.md)；字段与映射见 [references/schema.md](./references/schema.md)；MCP 约定见 [references/dingtalk-mcp.md](./references/dingtalk-mcp.md)。

## 环境要求

- **Node.js**（建议 18+）
- 写入钉钉时：**[mcporter](https://github.com/modelcontextprotocol/mcporter)** 已安装且在 `PATH` 中
- 已在 mcporter 中注册钉钉 MCP 目标，例如 `钉钉表格`、`钉钉日历`

本机若使用 n 管理 Node，命令前可加：

```bash
export PATH=/Users/cm/.n/bin:$PATH
```

## 首次配置

1. 复制本地配置（勿提交 git）：

```bash
cp references/default-table-node.local.example.json references/default-table-node.local.json
cp references/user-id-map.local.example.json references/user-id-map.local.json
```

2. 编辑 `default-table-node.local.json` 中的 `node_id`（钉钉文档节点 URL）。
3. 编辑 `user-id-map.local.json`：值班人姓名 → 钉钉 `userId`（创建日历时添加参与人需要）。

可选：复制并调整 `references/dingtalk-spreadsheet-adapter.example.json`、`references/dingtalk-calendar-adapter.example.json`。

## 快速开始

### 生成直播值班文档（2026 目录）

1. 配置 API Cookie：可在运行采集/补数命令时临时传入 `--cookie 'key=value; ...'`。
   也可以写入本地配置：`cp references/live-stream-api.local.example.json references/live-stream-api.local.json`

```bash
pbpaste | node scripts/set_live_stream_cookie.js --stdin --pretty
```

2. 开播后第 15 / 20 / 30 分钟采集：

```bash
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 15
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 20
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 30
```

临时使用本次 cookie：

```bash
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 15 --cookie 'PASTE_COOKIE_VALUE'
```

只传 cookie 的简化入口：

```bash
node scripts/run_with_cookie.js --cookie 'PASTE_COOKIE_VALUE' --pretty
```

也可以不传 cookie。脚本会读取本地已保存 cookie 并用今日第一场直播 ID 校验；如果 cookie 过期或不存在，会打开 `https://internal-account.codemao.cn/login`，等你登录成功后自动提取并保存 cookie，再继续采集：

```bash
node scripts/run_with_cookie.js --pretty
```

不希望自动打开浏览器时：

```bash
node scripts/run_with_cookie.js --no-login-if-expired --pretty
```

也可以从剪贴板读取，避免 cookie 留在命令历史：

```bash
pbpaste | node scripts/run_with_cookie.js --stdin --pretty
```

该入口默认读取钉钉表格 `https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr`，并按日期自动选择 `M5W4` 这类自然周 sheet。找到今日直播且表格包含 `直播ID` 列时，会先用第一场直播接口校验 cookie，再启动自动采集；找不到今日直播时只保存 cookie；找到今日行但没有 `直播ID` 时，会保存 cookie 并提示无法校验/采集。

或在开播前启动自动定时采集：

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --cookie 'PASTE_COOKIE_VALUE' --pretty
```

不传 `--cookie` 时，采集调度也会先读取本地配置并用第一场直播 ID 校验 cookie；如果缺失或失效，会自动打开浏览器登录并保存新 cookie。需要禁用自动登录时加：

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --no-login-if-expired --pretty
```

直播通常约 1 小时结束。需要在开播 2 小时后把最终观看总人数回写到钉钉表格 `实际人数` 列时，启动：

```bash
node scripts/schedule_actual_count_update.js \
  --raw input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/Obva6QBXJw9w2ZrQI6bN2RwGWn4qY5Pr" \
  --auto-sheet \
  --pretty
```

该脚本按 `直播ID` 定位行，取直播接口 `data.totalCount` 写入 `实际人数`。先预览计划可加 `--dry-run`；补跑已过去的直播可加 `--collect-past`。

`schedule_actual_count_update.js` 同样会在启动时校验 cookie，失效时自动打开浏览器登录；禁用方式同样是 `--no-login-if-expired`。

同时启动监控看板截图任务：

```bash
node scripts/schedule_monitor_dashboard_screenshots.js --raw input.txt --pretty
```

该脚本会直接打开 `https://grafana.codemao.cn/d/SpSQKcpMl13/ying-xiao-zhi-bo-overviews?orgId=1&refresh=30s`，并在开播后 15 / 20 / 30 分钟截图到 `output/duty-docs/assets/YYYY-MM-DD/`。每个时间点默认截三张：顶部概览、微服务与 Pod 资源曲线图、数据库 Overviews。

截图默认使用每个采集点的绝对时间范围（`from=开播时间`、`to=开播时间+分钟数`），所以补截历史直播时不会误用 Grafana 的 `Last 30 minutes`。如果确实要保留当前看板时间范围，可加 `--current-time-range`。

3. 生成并导出正文（标题 `YYYY-MM-DD 直播值班记录`）：

```bash
node scripts/publish_duty_document.js --raw input.txt --pretty
```

导出 Markdown 表格版：

```bash
node scripts/publish_duty_document.js --raw input.txt --format markdown --include-monitor-screenshots --pretty
```

资源截图会按 `15/20/30分钟资源整体使用情况` 分组，并在标题后直接写入图片。

4. （可选）在 Cursor 配置 **钉钉文档 MCP mcpId=9629** 后自动创建在线文档：

```bash
node scripts/publish_duty_document.js --raw input.txt --dingtalk-doc --pretty
```

配置说明：[references/dingtalk-doc-mcp.md](./references/dingtalk-doc-mcp.md)。默认目录：`https://alidocs.dingtalk.com/i/nodes/a9E05BDRVQ6AaedDFp9D6klbJ63zgkYA`。

### 仅解析（不写钉钉）

```bash
node scripts/parse_live_report.js examples/sample-input.txt --pretty
```

或从剪贴板（macOS）：

```bash
pbpaste | node scripts/parse_live_report.js --pretty
```

### 校验 MCP 是否可用

```bash
DINGTALK_MCP_TARGET="钉钉表格" \
node scripts/check_dingtalk_spreadsheet_mcp.js --target "$DINGTALK_MCP_TARGET" --pretty
```

### 预览写表 + 日程（dry-run）

```bash
node scripts/process_live_report.js \
  --raw examples/sample-input.txt \
  --node-id "$(node -p "require('./references/default-table-node.local.json').node_id")" \
  --auto-sheet \
  --dry-run \
  --pretty
```

### 一键写表并创建日程

```bash
node scripts/process_live_report.js \
  --raw examples/sample-input.txt \
  --node-id "https://alidocs.dingtalk.com/i/nodes/YOUR_NODE_ID" \
  --auto-sheet \
  --pretty
```

## 脚本一览

| 脚本 | 作用 |
|------|------|
| `parse_live_report.js` | 解析报备 → JSON / 表格行 |
| `write_dingtalk_spreadsheet.js` | 通过 MCP 写入钉钉表格 |
| `build_schedule_payload.js` | 生成日历事件 payload |
| `create_dingtalk_schedule.js` | 通过 MCP 创建日程并加参与人 |
| `fetch_live_user_statistics.js` | 查询单场实时人数 API |
| `collect_live_stats.js` | 缓存单场某时段快照 |
| `collect_live_stats_batch.js` | 按报备批量缓存某时段 |
| `schedule_live_stats_collection.js` | 按开播时间自动在 15/20/30 分钟采集 |
| `schedule_actual_count_update.js` | 按开播时间自动在 120 分钟后回写表格实际人数 |
| `schedule_monitor_dashboard_screenshots.js` | 按开播时间自动在 15/20/30 分钟截监控看板 |
| `build_duty_document.js` | 生成值班文档正文 |
| `publish_duty_document.js` | 导出标题 + 正文到 `output/duty-docs/` |
| `process_live_report.js` | 写表 + 建日程 + 可选值班文档 |
| `check_dingtalk_spreadsheet_mcp.js` | 检查表格 MCP 工具是否齐全 |

## 工作表命名（`--auto-sheet`）

按自然周（周一至周日）路由到 `M{月}W{当月第几周}`，例如 `2026-05-05` → `M5W1`。跨月周以该周周一所在月份为准。

## 在 Cursor 中使用

将本目录作为 skill 路径之一（或软链到 `~/.cursor/skills/market-live-report-skill`），在对话中提供标准格式报备文案，并说明「按 market-live-report-skill 处理」即可。Agent 会读取 `SKILL.md` 并调用上述脚本与钉钉 MCP。

## 仓库结构

```
├── SKILL.md              # Agent skill 主文档
├── README.md             # 本文件（开发说明）
├── scripts/              # Node 脚本
├── references/           # schema、MCP 说明、本地配置示例
└── agents/openai.yaml    # Agent 元数据
```

## 安全说明

`references/*.local.json` 含文档 URL 与 userId，已加入 `.gitignore`。请勿将真实配置提交到远程仓库。
