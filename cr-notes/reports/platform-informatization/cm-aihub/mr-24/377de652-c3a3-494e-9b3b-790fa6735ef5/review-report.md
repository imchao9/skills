# AI Code Review 报告

## 报告信息

| 字段 | 内容 |
| --- | --- |
| 审查快照ID | 377de652-c3a3-494e-9b3b-790fa6735ef5 |
| 团队 | platform-informatization |
| 项目 | cm-aihub |
| 目标类型 | mr |
| MR | https://gitlab.codemao.cn/backend/platform-informatization/tool/cm-aihub/-/merge_requests/24 |
| 分支 | feature/2608/data_safety -> main |
| 版本 | 0cbe01e2134e661cb26da1164bd4671c861ba05a..99100446a3f7e990edfac572fb5b8a90d5760dfa |
| 生成时间 | 2026-08-20T03:04:26.642051+00:00 |

## 风险摘要

- Issue 总数: 4
- P0: 0
- P1: 3
- P2: 1
- P3: 0

## 重点问题汇总表

| Issue | 优先级 | 问题描述 | 问题分类 | 审查状态 | 文件 | 详情跳转 |
| --- | --- | --- | --- | --- | --- | --- |
| Issue-1 | P1 | 新增审计字段和事件表未同步 SQLite schema | database | open | src/db/legacy-sqlite-schema.ts:110 | [Issue-1](#issue-1) |
| Issue-2 | P1 | 审计日志无条件信任客户端可控的代理头 | security | open | src/server.ts:763 | [Issue-2](#issue-2) |
| Issue-3 | P1 | 申请接口新增必填字段后既有调用契约直接回归为 400 | compatibility | open | src/server.ts:3012 | [Issue-3](#issue-3) |
| Issue-4 | P2 | 提交申请后的响应会清空刚查询到的数据安全等级 | correctness | open | src/server.ts:3120 | [Issue-4](#issue-4) |

## Issue 详情

<a id="issue-1"></a>

### Issue-1 P1 新增审计字段和事件表未同步 SQLite schema

- finding_key: `030d9a0e10839f2d`
- rule_id: `DB-SCHEMA-001`
- category: `database`
- location: `src/db/legacy-sqlite-schema.ts:110`
- status: `open`

**证据**

MR 仅在 MySQL schema/migration 中新增 query_audit_events.client_ip 和 mcp_event_logs；SQLite 的 legacy schema 以及 bootstrap create/ensureColumn 均未增加它们。业务代码却统一使用 MySQL schema 对 queryAuditEvents.clientIp 做 SELECT/INSERT，并向 mcpEventLogs INSERT。聚焦执行 npm test -- tests/local-alpha.test.ts tests/mcp-statistics.test.ts 时，统计接口返回 500，另一统计用例直接报 SQLITE_ERROR。

**影响**

仓库明确支持的本地/测试 SQLite 路径无法读取审计事件，也无法可靠记录 Key 生成事件；管理端 MCP 统计接口发生 500，现有测试套件无法通过。

**建议**

在 legacy-sqlite-schema.ts 和 SQLite bootstrap 中同步 client_ip 与 mcp_event_logs（包含必要索引和升级 ensureColumn），并让 SQLite schema 类型与运行时表定义一致；修复后复跑两组聚焦测试。

<a id="issue-2"></a>

### Issue-2 P1 审计日志无条件信任客户端可控的代理头

- finding_key: `7a0f2a3902704a23`
- rule_id: `SEC-AUDIT-001`
- category: `security`
- location: `src/server.ts:763`
- status: `open`

**证据**

resolveClientIp 优先采用请求中的 x-forwarded-for / x-real-ip，只校验字符串是否为合法 IP；Fastify 初始化未配置 trustProxy，也未验证请求确实来自可信反向代理。外部客户端可直接发送 X-Forwarded-For: 203.0.113.10，并使 Key 生成和 MCP 调用审计记录该伪造地址。

**影响**

新增的客户端 IP 审计字段不具备来源可信度，安全事件追踪、责任归属与合规取证都可能被调用方主动污染。

**建议**

通过 Fastify trustProxy 配置明确可信代理网段并统一读取 request.ip；未命中可信代理时只使用 socket.remoteAddress。不要在业务 helper 中直接信任任意代理头。

<a id="issue-3"></a>

### Issue-3 P1 申请接口新增必填字段后既有调用契约直接回归为 400

- finding_key: `cda0e78174f20f0c`
- rule_id: `COMPAT-API-001`
- category: `compatibility`
- location: `src/server.ts:3012`
- status: `open`

**证据**

单个和批量申请接口把 applyReason、durationMonths 从不存在直接改为必填，并在身份、能力及 Superset 状态判断前返回 400。仓库既有调用用例仍发送 {}、{authType} 或 {capabilityIds, authType}；聚焦测试中 4 个原本期望 200/404 的申请用例全部先收到 400。

**影响**

当前 MR 的测试套件为红；滚动发布期间已打开的旧页面或其他既有调用方也会在后端升级后立即无法申请，并且 dataset_not_found 等原有错误语义被参数校验遮蔽。

**建议**

明确并落实接口升级策略：至少同步所有仓库内调用和测试，覆盖新字段向 Superset 的透传；若需兼容已发布客户端，采用版本化端点或可观测的过渡期，而不是无版本地把原字段改为必填。

<a id="issue-4"></a>

### Issue-4 P2 提交申请后的响应会清空刚查询到的数据安全等级

- finding_key: `106156edc37f9314`
- rule_id: `STATE-MERGE-001`
- category: `correctness`
- location: `src/server.ts:3120`
- status: `open`

**证据**

申请前 capability 已由实时权限查询合并 dataSecurityLevelCode/Name；申请成功后，单个和批量路径再次调用 withPermissionStatus，但构造的 permission 只包含 status/updatedAt/reason/hasRowAuth。withPermissionStatus 在字段缺失时会无条件把 dataSecurityLevelCode/Name 写成 undefined，因此成功响应丢失安全等级。

**影响**

用户提交申请后，前端用响应替换当前 capability 时，详情页/卡片上的数据安全等级徽标会立即消失，直到下一次完整权限查询刷新。

**建议**

申请结果合并时保留 capability 上已由实时查询得到的安全等级，或让申请响应携带并透传这两个字段；将“完整权限快照覆盖”和“局部状态更新”拆成不同 merge 语义。

## 剩余盲点

- 数据库MCP状态: 离线（脚本未集成数据库 MCP，仅提供静态上下文）。
