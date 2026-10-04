# SLS 证据

SLS 用于运行时日志证据。脚本入口是 `scripts/alilog`。参数细节以对应子命令 `--help` 为准。

## 何时读取

用户提到日志、报错、traceId、requestId、container、服务运行异常、接口失败、SLS、logstore，或需要按时间范围确认运行时行为时读取。

## 默认目标

业务服务 logstore：

| 环境 | Project | Logstore |
| --- | --- | --- |
| `prod` | `kuebernetes-production` | `production` |
| `test` | `k8s-dev` | `test` |
| `staging` | `k8s-dev` | `staging` |
| `press` | `k8s-log-c58aa52bd44eb43d19df7dfa554656c46` | `press` |

已知的 `prod` 基础设施 logstore：`nginx-ingress`、`nginx-ingress-user`、`tomcat-log`。

`test`、`staging`、`press` 的基础设施 logstore 暂未记录。用户明确提供 project/logstore 时，优先使用用户给出的目标。目标不明确时先发现 logstore：

```bash
scripts/alilog logstores --project kuebernetes-production --keyword nginx --page 1 --page-size 18
```

## 排查流程与查询策略

1. 确认 Project、Logstore 和查询时间，执行 `index-fields` 读取当前索引配置。
2. 范围不清时先聚合，确认是否异常以及集中在哪个服务、接口、状态码或时间段。
3. 再缩小时间和查询条件，拉取样本正文。
4. 字段不确定时执行 `fields`，用实际样本确认字段后再调整查询和输出。

范围不清时先用：

```bash
scripts/alilog query --project kuebernetes-production --logstore production --query '_container_name_: service-name and error | SELECT count(*) AS cnt' --time last_15m
```

已经有明确服务、时间和关键词时：

```bash
scripts/alilog query --project kuebernetes-production --logstore production --query '* and _container_name_: service-name and content: keyword' --time last_15m
```

字段不确定时：

```bash
scripts/alilog fields --project kuebernetes-production --logstore production --query '*' --time last_15m
```

读取当前索引配置时：

```bash
scripts/alilog index-fields --project kuebernetes-production --logstore production
```

优先用已确认的索引字段缩小范围，再看正文。范围未知时先用 `count`、`top`、`group by` 判断分布，再拉具体日志。常用模式：

- 全量低成本探测：`*`
- 服务过滤：`_container_name_: service-name`
- 关键词：`error`、`Exception`、`"用户未登录"`
- 组合：`_container_name_: service-name and (error or Exception)`
- 排除：`not health`、`not "/actuator/health"`
- 标识定位：`requestId: xxx`、`traceId: xxx`、`userId: 123`、`orderId: 123`
- 聚合：`status:500 | SELECT url, count(*) AS cnt GROUP BY url ORDER BY cnt DESC LIMIT 20`

### Gotchas

- `--query '*'` 必须加引号；SLS 查询语法不是自然语言。
- 业务日志通常用 `content` 搜索，用 `message` 展示；`message` 常常没有索引。
- TID 通常是正文文本，不是稳定字段名；先在 `content` 搜索，字段输出前先用 `fields` 确认真实字段。
- 长 TID、trace id 或连续 hex 串不一定能用完整值命中，可根据分词配置尝试 `content:前缀*`，例如 `content:fc216*`；不要用前置通配 `*fc216*`。
- 条件超过 3–5 个仍无结果时，先放宽到一个已确认索引字段并缩小时间，或要求补充 requestId、用户 id、订单 id、错误截图、服务名或更精确时间。
- 仍无结果时，先按索引配置规则逐项核对，再判断日志是否不存在。
- 聚合结果用于判断范围和方向，不替代具体日志证据。
- SLS 查询不提供 raw。先缩小 `--time`、`--query`、字段或分页。

## `index-fields` 输出字段

`index-fields` 返回 Logstore 当前索引配置快照，其中的 `keys` 不是所有合法查询字段的全集；保留字段、`**tag**:*` Tag 字段、全文索引和扫描模式可能提供其他查询能力。

`fields` 表示某个查询、时间范围和样本日志中实际观察到的字段。结合两条命令判断：

| 结果 | 下一步 |
| --- | --- |
| 同时在 `fields` 和 `keys` | 样本中出现且当前有字段索引，可按索引类型生成查询 |
| 只在 `fields` | 样本中出现但没有普通字段索引，继续检查全文、保留字段或扫描模式 |
| 只在 `keys` | 当前有字段索引，但本次样本没有观察到 |

看到配置后按以下规则形成查询：

