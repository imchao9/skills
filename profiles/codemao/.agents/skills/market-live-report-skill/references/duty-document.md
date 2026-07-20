# 值班文档格式（2026）

每日一篇钉钉文档，标题：`YYYY-MM-DD 直播值班记录`（示例：`2026-05-16 直播值班记录`）。

默认目录见 `references/duty-docs-folder.local.json` 的 `folder_node_id`：

`https://alidocs.dingtalk.com/i/nodes/a9E05BDRVQ6AaedDFp9D6klbJ63zgkYA`

## 正文结构

1. 首行：`{N}场直播`
2. 每场直播：
   - `序号. 标题，预约人数：x，覆盖：x，预计：x`（来自报备；预约人数可来自 API 缓存）
   - `观看时长`
   - 第一场用 `观看人数`，其余场用 `总观看人数`
   - 每个时段（默认 15 / 20 / 30 分钟）：
     - `15分钟 `（首行时段标签后有一个空格）
     - `观看总人数：{totalCount}`
     - `在线人数：{onlineCount}`

可选：文末资源段（`--include-resource-section`）。

## 观看人数数据来源

接口（需登录 Cookie，**勿提交到 git**）：

`GET {baseUrl}/live-stream/{liveStreamId}/user-statistics`

默认 `baseUrl`: `https://lbk-mktadmin.codemao.cn`

响应 `data`：

| 字段 | 含义 |
|------|------|
| `totalCount` | 观看总人数 |
| `onlineCount` | 在线人数 |
| `reserveCount` | 预约人数 |

接口返回的是**实时快照**，没有历史分钟参数。要在 15 / 20 / 30 分钟记录准确数据，请在对应时刻执行采集脚本写入缓存。

### 配置 API

```bash
cp references/live-stream-api.local.example.json references/live-stream-api.local.json
# 编辑 cookie（或 export LIVE_STREAM_COOKIE='...'）
```

也可以不落本地文件，在单次命令里临时传入：

```bash
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 15 --cookie 'PASTE_COOKIE_VALUE'
node scripts/schedule_live_stats_collection.js --raw input.txt --cookie 'PASTE_COOKIE_VALUE' --pretty
```

如果只拿到 cookie，还没有显式传报备文件，可以用简化入口。它会默认读取钉钉表格并自动选择今日所在周 sheet；今日无直播时只保存 cookie；今日有直播但表格没有 `直播ID` 列时，只保存 cookie 并提示无法校验/采集：

```bash
node scripts/run_with_cookie.js --cookie 'PASTE_COOKIE_VALUE' --pretty
```

也可以不传 cookie。脚本会先读取本地配置中的 cookie，并在有今日直播 ID 时先校验是否有效；如果过期或不存在，会打开登录页，等用户登录成功后自动提取并保存 cookie：

```bash
node scripts/run_with_cookie.js --pretty
```

更安全的剪贴板形式：

```bash
pbpaste | node scripts/run_with_cookie.js --stdin --pretty
```

推荐用脚本从剪贴板写入，避免把 Cookie 留在 shell 历史：

```bash
pbpaste | node scripts/set_live_stream_cookie.js --stdin --pretty
```

Cookie 获取方式：

推荐自动获取：

```bash
node scripts/run_with_cookie.js --pretty
```

手动获取：

1. 用浏览器登录 `https://lbk-operational.codemao.cn/` 或能访问营销后台接口的后台页面。
2. 打开开发者工具 Network，找到 `https://lbk-mktadmin.codemao.cn/live-stream/{直播ID}/user-statistics` 请求。
3. 只复制 Request Headers 里的 `Cookie` 值，作为 `--cookie` 参数传入，或粘到 `references/live-stream-api.local.json` 的 `cookie` 字段，或设置 `LIVE_STREAM_COOKIE`。
4. 用 `node scripts/fetch_live_user_statistics.js --live-id 952 --cookie 'PASTE_COOKIE_VALUE' --pretty` 验证是否可用。

