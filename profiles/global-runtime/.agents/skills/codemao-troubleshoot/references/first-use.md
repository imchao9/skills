# 首次使用

## 何时读取

用户说明首次使用、新机器、刚分发、刚更新 skill，或工具报依赖缺失时读取。正常排障不要每次读取或重复 setup。

## 先用这条

```bash
scripts/skillctl setup --check
```

## Gotchas

- 正常排障不要每次 setup；只有首次、新机器、刚更新或工具报依赖缺失时再检查。
- `setup --check` 只检查本地依赖，不代表 SLS、dbops 或 service-api 已登录。
- alilog 自动填充是可选初始化，不配置也可以手动登录。

如果提示缺依赖，再运行：

```bash
scripts/skillctl setup --install
```

## 配置 alilog 自动填充

如果要使用 SLS，建议配置阿里云登录自动填充。这样 `scripts/alilog auth` 可以辅助填写账号、密码和 TOTP 安全码。

不配置也可以使用 SLS，只是登录时需要手动填写。

### 自动填充行为

脚本只在对应输入框为空时填写账号、密码和 TOTP，不会覆盖你已经填写的内容，也不会点击下一步、登录、获取验证码、提交验证或安全验证按钮。

短信/手机验证码不能由本地 TOTP seed 生成。脚本检测到手机验证码输入框时，只会提示手动获取并填写，不会把本地 TOTP 填进去。

遇到阿里云滑块验证码时，脚本会停止本轮自动填充，重新打开 RAM 登录页，最多自动恢复 2 次。仍失败时会提示完整手动登录。

### 保存密码

把 `<account>` 换成阿里云账号：

```bash
read -rsp "Aliyun password: " ALILOG_PASSWORD; echo
security add-generic-password -U -s alilog -a "<account>" -w "$ALILOG_PASSWORD"
unset ALILOG_PASSWORD
```

### 保存 TOTP seed

支持普通 TOTP seed，也支持 `otpauth://` URL。把 `<account>` 换成同一个阿里云账号：

```bash
read -rsp "Aliyun TOTP seed or otpauth URL: " ALILOG_TOTP_SEED; echo
security add-generic-password -U -s alilog-totp -a "<account>" -w "$ALILOG_TOTP_SEED"
unset ALILOG_TOTP_SEED
```

### 账号来源

脚本按这个顺序获取账号：

```text
ALILOG_USERNAME
-> output/alilog-user.json
-> Keychain service=alilog 的 account
-> Keychain service=alilog-totp 的 account
-> 登录页手动填写
```

通常只要密码或 TOTP seed 已经保存到 Keychain，脚本就能从对应 Keychain 条目的 `acct` 字段反查账号，不一定需要 `output/alilog-user.json`。

### 验证

运行：

```bash
scripts/alilog auth
```

成功后 stdout 只输出：

```text
auth ready
```

需要查看自动填充、验证码恢复、CSRF 捕获等状态时运行：

```bash
scripts/alilog auth --debug
```

不要把密码、TOTP seed、cookie、CSRF token 或 `output/alilog-auth.json` 内容粘贴到聊天或文档里。
