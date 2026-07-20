# 数据证据

数据证据必须只读。不要执行写入、DDL、修复、审批、状态变更或任何可能改变数据的命令。参数细节以 `scripts/dbops-query --help` 和 `scripts/offline-data-query --help` 为准。

## 何时读取

用户提供用户 id、订单 id、活动 id、记录 id、缓存 key、数据库表、数据异常、线上 dbops 或线下 MySQL/Redis/Mongo 线索时读取。

## 先用这条

线上先走 dbops 只读：

```bash
scripts/dbops-query query-on "实例名" "库名" "SELECT COUNT(*) FROM tbl_xxx"
```

线下先走明确 profile 或显式 source：

```bash
scripts/offline-data-query --profile test-mysql "SELECT COUNT(*) FROM tbl_xxx"
scripts/offline-data-query --profile test-redis "TYPE cache_key"
scripts/offline-data-query --profile test-mongo '{"op":"listCollections","limit":5}'
```

## Gotchas

- 数据证据只能只读；写入、DDL、修复、审批和状态变更禁止。
- `prod` 数据证据只走 dbops。线下数据查询不能替代线上证据。
- `offline-data-query` 不接收环境参数，只接收 profile、source 和查询命令。
- 密码不能明文传给 query；必须使用 sealed 值，URL 里也不能带 `user:password@host`。
- dbops 输出会脱敏手机号和密钥类字段；不要为了看原文绕过工具。
- 单条数据状态通常只是线索，需要和日志、代码条件或配置组合后再下结论。
- `instances` 和 `resources` 查的是 dbops 元数据，可证明候选实例、库、表在平台侧存在；但不证明当前账号有数据查询权限，权限必须用最小只读 SQL 验证。
- 当前 dbops 查询路径没有 `information_schema` 权限，定位表不要走 `information_schema`。
- 数据位置不明时，禁止默认全量扫描所有可读实例、库和表。先用业务对象、页面/接口、服务名、日志/TID、代码或 SQL 片段、`querylog`、`favorites` 等线索缩小候选；确需全量元数据扫描时，先说明成本并等待确认。

## 线上：dbops-query

`prod` 数据证据使用 `scripts/dbops-query`。dbops 登录状态缺失或过期时，运行：

```bash
scripts/dbops-query auth
```

认证会写入 `output/dbops-auth-cookie.txt` 和 `output/dbops-auth-storage-state.json`。cookie 文件也可以手工更新：可以保留注释，但完整 Cookie header 必须放在最后一行非空、非注释内容。

非敏感默认配置放在 `scripts/dbops-query.config.json`。cookie 材料不能写进该配置。

只有在默认实例和数据库明确匹配目标时，才使用默认查询目标。否则应要求用户提供实例和数据库。

`instances`、`resources`、`querylog`、`favorites` 等探索命令用于确认目标实例、库、表、历史 SQL 或收藏入口；具体参数看 `scripts/dbops-query --help`。默认 SQL 入口、`query-on`、`favorite-run`、`favorite-query` 输出 TSV 查询结果。

需要完整 dbops 上游响应时，使用显式 `api GET|POST` 兜底。不要把 `api` 当默认排障入口；它适合验证尚未包装的平台接口或临时补足能力。

收藏和取消收藏是排查准备或知识沉淀动作。例如排查中发现某条 SQL 后续会经常复用，可以建议收藏；排查后总结发现某条收藏已无价值，也可以建议取消。

## 线下：offline-data-query

线下数据证据使用 `scripts/offline-data-query`。这个工具只关心数据源和查询命令，不接收 `test`、`staging`、`press` 这类排障环境参数。环境、Apollo 发现、用户提供的数据源信息，都应该在工具外层先整理成 profile，或作为 `--source` 临时数据源显式传入。

支持 `mysql`、`redis`、`mongo` 三类 profile。所有执行入口都必须保持只读：MySQL 只允许查询类 SQL 前缀，Redis 只允许只读命令白名单，Mongo 只允许有限的 JSON 只读操作。

profile 配置默认在 `scripts/offline-data-query.config.json`，也可以通过 `OFFLINE_DATA_QUERY_CONFIG_FILE` 指向其他文件。内部预定义数据源可以直接随 skill 分发；Apollo 发现或用户临时提供的数据源，也可以整理成同样的 profile 文件后使用。

临时发现的数据源优先使用 `--source`，避免为了单次排障重复写入 profile。常用、稳定、准备随 skill 分发的数据源再写入 profile。

`password` 必须是 sealed 值。明文密码会被拒绝。URL 中也禁止携带 `user:password@host`，应把 user 和 sealed password 拆成独立参数或 profile 字段。sealed 不是权限边界；它只用于避免明文密码直接进入模型上下文。

生成 sealed 密码：

```bash
printf '%s' 'password' | scripts/skillctl credential seal
```

校验 sealed 值但不打印明文：

```bash
printf '%s' 'sealed:v1:...' | scripts/skillctl credential check
```

Redis query 参数是命令文本，例如 `TYPE cache_key`、`HGETALL hash_key`。只允许只读命令。

Mongo query 参数是 JSON 对象，例如 `{"op":"findOne","collection":"orders","filter":{"id":"xxx"}}`。只允许 `listCollections`、`findOne`、`find`、`countDocuments`、`distinct`；`find` 和 `listCollections` 会限制输出数量。

## 数据源发现

数据源发现和数据查询必须分离。发现可以来自 Apollo、用户输入或已有工具配置。

`offline-data-query` 不调用 Apollo，也不提供 discover 命令。组合逻辑在 skill 或 agent 层完成：先确认 profile 或 `--source` 参数，再调用 query。