不要把完整 curl 或真实 Cookie 提交到仓库。

### 采集某场某个时段

```bash
node scripts/collect_live_stats.js --live-id 952 --milestone 15 --date 2026-05-16
```

### 按报备批量采集（同一时段所有场次）

```bash
node scripts/collect_live_stats_batch.js --raw input.txt --milestone 15
```

### 开播前自动定时采集

```bash
node scripts/schedule_live_stats_collection.js --raw input.txt --dry-run --pretty
node scripts/schedule_live_stats_collection.js --raw input.txt --pretty
```

脚本会按每场 `开播时间 + 15/20/30 分钟` 等待并采集。接口没有历史分钟参数，所以应在开播前启动；如果启动晚了，默认跳过已过时段，可加 `--collect-past` 立即补抓当前快照。

缓存文件：`references/live-stats-cache/YYYY-MM-DD.json`

### 开播前自动截监控看板

```bash
node scripts/schedule_monitor_dashboard_screenshots.js --raw input.txt --dry-run --pretty
node scripts/schedule_monitor_dashboard_screenshots.js --raw input.txt --pretty
```

脚本会在每个唯一的 `开播时间 + 15/20/30 分钟` 时间点直接打开 `https://grafana.codemao.cn/d/SpSQKcpMl13/ying-xiao-zhi-bo-overviews?orgId=1&refresh=30s`，并截图保存到：

`output/duty-docs/assets/YYYY-MM-DD/monitor-{section}-T{分钟}-{时间}.png`

每个时间点默认截三张：

- `overview`：顶部 Ingress / 微服务 / Pod 汇总区域
- `microservice-pod-curves`：微服务与 Pod 资源曲线图区域
- `database-overviews`：RDS / MongoDB / Redis Overviews 区域

如果多场直播开播时间相同，同一 milestone 只截一张图。截图默认会把 Grafana URL 改成绝对时间范围：`from=开播时间`、`to=开播时间+分钟数`，所以补截图加 `--collect-past` 时也会看历史窗口，而不是当前 `Last 30 minutes`。只有需要保留当前看板时间范围时才加 `--current-time-range`。

### 生成文档

```bash
node scripts/build_duty_document.js --raw input.txt --stats-cache-dir references/live-stats-cache
node scripts/publish_duty_document.js --raw input.txt --stats-cache-dir references/live-stats-cache
```

生成 Markdown 表格版：

```bash
node scripts/publish_duty_document.js --raw input.txt --stats-cache-dir references/live-stats-cache --format markdown --include-monitor-screenshots
```

资源截图会按 `15/20/30分钟资源整体使用情况` 分组，并在标题后直接写入图片。

发布到钉钉文档时，脚本会先把本地截图上传到同一钉钉目录，再把返回的钉钉文件链接写进 Markdown：

```bash
node scripts/publish_duty_document.js \
  --raw input.txt \
  --stats-cache-dir references/live-stats-cache \
  --format markdown \
  --include-monitor-screenshots \
  --dingtalk-doc \
  --skip-local-output \
  --pretty
```

`--fetch-missing` 会对缺失缓存立即调 API（得到的是当前实时值，仅适合补数，不适合代替定时采集）。

## 发布到钉钉目录

不带 `--skip-local-output` 时，`publish_duty_document.js` 会生成本地文件：

- `output/duty-docs/{标题}.txt` — 正文
- `output/duty-docs/{标题}.md` — `--format markdown` 时的表格正文
- `output/duty-docs/assets/YYYY-MM-DD/*.png` — 监控看板截图；发布钉钉文档时会自动上传并替换为钉钉文件链接
- `output/duty-docs/{标题}.meta.json` — 目录 node、标题、缓存路径

使用 **钉钉文档 MCP（mcpId=9629）** 自动创建，见 [dingtalk-doc-mcp.md](./dingtalk-doc-mcp.md)。未配置时仍可只生成本地 `output/duty-docs/*.txt` 或 `output/duty-docs/*.md`。
