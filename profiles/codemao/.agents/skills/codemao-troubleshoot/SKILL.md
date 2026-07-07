---
name: codemao-troubleshoot
description: Use when investigating Codemao runtime problems in production, test, staging, or press environments, including incidents, bugs, request failures, data anomalies, configuration doubts, and environment-specific behavior. First identify the environment and evidence needed before choosing any internal tool.
---

# Codemao Troubleshooting

这是点猫运行时排障辅助 skill。主文档只负责排障编排、边界和工具路由；具体命令、字段和失败解释按需读取 `references/`。

## 排障循环

1. 先明确边界：环境、服务或系统、时间范围、定位标识、异常现象、期望行为。
2. 选择最窄的证据入口：日志、配置、服务发现、服务请求、只读数据或代码。
3. 把假设写成可证伪的表述，再用工具和代码路径验证。
4. 区分事实、推断和缺口；证据冲突时停止推进，报告冲突并要求用户确认事实源。
5. 当继续排查的 token、时间或交互成本明显高于问题复杂度时，先汇报取舍，让用户决策。

缺少关键因素时，优先引导用户补充环境、服务名、时间范围、请求标识、业务 id、错误截图、代码仓库或执行入口。只有假设安全且成本低时才继续探索。

## 基础守卫

- 安全性和成本控制优先于“多查一点”。
- 只读动作通常可直接执行；可能改变状态的服务请求、收藏增删、浏览器登录、分支切换等动作要看风险和上下文。
- 创建、更新、删除、发消息、发券、触发任务、提交支付、发起审批、修复数据或启动后台任务，不能静默执行。必须说明目标、意图、风险和替代只读证据，等待用户明确授权。
- 认证材料、cookie、CSRF、TOTP seed、明文密码不进入报告。只能报告认证文件是否存在、是否刷新、cookie 名称或脱敏状态。
- SLS 日志和 dbops 输出默认脱敏手机号与密钥类字段；不要绕过工具读取原文。
- 执行工具命令时正常等待进程结束后再读取输出；不要频繁 poll、重复复述 stdout，或因为暂时没有新输出就重复执行同一命令。
- 默认使用紧凑输出。只有当前假设需要上游隐藏字段时，才使用大 page size、全量字段或更多翻页。
- 不把个人文件系统路径、运行态 cookie、storage state 或临时 inspection 文件写进可分发内容。

## 环境边界

| 环境 | 含义 | 证据方向 |
| --- | --- | --- |
| `prod` | 线上环境 | 线上日志、线上只读数据、`master` 代码 |
| `test` | 测试环境 | 线下运行时证据、配置/发现证据、`test` 代码 |
| `staging` | staging 环境 | 线下运行时证据、配置/发现证据、`master` 代码 |
| `press` | 压测环境 | 压测运行时证据、配置/发现证据、用户确认的代码分支；缺失时可暂按 `test`，但必须标注不确定性 |

`dev` 不是维护中的排障环境。`prod` 禁止 Apollo/Eureka；即便入口看似可访问，也不安全且通常没有权限。

本地代码分支不匹配时，应强烈建议切换分支并等待授权。用户不切换时，只能弱化代码证据，不能在错误分支上给强结论。

## 首步决策

| 用户提供 | 首选动作 |
| --- | --- |
| 环境 + 时间 + 服务 | 读 `references/sls.md`，先用窄时间窗日志或聚合确认范围 |
| traceId、requestId、错误关键词 | 读 `references/sls.md`，优先用索引字段和 `content` 搜索 |
| 用户、订单、活动或记录 id | 读 `references/database.md`，结合代码条件和日志事件 |
| app 或 service 名 | 读 `references/service-api.md`，先 `exists/get`，再按需请求 |
| 配置怀疑 | 读 `references/service-api.md`，先 `config get --keys` 或 `--keyword` |
| 只有现象 | 先索要环境、时间、服务、id、截图或代码入口；必要时只做低成本 list/exists |
| 线上问题 | SLS + dbops + `master` 代码；禁止 Apollo/Eureka |

## Reference 路由

| 问题类型 | 读取 |
| --- | --- |
| 日志、报错、traceId、container、logstore | `references/sls.md` |
| MySQL、Redis、Mongo、线上 dbops、数据状态 | `references/database.md` |
| Apollo 配置、Eureka 服务发现、服务请求、登录 cookie | `references/service-api.md` |
| 代码入口、调用链、配置读取、分支匹配 | `references/code-evidence.md` |
| 首次使用、新机器、依赖安装、alilog 自动填充 | `references/first-use.md` |

不要默认读取所有 reference。先根据问题类型选择一个入口，工具输出或证据缺口指向其他方向时再加载下一份。

## 全局坑点

- `prod` 禁止 Apollo/Eureka；即便入口看似可访问，也不安全且通常没有权限。
- 缺少环境、时间、服务、定位 id 或代码入口时，先补关键因素；不要用大范围查询代替澄清。
- 可能写入的 service request 必须先获得用户授权；HTTP method 本身不足以证明安全。
- 本地分支不匹配时，代码证据降级；不能在错误分支上给强结论。
- 信息前后冲突时停止推进，报告冲突并要求用户确认事实源。

## 脚本即 API

需要执行动作时优先使用 `scripts/` 中的对应命令；参数以 `--help` 为准。文档只说明何时用、先用哪条、常见失败怎么解释，以及何时升级到更多字段。

## 首次使用

正常排障不主动重复跑 setup。只有用户说明首次使用、新机器、刚分发或刚更新 skill，或工具报依赖缺失时，才提示或执行 `scripts/skillctl setup --install`。具体指引见 `references/first-use.md`。

## 汇报格式

正式排障结论分开写：

1. 已观察事实。
2. 推断或假设。
3. 置信度。
4. 证据缺口。
5. 下一步验证或处理建议。

小型检查可以简化为结论、证据、缺口或下一步。
