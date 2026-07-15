# AI Code Review 报告

## 报告信息

| 字段 | 内容 |
| --- | --- |
| 审查快照ID | d4eb7f5b-7ad0-4a09-9ddd-511234d0bdea |
| 团队 | platform-informatization |
| 项目 | account_hub |
| 目标类型 | mr |
| MR | https://gitlab.codemao.cn/backend/platform-informatization/account/account_hub/-/merge_requests/534 |
| 分支 | feature/log -> master |
| 版本 | a71ba39ea81397608c2568b0fa28060626edf3a5..6558af30ae4c3132b9bbb7e12a6e4a33f80e8d15 |
| 生成时间 | 2026-07-15T09:22:46.452149+00:00 |

## 风险摘要

- Issue 总数: 3
- P0: 1
- P1: 2
- P2: 0
- P3: 0

## 重点问题汇总表

| Issue | 优先级 | 问题描述 | 问题分类 | 审查状态 | 文件 | 详情跳转 |
| --- | --- | --- | --- | --- | --- | --- |
| Issue-1 | P0 | 注销状态校验与删除未原子化，撤销后仍可能被注销 | concurrency-data-safety | open | accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:861 | [Issue-1](#issue-1) |
| Issue-2 | P1 | 复用 closeWork 缺少失败状态与幂等恢复 | data-consistency | open | accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:872 | [Issue-2](#issue-2) |
| Issue-3 | P1 | 管理日志失败被吞掉，注销仍返回成功 | audit-reliability | open | accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:885 | [Issue-3](#issue-3) |

## Issue 详情

<a id="issue-1"></a>

### Issue-1 P0 注销状态校验与删除未原子化，撤销后仍可能被注销

- finding_key: `01c7b8d4e74e3823`
- rule_id: `CONC-001`
- category: `concurrency-data-safety`
- location: `accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:861`
- status: `open`

**证据**

accelerateCloseAccount 先查询申请并确认 state=DEALING，随后才调用 closeWork；期间没有条件更新、行锁或分布式锁。方法上的 synchronized 只锁当前 JAccountFacadeImpl 实例，既不覆盖 revokeCloseAccountApply/revokeCloseAccountApplyByUser，也不跨服务实例。定时任务 closeAccountJob 同样会读取 DEALING 后直接调用 closeWork。

**影响**

如果用户撤销与后台加速请求并发，撤销线程可先把申请改为 REVOKE 并恢复账号，已通过旧状态校验的加速线程仍会解绑认证、清理 ES/OAuth、关闭账号并最终把申请覆盖成 CLOSE。多实例或定时任务并发还会重复执行注销、MQ 和日志副作用，属于真实的数据删除风险。

**建议**

在执行任何注销副作用前，用数据库条件更新原子抢占申请，例如 UPDATE ... SET state=PROCESSING WHERE id=? AND state=DEALING，并以 affectedRows=1 作为唯一执行资格；撤销也必须通过互斥的条件状态迁移。PROCESSING 状态下再执行幂等注销流程，并为失败状态和人工恢复提供明确路径。不要用 JVM synchronized 代替跨实例状态机。

<a id="issue-2"></a>

### Issue-2 P1 复用 closeWork 缺少失败状态与幂等恢复

- finding_key: `20c38b9a8853e4d5`
- rule_id: `CONSISTENCY-001`
- category: `data-consistency`
- location: `accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:872`
- status: `open`

**证据**

新 RPC 直接调用 closeWork。closeWork 会依次解绑手机号/邮箱/OAuth、关闭账号、撤销 token、发送 MQ、清理 ES，最后才 updateById 将申请改为 CLOSE；这些跨 MySQL、ES、RPC、MQ 的步骤没有统一事务、执行进度或幂等键，任一步抛异常都会让申请继续保持 DEALING。

**影响**

调用方收到失败后重试会再次执行已经成功的前半段；账号可能处于认证已解绑但状态未关闭、主库已关闭但 ES 未清理、MQ 重复发送等部分注销状态。定时任务之后还会继续重试这条 DEALING 申请，扩大不一致。

**建议**

先通过原子状态迁移记录 PROCESSING，再把各删除步骤设计为可重复执行，并记录步骤结果或使用可靠事件/outbox；失败时落明确 FAILED/RETRY 状态，由补偿任务继续，而不是重新从 DEALING 无条件执行整条流程。完成全部关键步骤后再条件更新为 CLOSE。

<a id="issue-3"></a>

### Issue-3 P1 管理日志失败被吞掉，注销仍返回成功

- finding_key: `6737b5794e56563b`
- rule_id: `AUDIT-001`
- category: `audit-reliability`
- location: `accounthub-service/src/main/java/cn/codemao/service/platform/accounthub/hub/facade/impl/JAccountFacadeImpl.java:885`
- status: `open`

**证据**

账号注销完成后才调用 recordAccelerateCloseAccountManagementLog；该方法捕获所有 Exception，只打印错误并继续返回 accelerated=true。管理日志保存没有重试、补偿或可靠事件。

**影响**

这是后台主动提前执行的不可逆账号注销。如果日志服务短暂故障，账号已经被删除但操作人、来源和状态变更记录永久缺失，无法满足 MR 描述中的管理操作留痕，也会破坏后续审计与责任追溯。

**建议**

将操作意图和操作者信息在原子抢占申请时持久化，或写入可重试的 outbox/审计任务；只有审计事件被可靠接收后才报告完整成功。至少不要静默吞掉失败，应落可检索的失败记录并触发补偿重试。

## 剩余盲点

- 数据库MCP状态: 离线（脚本未集成数据库 MCP，仅提供静态上下文）。
- 命中空值风险专项规则，review 时应额外读取 references/nullability-gotchas.md。
