---
name: crp-deploy
description: Use for CRP build, test submission, release, deploy, especially one-command test deployment.
---

# CRP Deploy

这个 skill 覆盖 CRP 上常见的构建、提测、部署操作。

命令都在本 skill 主目录执行。
执行构建、提测、部署相关命令时，运行环境必须能访问 CRP/CMDB 网络接口；如果默认执行环境无法访问这些接口，应直接使用具备网络访问能力的执行方式。

## 使用场景

- 用户目标明确是“把需求里的模块发到 `test`”时，直接用 `workflow-deploy-test`一键部署
- 用户要做的不是一键部署，而是查询、构建、提测、部署时，查看 [references/atomic.md](references/atomic.md)
- 遇到鉴权、cookie、token 失效时，查看 [references/auth.md](references/auth.md)，完成鉴权后重新执行原指令

## `workflow-deploy-test`一键部署

用户目标是把需求里的模块部署到 `test` 时，直接执行 `workflow-deploy-test`。命令会根据需求名和模块名片段自动匹配完整名称。

```bash
scripts/crp-deploy workflow-deploy-test \
  --requirement-name "<需求名>" \
  --module-name <模块名>
```

多模块时重复传 `--module-name`。

### 参数解析与重试

- `--requirement-name` 在当前可选需求里做字符串包含匹配，唯一命中才继续
- `--module-name` 支持完整模块名、业务名或唯一片段，例如 `namespace/example-service-name`、`example-service-name`、`example-service`
- 搜索不到或候选不唯一时，命令会失败并打印精简 JSON 候选。需求看 `requirement_candidates`；模块看 `resolved_modules` 和 `module_candidates`。能唯一判断就用更准确的参数重试；不能判断就向用户要更准确名称，或让用户从候选里复制。
- 当前需求下已有测试单时，workflow 会复用最新一张；完全没有测试单时才会新建提测单。若新建时项目下有多个 QA，按提示从可选 QA 名单里选一个 `user_id`，补上 `--qa-assignee <QA user_id>` 重试。

除非用户明确要求，否则不要加 `--dry-run` 或 `--wait`。

已知需要新建提测单且已经知道测试人时，可以直接传：

```bash
scripts/crp-deploy workflow-deploy-test \
  --requirement-name "<需求名>" \
  --module-name <模块名> \
  --qa-assignee <QA user_id>
```

### 异步反馈与进度查询

常用日志命令：

```bash
scripts/crp-deploy list-workflow-logs --limit 10
scripts/crp-deploy show-workflow-log --run-id <run_id>
```

`workflow-deploy-test` 启动时会自动静默清理旧 workflow logs。需要手动清理时，先用 `scripts/crp-deploy cleanup-workflow-logs --dry-run` 预览，确认后去掉 `--dry-run`；清理只影响 `output/workflow-logs` 下的一键部署日志、state 和 lock，不删除鉴权文件或 metrics。

- 默认异步执行：命令完成鉴权、参数解析、active preflight 及测试单处理并触发 build 后，看到 stdout 出现 `stage=build` 和 `eta` 就返回；后台会继续构建、创建 release、更新镜像并部署
- 异步模式下，看到 `stage=build` 后不要继续观察终端，不要马上查日志；只总结当前状态、`run_id` 和预计等待时间，不逐字复述 stdout。最终回复必须告诉用户：需要查看进度时，可以按 `run_id` 查询一次；下次也可以直接说同步部署，我会等到最终结果后再回复
- 部署未启动时，说明阻断原因，并告知修正后默认仍异步执行；最终回复必须告诉用户：如需等待最终结果，下次可以直接说同步部署
- 异步进度查询时，按 build `eta` 等待后只查一次 `show-workflow-log --run-id <run_id>`；如果仍是 `running`，根据返回的 `eta` 再等，不连续查询（最多重试 2 次，随后告知用户稍后再查）
- 同步模式仅在用户明确要求“同步部署”或等待最终结果时使用 `--wait`；同步模式有内置 build/release 超时，必须等待命令结束后一次性读取最终 stdout，禁止轮询 stdout、并行查日志或后台轮询，避免额外 token 消耗；仅当失败、超时或用户要求细节时，才查一次 `show-workflow-log` 兜底
- `show-workflow-log` 默认输出紧凑状态摘要；排查细节时才用 `--tail`，明确需要完整事件时才用 `--raw`

### 非参数阻断

- 提示已有 active build / active release：这是平台状态阻断，不是参数问题。等待现有构建或发布结束后再重试。
- build failed / build timeout：通常是构建或代码问题，或者 CRP 构建耗时过长。先用 `scripts/crp-deploy list-builds --requirement-id <需求ID> --page 1 --pagesize 20` 看最新状态。
- release failed / release timeout：通常是发布前置条件缺失或平台状态问题，例如未关联迭代、发布校验失败、发布耗时过长。先用 `scripts/crp-deploy get-release --release-id <release_id>` 查看失败原因。
- 鉴权失效：按 [references/auth.md](references/auth.md) 重新鉴权后，再重跑原命令。
