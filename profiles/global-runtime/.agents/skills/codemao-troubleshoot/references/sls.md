# SLS 证据

SLS 用于运行时日志证据。脚本入口是 `scripts/alilog`。参数细节以对应子命令 `--help` 为准。

## 何时读取

用户提到日志、报错、traceId、requestId、container、服务运行异常、接口失败、SLS、logstore，或需要按时间范围确认运行时行为时读取。

## 先用这条

范围不清时先聚合，确认有没有异常、集中在哪个服务或接口：

```bash
scripts/alilog query --project kuebernetes-production --logstore production --query '_container_name_: service-name and error | SELECT count(*) AS cnt' --time last_15m
```

已经有明确服务、时间和关键词时，再拉样本正文：

```bash
scripts/alilog query --project kuebernetes-production --logstore production --query '* and _container_name_: service-name and content: keyword' --time last_15m
```

字段不确定时，用样本日志探索字段：

```bash
scripts/alilog fields --project kuebernetes-production --logstore production --query '*' --time last_15m
```

## 默认目标

业务服务 logstore：

| 环境 | Project | Logstore |
| --- | --- | --- |
| `prod` | `kuebernetes-production` | `production` |
| `test` | `k8s-dev` | `test` |
| `staging` | `k8s-dev` | `staging` |
| `press` | `k8s-log-c58aa52bd44eb43d19df7dfa554656c46` | `press` |

已知的 `prod` 基础设施 logstore：`nginx-ingress`、`nginx-ingress-user`、`tomcat-log`。

`test`、`staging`、`press` 的基础设施 logstore 暂未记录。用户明确提供 project/logstore 时，优先使用用户给出的目标。

## Gotchas

- `--query '*'` 必须加引号；SLS 查询语法不是自然语言。
- 业务日志通常用 `content` 搜索，用 `message` 展示；`message` 常常没有索引。
- SLS 查询不提供 raw。先缩小 `--time`、`--query`、字段或分页。
- 输出会脱敏手机号和密钥类字段；不要为了看原文绕过工具。
- `fields` 来自样本日志，`sampled_logs=0` 只代表当前查询没采到样本。
- 聚合结果用于判断范围和方向，不替代具体日志证据。
- TID 通常是正文文本，不是稳定字段名；先在 `content` 搜索，字段输出前先用 `fields` 确认真实字段。

## 查询策略

优先用索引字段缩小范围，再看正文。范围未知时先 `count`、`top`、`group by` 判断有没有问题、集中在哪些服务、接口、状态码或时间段，再拉具体日志正文。

常用模式：

- 全量低成本探测：`*`
- 服务过滤：`_container_name_: service-name`
- 关键词：`error`、`Exception`、`"用户未登录"`
- 组合：`_container_name_: service-name and (error or Exception)`
- 排除：`not health`、`not "/actuator/health"`
- 标识定位：`requestId: xxx`、`traceId: xxx`、`userId: 123`、`orderId: 123`
- 聚合：`status:500 | SELECT url, count(*) AS cnt GROUP BY url ORDER BY cnt DESC LIMIT 20`

查询条件不要堆太多。超过 3-5 个条件仍然没命中时，先用 `fields` 看字段，或要求用户补充 requestId、用户 id、订单 id、错误截图、服务名或更精确时间。

长 TID、trace id 或连续 hex 串不一定能用完整值直接命中，可尝试 `content:前缀*`，例如 `content:fc216*`；不要用前置通配 `*fc216*`。

## 输出和字段

默认输出是紧凑证据，不是完整日志导出。工具会控制字段、截断、脱敏和空白压缩。需要参数细节时看 `scripts/alilog query --help`。

达到单条限制时，按提示用 `--continue INDEX:OFFSET` 查看同一条日志正文后续片段。`INDEX` 是本次查询结果里的第几条日志，从 1 开始；`OFFSET` 是这条日志正文的字符偏移量。它不是下一页，也不是下一条日志。继续查看同一条长日志是合理的，但不要把连续翻正文当成扩大搜索范围的替代。

字段不确定时先 `fields`。`--select-fields` 适合临时对照字段；`--extra-fields` 只加已确认的短元数据字段，不要拿它默认拉长 `content`。

发现 logstore 时使用：

```bash
scripts/alilog logstores --project kuebernetes-production --keyword nginx --page 1 --page-size 18
```

## 认证

`scripts/alilog auth` 会打开 SLS 控制台，监听真实 SLS 页面请求，捕获查询需要的 cookie 和 CSRF，写入 `output/alilog-auth.json`。这个文件包含敏感认证材料，不要打印或粘贴。

auth 的 project/logstore 只是目标提示。目标不存在时，如果仍能捕获认证材料，也应视为登录成功；真实查询时再暴露目标不存在的问题。

自动填充账号、密码和 TOTP 的首次配置见 `references/first-use.md`。
