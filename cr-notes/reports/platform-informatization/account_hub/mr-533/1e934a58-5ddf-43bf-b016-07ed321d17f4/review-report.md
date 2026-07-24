# AI Code Review 报告

## 报告信息

| 字段 | 内容 |
| --- | --- |
| 审查快照ID | 1e934a58-5ddf-43bf-b016-07ed321d17f4 |
| 团队 | platform-informatization |
| 项目 | account_hub |
| 目标类型 | mr |
| MR | https://gitlab.codemao.cn/backend/platform-informatization/account/account_hub/-/merge_requests/533 |
| 分支 | feature/trace-0625 -> master |
| 版本 | 5b50de908d7e7639d0c756dd9bfb3d9b11f42dd8..2b1104c4cf940a2c254ef16392041014f8e5eda9 |
| 生成时间 | 2026-07-15T08:44:16.551959+00:00 |

## 风险摘要

- Issue 总数: 3
- P0: 0
- P1: 2
- P2: 1
- P3: 0

## 重点问题汇总表

| Issue | 优先级 | 问题描述 | 问题分类 | 审查状态 | 文件 | 详情跳转 |
| --- | --- | --- | --- | --- | --- | --- |
| Issue-1 | P1 | RPC 入参可覆盖服务端采集的审计来源 | audit-integrity | open | accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/controller/rpc/AccountOperateLogController.java:92 | [Issue-1](#issue-1) |
| Issue-2 | P1 | 新增 serviceName/tid 查询未提供匹配索引与上线验证 | mongodb-performance | open | accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/mongo/dao/MongoVehicleUploadLogService.java:69 | [Issue-2](#issue-2) |
| Issue-3 | P2 | Feign 客户端直接修改 search 方法描述符会破坏升级兼容 | api-compatibility | open | accounthub-client/src/main/java/cn/codemao/service/platform/accounthub/hub/client/client/AccountOperateLogClient.java:34 | [Issue-3](#issue-3) |

## Issue 详情

<a id="issue-1"></a>

### Issue-1 P1 RPC 入参可覆盖服务端采集的审计来源

- finding_key: `870c86acc7b0a74c`
- rule_id: `SEC-001`
- category: `audit-integrity`
- location: `accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/controller/rpc/AccountOperateLogController.java:92`
- status: `open`

**证据**

POST /operate-log/save 和 /batch 直接对调用方提交的 AccountOperateLogRequest 执行 enrich；enrich 仅在 serviceName、tid、requestPath、requestMethod 为空时才读取 FeignCallerHelper、TraceContext 和 HttpServletRequest。因此调用方只要在请求体预填这些字段，后续会原样落入 accounts_operate_log。

**影响**

本次新增字段被定位为误覆盖排查所依赖的审计证据，但任一有权调用日志接口的服务都能伪造来源、trace 和请求路径，日志不能可靠回答真正的发起方与调用链，甚至会把排查引向错误服务。

**建议**

在 HTTP/RPC 边界忽略并覆盖请求体中的审计上下文字段，始终以服务端解析结果为准；异步内部调用需要保留上游上下文时，使用与外部请求 DTO 分离的可信内部对象，或在进入异步前采集后直接调用内部 service，避免把可写审计字段暴露给远端请求。

<a id="issue-2"></a>

### Issue-2 P1 新增 serviceName/tid 查询未提供匹配索引与上线验证

- finding_key: `464c2e68bb38373d`
- rule_id: `PERF-001`
- category: `mongodb-performance`
- location: `accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/mongo/dao/MongoVehicleUploadLogService.java:69`
- status: `open`

**证据**

MR 新增 serviceName、tid 等值条件，但随后仍会先 template.count，再按 createdAt DESC、_id ASC 分页查询；仓库和本次 diff 中没有 accounts_operate_log 的索引迁移或索引校验。本集合此前已出现约 3.88 亿文档的 COLLSCAN + SORT 慢查询；当前数据库 MCP 离线，无法确认线上已存在新字段索引。

**影响**

按 serviceName 查询通常会命中大量记录；若没有覆盖过滤和排序的复合索引，count 与分页查询都会扫描/排序大集合，新提供的排查接口本身可能再次触发分钟级慢查询并放大 Mongo 压力。

**建议**

合并或开放筛选前先在目标环境用 getIndexes 与 explain("executionStats") 验证 winningPlan。至少按实际查询形状评估并建立 serviceName + createdAt + _id、tid + createdAt + _id 的索引（字段方向与排序一致），同时为 limit 设置上限并记录索引发布、回滚和验收结果。

<a id="issue-3"></a>

### Issue-3 P2 Feign 客户端直接修改 search 方法描述符会破坏升级兼容

- finding_key: `0ee2f35e65f1d701`
- rule_id: `COMPAT-001`
- category: `api-compatibility`
- location: `accounthub-client/src/main/java/cn/codemao/service/platform/accounthub/hub/client/client/AccountOperateLogClient.java:34`
- status: `open`

**证据**

公开 client 模块把 search(userId, phoneNumber, startTime, endTime, pid, page, limit) 直接改为增加 serviceName、tid 的 9 参数方法；accounthub-client2 做了相同变更，旧 7 参数签名没有保留。AccountOperateLogQuery 和 AccountOperateLogResponse 的原有全参构造器也被替换。

**影响**

下游一旦升级 client/client2 依赖，现有源码调用会编译失败；若存在基于旧方法描述符的运行时动态调用，也可能产生 NoSuchMethodError。服务端 HTTP 接口虽然兼容可选参数，但 SDK 发布并不向后兼容。

**建议**

保留旧 search 签名并新增命名不同的扩展查询方法，或提供明确的兼容重载/查询对象入口；同时保留 DTO 原构造器并委托到新构造器。两个 client 模块应同步执行兼容性检查。

## 剩余盲点

- 数据库MCP状态: 离线（脚本未集成数据库 MCP，仅提供静态上下文）。
- 命中空值风险专项规则，review 时应额外读取 references/nullability-gotchas.md。