- 有 `line` 时，裸关键词范围由全文配置决定，先读 `include_keys` / `exclude_keys`。没有 `line` 不等于不能裸词查询；继续检查所有 `type=text`，裸词会搜索这些文本字段，而不是全部原始字段。
- `type=text` 使用文本和分词匹配；`type=long`、`type=double` 使用数值条件；`type=json` 继续读取 `json_keys`。
- `doc_value=true` 时可以优先考虑 SQL 提取、聚合、分组或排序，但它不是 SQL 可用的充分条件；`doc_value=false` 不代表没有字段索引，也不阻止 `field:value` 查询。
- 非空 `alias` 用于分析语句；字段查询仍使用 `keys` 中的原始字段名。
- `token`、`caseSensitive`、`chn` 决定关键词如何分词和匹配。空 `token` 仍有意义，通常需要完整值或合适的后缀通配。
- JSON 子字段递归读取 `json_keys`，查询时使用完整父路径，例如 `payload.token_de_base64`。依赖 `index_all` 时只考虑不超过 `max_depth` 的层级，`max_depth=-1` 表示不限深度；不要凭 `index_all` 虚构字段名或 JSON 数组路径。需要核实 JSON 索引边界时，再参见[阿里云 JSON 索引数据类型](https://help.aliyun.com/zh/sls/data-types)。
- `ttl` 只提示查询时间可能超出数据或索引保留范围，不是精确删除边界，也不能用 `lastModifyTime + ttl` 计算过期时间。
- 查询跨越 `lastModifyTime` 时，更早数据可能没有使用当前配置或没有重建索引。需要核实索引生效规则时，再参见[阿里云索引配置说明](https://help.aliyun.com/zh/sls/create-indexes)。
- 查询超长正文、请求体或异常栈时检查 `max_text_len`，超过部分可能没有参与索引。

## 输出和字段

默认输出是紧凑证据，不是完整日志导出。工具会控制字段、截断、脱敏和空白压缩；不要为了看原文绕过工具。

达到单条限制时，按提示用 `--continue INDEX:OFFSET` 查看同一条日志正文后续片段。`INDEX` 是本次结果中的日志序号，从 1 开始；`OFFSET` 是正文字符偏移量。它不是下一页，也不是下一条日志；连续翻正文不能代替扩大搜索范围。

`fields` 依赖当前查询、时间和样本，`sampled_logs=0` 只代表当前查询没采到样本。`--select-fields` 适合临时对照字段；`--extra-fields` 只加已确认的短元数据字段，不要拿它默认拉长 `content`。

输出会脱敏手机号和密钥类字段。

## 认证

运行 `scripts/alilog auth` 后，脚本会登录阿里云并监听真实 SLS 页面请求。捕获到查询所需的 cookie 和 CSRF 后，会写入 `output/alilog-auth.json`，并输出 `auth ready`。

`auth ready` 表示认证文件已经写完，可以立即执行 `query`、`fields`、`logstores` 或 `index-fields`。浏览器由独立 worker 在后台尽力关闭；关闭失败不改变认证结果。有头 Chrome 持续未关闭时，可以直接手动关闭。

`output/alilog-auth.json` 包含敏感认证材料，不要打印或粘贴。未指定 `--profile-dir` 时，`auth` 使用一次性临时浏览器 profile，不会主动清除浏览器 cookie。

### 自动登录与自动填充

账号、密码和受支持的 TOTP 都已配置时，`auth` 先尝试无头 auto-login。遇到验证码或无法识别的登录页错误时，会在同一个浏览器会话中重开登录页并重试一次，最终仍失败时打开 Chrome 做有头 auto-fill；其他可恢复失败也会降级到有头 auto-fill。明确检测到账号/密码或 TOTP 安全码错误时，不再用同一份凭据重试或自动填充，而是打开 Chrome 转为手动登录并显示处理提示。凭据不完整但至少有一个可填字段时进入有头 auto-fill；完全没有可填字段时进入有头手动登录。

有头 auto-fill 只补空的账号、密码和 TOTP，不覆盖用户输入或点击登录、验证按钮；不会将本地 TOTP 填入短信验证码。滑块和无法识别的登录页错误共用 2 次自动恢复机会，耗尽后转为手动登录；明确的账号/密码或 TOTP 安全码错误会立即停止自动填充。

`scripts/alilog auth --no-auto-fill` 从一开始走完全手动登录，只打开 Chrome，不读取本地账号、密码或 TOTP。认证未成功或需要定位失败原因时，运行 `scripts/alilog auth --debug`，观察自动填充、验证码恢复和认证材料捕获停在哪一步。

认证页面提示密码或安全码错误时，可以在当前窗口手动完成本次登录。若已更新 Keychain 中 `alilog` 的密码或 `alilog-totp` 的 TOTP seed，需要重新运行 `scripts/alilog auth`，让新进程读取更新后的凭据。
