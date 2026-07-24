# AI Code Review 报告

## 报告信息

| 字段 | 内容 |
| --- | --- |
| 审查快照ID | 9efbe5e8-73da-4bf3-ab4a-d8e377d75e61 |
| 团队 | platform-informatization |
| 项目 | platform-informatization-manage-system |
| 目标类型 | mr |
| MR | https://gitlab.codemao.cn/backend/platform-informatization/internal-service/platform-informatization-manage-system/-/merge_requests/297 |
| 分支 | feature/log -> master |
| 版本 | 49cb3e4eed615270a7b5f633edbfc3be530ccae1..80589686698fe01aa44fab46adea0e77c21ce94d |
| 生成时间 | 2026-07-15T08:59:36.319124+00:00 |

## 风险摘要

- Issue 总数: 2
- P0: 0
- P1: 2
- P2: 0
- P3: 0

## 重点问题汇总表

| Issue | 优先级 | 问题描述 | 问题分类 | 审查状态 | 文件 | 详情跳转 |
| --- | --- | --- | --- | --- | --- | --- |
| Issue-1 | P1 | pid 单条件查询被误判为无查询条件 | correctness | open | platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/controller/admin/AccountOperateLogController.java:53 | [Issue-1](#issue-1) |
| Issue-2 | P1 | 日志查询优化 MR 混入独立的账号注销功能和 SNAPSHOT 依赖 | compatibility | open | platform-informatization-manage-system-service/pom.xml:137 | [Issue-2](#issue-2) |

## Issue 详情

<a id="issue-1"></a>

### Issue-1 P1 pid 单条件查询被误判为无查询条件

- finding_key: `821066dab3a5b225`
- rule_id: `QUERY-001`
- category: `correctness`
- location: `platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/controller/admin/AccountOperateLogController.java:53`
- status: `open`

**证据**

search() 会把 query.getPid() 作为查询参数传给 accountOperateLogClient.search（第 46 行），说明 pid 是有效筛选条件；但 checkQueryTime() 的 hasSearchCondition 只检查 userId 和 phoneNumber。请求仅携带 pid 且未携带完整时间范围时，会在第 55-56 行抛出 LOG_QUERY_TIME_REQUIRED。

**影响**

已有的按产品 pid 查询账号操作日志会从正常查询变成业务错误，属于接口行为回归；前端或调用方若以 pid 作为唯一条件，将无法使用该查询入口。

**建议**

把 StringUtils.isNotBlank(query.getPid()) 纳入 hasSearchCondition，并补充 pid-only、完全无条件、仅一个时间端点三条回归用例。

<a id="issue-2"></a>

### Issue-2 P1 日志查询优化 MR 混入独立的账号注销功能和 SNAPSHOT 依赖

- finding_key: `c3251466fe33a01b`
- rule_id: `SCOPE-001`
- category: `compatibility`
- location: `platform-informatization-manage-system-service/pom.xml:137`
- status: `open`

**证据**

MR 标题和描述只对应 TAPD 48699533 的日志查询优化，但实际提交还包含 cfcc8252（新增加快注销接口、撤销权限和 3 份注销需求文档）及 80589686（把 accounthub-client2 从 1.11.29-RELEASE 升到 1.11.41-SNAPSHOT）。这些改动共增加 383 行，并引入新的 PUT /accounts/close/{id}/accelerate 行为。

**影响**

合并本 MR 会同时发布未经本 MR 需求和验收范围覆盖的账号注销能力、改变撤销接口权限，并依赖可变 SNAPSHOT；审查、回滚和发布无法再以“日志查询优化”为独立单元，存在功能误发布和依赖不可复现风险。

**建议**

将 feature/log 重新基于 master 整理，只保留 0757c6a4 对应的日志查询改动；cfcc8252 和 80589686 放到独立的账号注销 MR，并在其中使用已发布的 RELEASE client 版本或明确配套发布顺序。

## 剩余盲点

- 数据库MCP状态: 离线，仅完成静态分析。
- 目标模块编译在本机 Java 21 环境下因旧版 Lombok 与 JDK 模块访问不兼容而失败，未进入 admin-service 编译；该失败不是本次 diff 引入。
- 未执行真实 account_hub 联调，也未验证权限后台是否已配置 all-user:cancel:accelerate。
