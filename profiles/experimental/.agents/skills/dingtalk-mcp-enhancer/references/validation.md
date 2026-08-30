# 验证与维护协议

## 原则

- 能力始终以当前会话真实工具 schema、权限和独立读回为准。
- 历史证据帮助选择路线，不充当白名单；新工具先标 `not-yet-tested`，仍允许最小尝试。
- 远程验证必须使用隔离资产，并在创建前说明名称、位置、用途和清理方式，取得授权。创建授权不包含删除授权。
- 运行名统一使用 `Agent-DingTalk-MCP-Validation-YYYYMMDD-HHMMSS-*`。
- `able` 名称还必须服从当前 schema 的长度上限；当前上限为 50 字符时使用 `-a1`、`-a2` 等紧凑后缀，不为保留冗长类型说明而发送必然失败的创建请求。
- 本地盲测不得创建远程钉钉资产，也不得实际发起上传、分享、通知、工作流、AI 或同步。

## 固定夹具

| 文件 | 类型 | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| `assets/validation/dingtalk-validation-image.png` | PNG | 以校验脚本为准 | `388782231ef66f9ab044e673d95cea358f58d9779152097235fb5140e44b35e3` |
| `assets/validation/dingtalk-validation-attachment.txt` | UTF-8 文本 | 以校验脚本为准 | `2958d7fbb95d7699b250f32799db8f061ddd63eaf934d0405f665f2684fc34c9` |
| `assets/validation/dingtalk-validation-import.csv` | UTF-8 CSV | 以校验脚本为准 | `20b4d59e3b409d39c05e51e478e4195b5ff92918824ca0ea62f6dce35c680028` |

夹具进入任何上传准备前，先运行 `scripts/validate-skill.sh` 验证存在、类型、大小和哈希。上传后再校验钉钉端元信息，能安全下载时校验下载字节哈希。

## 本地验收

1. 运行平台 `quick_validate.py`、`bash -n scripts/validate-skill.sh` 和技能自带校验。
2. 检查 frontmatter、`agents/openai.yaml`、相对 Markdown 链接、目录结构、脚本权限和 `SKILL.md` 行数。
3. 静默扫描 Markdown、YAML、脚本、JSON、CSV 和文本资产中的凭证模式；命中时只报告文件类别与失败，不打印秘密。
4. 静态脚本验证带日期的 40/74/56 清单完整；远程维护时另从当前会话工具列表按命名空间盘点，并证明每个当前工具在 `capabilities.md` 出现。历史数量不是永久断言。
5. 检查技能不包含私有 MCP 地址、签名 URL、鉴权头值或个人标识。

## 远程验证顺序

1. 读取当前 schema 并建立带时间戳的工具清单。
2. 取得用户对隔离资产的创建授权，再分别创建 adoc、axls、able；每个资产只测试自己的命名空间。
3. 先验证精确创建/更新和独立回读；同时检查调用外层状态、业务状态和目标读回，任一缺失都不能直接算成功。
4. 覆盖、清空、删除、权限、公开分享、通知、工作流、AI 和同步必须二次确认；Chart 创建因当前可能隐式启用分享，也按访问控制操作预览、确认并在创建后立即检查和收敛分享状态。
5. Dashboard 验证同时核对 Base 目录、详情、子 chart 归属和分享状态；分享读取最多两次有界重试，仍不确定就记录 `ACCESS_STATE_UNVERIFIED`。
6. 假成功以读回为准；安全恢复成功就记录替代路线，恢复耗尽且当前复现才新增带日期 `observed-issue`。
7. 清理只处理本轮返回的稳定 ID，并再次取得确认；记录删除语义和可恢复性。

## 核心读写证据

- adoc：元信息、Markdown、JsonML/blocks、图片附件、追加、精确 block、版本恢复。
- axls：sheet 目录、精确范围值/显示值/公式/样式、CSV、下拉、筛选、图片与高级对象。
- able：Base 目录、table/field/view schema、记录分页、附件、导入、dashboard/chart、说明文档。
- 每项写入证据至少包含写前状态、请求参数的脱敏摘要、写响应、独立读回和最终状态。

## 维护结论

| 结果 | 记录方式 |
| --- | --- |
| 当前调用与独立读回一致 | `recommended`，记录日期、参数边界和回读工具 |
| 当前工具存在但证据不足 | `not-yet-tested`，不限制后续最小尝试 |
| 当前复现异常且恢复耗尽 | `observed-issue`，记录日期、环境、恢复路径和影响 |
| 当前会话缺少工具 | `unavailable`，记录稳定错误码，不泛化平台能力 |

验证报告不得包含上传地址、签名 query、headers、Cookie、Token、MCP Key 或临时下载 URL。
