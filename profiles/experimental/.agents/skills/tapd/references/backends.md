# TAPD 执行后端

选择或配置 TAPD 执行方式时读取本说明。

## 选择方式

| 执行方式 | 优先使用场景 | 优点 | 主要风险 |
|---|---|---|---|
| `tapd-ai-cli` | 有终端且已安装 `tapd` | 输出紧凑、可查现场 `--help`、支持 URL 和筛选、读写能力完整 | 包含外部写操作，且可能持久化凭证 |
| TAPD MCP | 已连接 TAPD MCP 且能看到现场 Schema | 直接使用类型化工具，支持 stdio 或 Streamable HTTP | 写能力广，通用 `options` 参数需要检查 Schema |
| 直接调用 OpenAPI | 已有经过审计的窄范围脚本 | 容易强制端点白名单并生成确定性报告 | 容易重复实现认证、分页和响应处理 |

通用 Agent 操作优先使用 CLI。只有需要确定性输出或强制只读白名单时，才优先使用现有窄范围
OpenAPI 脚本。不要把通用 CLI 或 MCP 实现复制进本 skill。

## tapd-ai-cli

来源：<https://github.com/studyzy/tapd-ai-cli>

初始审计基线：2026-07-27 的提交
`20a8c929bc128aedf4a9757bd57f723e515a65dd`。依赖参数前重新检查现场命令树。

只有获得用户授权后才安装：

```bash
go install github.com/studyzy/tapd-ai-cli/cmd/tapd@latest
```

CLI 支持个人访问令牌和 API 用户名/密码。优先使用通过 `TAPD_ACCESS_TOKEN` 提供的个人令牌；
它是 Bearer 凭证，不是 AK/SK。配置优先级如下：

1. CLI 参数。密钥不要走此方式，避免被进程信息或命令日志暴露。
2. `TAPD_ACCESS_TOKEN`，或 `TAPD_API_USER` 加 `TAPD_API_PASSWORD`。
3. `./.tapd.json`。
4. `~/.tapd.json`。

可选端点覆盖：

- `TAPD_API_BASE_URL`，默认 `https://api.tapd.cn`。
- `TAPD_BASE_URL`，默认 `https://www.tapd.cn`。

使用 `tapd --help` 和 `tapd <group> <action> --help` 作为当前命令契约。仓库也提供
`tapd skill init`，但不要在此 profile 中执行；当前目录已经是经过审查的规范版本。

已审计版本存在一个已知限制：需求、任务、缺陷和迭代列表通过独立 count 请求获取 `total`，
而该请求只携带工作区和状态。其他列表筛选条件不会传给 count 请求，因此返回的 `items`
可能正确，但 `total` 和 `has_more` 与筛选结果无关。应统计每页实际条数，并在出现不足一页时
停止；不要把包装响应中的过滤总数当成事实。

安全注入和最小范围验证见[认证说明](authentication.md)。不要把真实令牌写进会提交到仓库的
MCP JSON 配置。

## 腾讯 TAPD MCP

SkillHub 页面：<https://skillhub.cloud.tencent.com/mcp/mcp-server-tapd>

源码：<https://cnb.cool/tapd_mcp/mcp-server-tapd>

初始审计基线：2026-07-27 的提交
`2b607cceaf4d5b1854967371b5c5a2e6d5dec697`。调用前重新检查现场 MCP Schema。

发布的 stdio 配置通过 `uvx mcp-server-tapd` 运行，支持：

- `TAPD_ACCESS_TOKEN`，优先。
- `TAPD_API_USER` 加 `TAPD_API_PASSWORD`。
- `TAPD_API_BASE_URL`。
- `TAPD_BASE_URL`。
- 可选的企微机器人 `BOT_URL`。

服务也可以通过 Streamable HTTP 运行。不要把它监听到 `0.0.0.0`、暴露到网络，
也不要仅为查询 TAPD 而注入机器人 Webhook。本地 Agent 优先使用 stdio 或仅监听回环地址。

在创建本 skill 时审计的版本中，MCP 同时包含需求/任务、缺陷、评论、流程、迭代、关联、
测试用例、Wiki、工时、发布计划、工作区成员和企微消息的读写工具。由于该能力面可能变化，
始终以现场工具 Schema 为准。

## 现有窄范围汇报流程

本地 `tapd_task_cost` 项目展示了适合只读状态报告的替代方案：

- 业务请求限制在明确的 GET 端点白名单内；
- 只有获取令牌允许使用 POST；
- 分别读取需求、缺陷和任务数量；
- 对迭代完成分页；
- 输出记录工作区、生成时间、数量和迭代筛选条件。

生成报告时复用这些保护规则。不要复制其中的凭证，也不要假设它的四个端点足以覆盖通用 TAPD 操作。
