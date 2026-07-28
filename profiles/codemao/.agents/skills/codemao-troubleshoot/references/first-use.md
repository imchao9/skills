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

## 保存 SLS 登录凭据

在终端执行以下两条命令，并将 `"你的阿里云账号"` 替换为实际登录账号。

保存登录密码：

```bash
security add-generic-password -U -s alilog -a "你的阿里云账号" -w
```

保存 TOTP seed：

```bash
security add-generic-password -U -s alilog-totp -a "你的阿里云账号" -w
```

命令等待输入时，直接粘贴对应的密码或 TOTP seed 并按回车。输入内容不会显示。两条命令必须使用同一个账号；`-U` 会更新已有的 Keychain 条目。

如需核对保存结果，可以分别执行：

查看登录密码：

```bash
security find-generic-password -s alilog -a "你的阿里云账号" -w
```

查看 TOTP seed：

```bash
security find-generic-password -s alilog-totp -a "你的阿里云账号" -w
```

命令会在终端中明文显示密码或 TOTP seed，请勿在屏幕共享或录屏时执行。

不配置这些凭据也可以使用 SLS，但需要在 Chrome 中手动登录。


### TOTP seed 的格式和获取方式

TOTP seed 是虚拟 MFA 生成动态安全码所使用的长期密钥，不是认证器当前显示的 6 位安全码。可以保存以下任一种内容：

- Base32 seed
- 完整的 `otpauth://totp/...` URL

例如：

Base32 seed：

```text
JBSWY3DPEHPK3PXP
```

完整的 `otpauth://` URL：

```text
otpauth://totp/Aliyun:example?secret=JBSWY3DPEHPK3PXP&issuer=Aliyun
```

绑定或重新绑定阿里云虚拟 MFA 时，选择手动添加。页面显示的“密钥”就是 seed；已有完整的 `otpauth://totp/...` URL 时，也可以直接使用。

二维码图片、短信验证码和当前显示的 6 位安全码都不能作为 seed。如果没有原始密钥或完整 URL，需要通过有权限的虚拟 MFA 重新绑定流程生成。

自动填充仅支持 RFC 6238 TOTP：`SHA1`、6 位安全码和 30 秒周期。

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

### 验证配置

运行：

```bash
scripts/alilog auth
```

同一次 `auth` 运行维护一份凭据计划。账号未知的有头自动填充可能在账号出现在页面后，才首次读取对应的 Keychain 条目；某项从 Keychain 读取后，即使随后更新，当前窗口也不会重新读取。若页面明确提示密码或安全码错误，当前窗口会停止自动填充，你仍可在该页面手动输入并完成本次登录；更新凭据后，请重新运行 `scripts/alilog auth`。

认证流程、输出和登录失败处理见 `references/sls.md`。
