# TAPD 认证

配置或测试 TAPD 凭证前先读取本说明。

## 选择认证方式

| 方式 | 输入 | 适用场景 |
|---|---|---|
| 个人访问令牌 | `TAPD_ACCESS_TOKEN` | 个人交互式自动化和 Agent 只读查询 |
| API 用户名和密码 | `TAPD_API_USER`、`TAPD_API_PASSWORD` | 现有集成已经使用传统 API 凭证 |
| 应用凭证 | `TAPD_APP_ID`、`TAPD_APP_SECRET` | 由边界明确的服务负责令牌交换和密钥管理 |
| 浏览器会话 | 现有浏览器登录态 | OpenAPI 无法复现准确的保存列表视图 |

个人访问令牌是 Bearer 凭证，不是 AK/SK。用户已有个人令牌时，CLI 路径优先使用该方式。
一种认证方式失败后，不要静默改用另一种方式。

## 安全注入个人令牌

优先使用当前运行环境提供的安全环境变量。本地交互式 Shell 可通过隐藏输入避免令牌进入历史记录：

```bash
read -r -s TAPD_ACCESS_TOKEN
printf '\n'
export TAPD_ACCESS_TOKEN
tapd workspace list
unset TAPD_ACCESS_TOKEN
```

禁止：

- 通过 `--access-token` 传递令牌，或把令牌插入 Agent 命令字符串；
- 把令牌写入 `SKILL.md`、`agents/openai.yaml`、参考文档、示例、`.env` 或日志；
- 仅为完成一次查询而创建或覆盖 `.tapd.json`；
- 打印环境变量块、Authorization Header 或原始配置文件。

用户主动配置的现有 `.tapd.json` 可以在不展示其内容的前提下使用。创建或修改该文件属于
持久化外部副作用，必须获得用户明确授权。

## 以最小范围验证

按以下顺序执行无副作用读取：

```bash
tapd workspace list
tapd workspace info --workspace-id <workspace-id>
tapd story count --workspace-id <workspace-id>
```

成功只能证明令牌有效且可以读取已测试工作区，不能证明它有权读取所有工作区、字段、附件、
Wiki 或执行写操作。不要为了探测权限而测试写入。

只汇报认证方式、命令结果、目标工作区和最小权限证据。不要返回令牌或无关工作区数据。

## 处理已经暴露的令牌

令牌一旦出现在聊天、命令记录、终端历史、截图或 Git 跟踪文件中，就按已暴露处理。
只有用户明确接受当前操作风险时才继续使用，不要再次复制令牌，并建议测试后撤销和更换。
不要把令牌保存到记忆或仓库产物。
