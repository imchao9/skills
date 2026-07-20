# 服务 API 证据

`scripts/service-api` 用于线下配置证据、服务发现证据和服务请求证据。参数细节看具体 action 的三级 `--help`，例如 `scripts/service-api config get --help`、`scripts/service-api discover get --help`、`scripts/service-api auth custom --help`。

## 何时读取

用户提到 Apollo 配置、Eureka、服务名、app id、接口请求、admin/customer 登录、cookie、服务发现或线下服务调用时读取。

## 先用这条

服务名明确时先验证存在：

```bash
scripts/service-api discover exists --env test --service service-name
scripts/service-api discover get --env test --service service-name
```

配置怀疑时先查 key，再按关键词缩小：

```bash
scripts/service-api config get --env test --app app-name --namespace application --keys
scripts/service-api config get --env test --app app-name --namespace application --keyword datasource
```

已知安全查询接口时再请求：

```bash
scripts/service-api request --url https://example.codemao.cn/api/path --auth none
```

## Gotchas

- `prod` 禁止 Apollo/Eureka，生产服务请求也不是默认排障能力。
- Apollo app id 和 Eureka service 名不保证一致，可能只有 `-`/`_` 差异，也可能完全不同。
- Eureka 实例 IP 请求不等价于域名请求，鉴权可能发生在网关、mesh 或服务内部。
- `request` 默认 `--auth none`；admin/customer/custom cookie 只在需要时使用。
- 可能写入的请求必须先获得用户授权；HTTP method 本身不足以证明安全。

支持环境：`test`、`staging`、`press`。

配置默认在 `scripts/service-api.config.json`，也可以通过 `SERVICE_API_CONFIG_FILE` 或 `--config` 指定。运行态认证 cookie 默认写入 `output/service-api-auth.json`，也可以用 `SERVICE_API_AUTH_FILE` 指定。cookie 和密码不要进入报告。

默认输出应匹配命令的证据目的并保持紧凑，不重复命令参数或环境字段。只有紧凑输出隐藏了当前假设需要的字段时，才使用 `--raw`。

## Apollo 配置和 app

Apollo 是配置证据。`config get` 必须显式选择输出范围：`--keys`、`--key`、`--prefix`、`--keyword` 或 `--all`。默认不要直接拉全量配置。需要先探索时用 `--keys`，再配合管道搜索：

```bash
scripts/service-api config get --env test --app app-name --namespace application --keys | rg 'datasource|redis|mongo'
```

省略 namespace 时，工具会查询 `application` 和 `application-volatile`。只有明确需要完整配置时才使用 `--all`。

`config exists` 使用和 `config get` 相同的内部 Apollo 配置接口，默认检查 `application` namespace。

`config list` 使用 Apollo Portal 的 `/signin` 和 `/apps?appIds=` 流程。Portal 凭据可以使用 `scripts/skillctl credential seal` 生成的 sealed password。Portal cookie 只在当前命令内存中保存，不要在报告中打印 Portal cookie 或密码。

任一 namespace 查询失败时，命令非 0 退出，并在 stderr 输出紧凑错误，例如 `[apollo_config_failed] namespace=application status=404`。不要把半截配置当完整证据。

`config get` 会在输出前封装敏感密码字段。字段名命中 `password`、`passwd`、`pwd`、`pass` 时，值会转换为 `sealed:v1:...`；如果 URL/URI 中包含 `user:password@host`，password 也会封装并进行 URL encode。`apollo_hover_content` 会被忽略。这样 Apollo 查询结果可以直接作为 `offline-data-query --source` 参数来源，同时避免把明文密码直接暴露给模型上下文。

服务发现名和 Apollo app id 只是相关线索，不保证一致。能访问代码时，优先从代码证据确认，例如部署服务名、Apollo `app.id`、bootstrap 配置或启动参数。没有代码时，如果候选名明确，先用 `discover exists` 或 `config exists`；否则用 `discover list --keyword ...` 和 `config list --keyword ...` 对比候选。

## Eureka

Eureka 是服务发现证据。`discover list` 用于搜索候选服务，`discover exists` 用于低成本判断明确候选，`discover get` 用于解析实例地址。服务名按大小写不敏感处理。

默认输出是紧凑证据，不重复命令里的环境或服务名。需要实例 IP、端口列表或完整 Eureka payload 时再使用 `--raw`。

通过 Eureka 解析得到的是实例 IP，直接访问实例不保证和公网或内网域名路径等价。鉴权可能发生在请求到达服务之前，例如网关或 mesh，也可能发生在服务内部。因此鉴权接口优先使用明确域名 URL。

## 请求和鉴权

服务请求是行为证据。默认 `request` 输出只保留紧凑响应证据：`status_code` 和 `body`。只有调试请求构造、服务解析或响应 headers 时才用 `--raw`；raw 输出中的请求 cookie 会脱敏。

`request --env` 只在命令需要环境配置时有意义：`--service` 需要 Eureka 解析，`--auth admin/customer` 需要环境维度 cookie。显式 `--url --auth none/custom` 不需要 `--env`；custom cookie 按最终请求 URL 的 origin 查找。

当代码证据提供了服务名，而下一步需要发起请求时，推荐编排：

1. 用 `discover exists --env ENV --service SERVICE` 检查服务名，或用 `discover get` 查看地址。
2. 如果接口很可能无需鉴权，先通过 Eureka 解析调用：`request --env ENV --service SERVICE --path PATH --auth none`。
3. 如果响应显示需要鉴权，并且该接口合理属于 admin 或 customer 账号体系，再分别尝试 `--auth admin` 或 `--auth customer`。
4. 如果两种配置 cookie 都不适用，停止并要求用户用 `service-api auth custom --login-url URL --auth-check-url URL` 捕获 custom cookie，再用 `--auth custom` 重试。

不要让低层工具按服务名猜测 auth mode。auth 猜测属于 agent 排障编排层，必须作为假设明确说出。

支持的 auth mode 是 `none`、`admin`、`customer`、`custom`。`internal-auth`、`user-auth` 这类 token 风格模式不属于工具契约。

`auth` 会使用临时 profile 打开本机 Chrome，等待用户手工登录，并监听配置的 auth-check URL。只有该 auth-check URL 在浏览器中自然返回成功后，才把 cookie 写入 `output/service-api-auth.json`。工具不会主动调用 auth-check URL，也不会打印 cookie 值。

`admin` 和 `customer` auth 按环境区分，使用配置里的登录 URL 和 auth-check URL。`custom` auth 不按环境区分，必须提供 `--login-url` 和 `--auth-check-url`，然后把 cookie 存到 auth state 的 `customCookies[origin]`，其中 origin 来自 auth-check URL。

当 `request --auth custom` 找不到最终请求 origin 对应的 cookie 时，会报告 origin，并提示运行 `service-api auth custom --login-url <login-url> --auth-check-url <auth-check-url-for-origin>`。

优先发起查询类请求。如果请求可能创建、更新、删除、发消息、发券、触发任务、提交支付，或产生任何状态变化，必须说明目标、意图和风险，然后等待用户明确授权。
