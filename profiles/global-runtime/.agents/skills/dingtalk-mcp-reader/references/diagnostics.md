# 钉钉 MCP 诊断

路径失败或缺少必需工具时使用本参考。

## 组合模式

当本技能被其他技能引用时，默认非交互：
- 不直接向用户追问读取范围、抽样深度或权限修复方式。
- 先按当前可见工具和默认范围读取。
- 失败时先走恢复阶梯；只把恢复后仍未读到的问题写入 `gaps`、`errors` 或 `next_actions`。
- 如果没有任何可用内容，返回 `failed` 和 `USER_INPUT_REQUIRED` 或具体失败码。

## 恢复优先

一次工具失败、一次 HTTP 超时、一个格式为空，都不是最终缺口。先按下面顺序恢复：

1. 重试同一只读工具或下载请求，至少 2 次；HTTP 下载使用较长超时，必要时串行处理。
2. 换等价只读路径：正文在 `markdown`、`jsonml`、`list_document_blocks` 之间互补；资源在 Markdown URL、JsonML `resourceId`、block `resourceId` 之间互补。
3. 刷新临时凭证：有 `resourceId` 时重新调用 `download_doc_attachment`；普通文件重新调用 `download_file`。
4. 使用可见导出能力：仅在工具支持且类型允许时，对 `adoc` 尝试导出 `markdown` 或 `docx` 以恢复正文和内嵌图片。
5. 复核失败性质：区分网络超时、权限失败、过期签名、占位图、空内容和解析失败。

只有这些路径都不可用或失败，才输出 `gaps`。每个 `gap` 必须带 `recovery_attempts`，写明尝试过哪些路径。

## 工具可见性

先以当前会话实际可见的工具为准。必需工具不可见时，不要描述对应内容已经读取。

常见缺口：
- 缺少钉钉文档 MCP：无法读取元信息或在线文档。
- 缺少钉钉表格 MCP：无法结构化读取 `axls`。
- 缺少钉钉 AI 表格 MCP：无法结构化读取 `able` 记录。
- 缺少本地文件解析工具：文件已下载，但内容无法解析。

表格/AI 表工具缺失时，输出预期工具名和启用建议。

错误码：
- `TOOL_MISSING`：必需 MCP 工具在当前会话不可见。
- `TOOL_NOT_HOT_LOADED`：协议级可见或配置存在，但当前会话未暴露工具。
- `TOOL_CALL_FAILED`：工具可见但调用失败。

已接入但当前会话不可见时：
- 可能是 Codex 会话未重新加载 MCP 配置。
- 让用户刷新/重开会话后再验证工具是否出现。
- 如果协议级 `tools/list` 可见，但当前工具列表不可见，报告为“已接入，当前会话未热加载”。
- 不要因此声称表格或 AI 表内容已读取。

## 权限和鉴权

症状：
- 元信息不可用。
- nodeId 有效但正文为空。
- 资源下载跳转到 `noAuth.png`。
- HTTP 401/403。
- OSS 返回 XML 错误。

处理：
- 记录 nodeId 或脱敏 URL。
- 记录失败工具和错误摘要。
- 请用户授权、提供新导出或原始文件。
- 不要声称完整读取。

错误码：
- `AUTH_FAILED`：元信息、正文或资源因权限失败不可读。
- `EMPTY_RESULT`：nodeId 有效但正文、范围或记录为空；必须说明这是空结果还是字段未返回。

## OSS 和临时 URL

临时 OSS URL 可能过期或失去权限上下文。

规则：
- 下载前不要改写、解码重组或丢弃 query 参数。
- 签名 URL 失败时，优先用 `resourceId` 通过 MCP 刷新。
- HTTP 超时或连接失败时，不立即判定失败；先重试，再刷新 `resourceId`，再尝试其他已登记来源。
- 输出中脱敏 `Expires`、`OSSAccessKeyId`、`Signature`、token 和 headers。
- `403 application/xml` 表示资源未恢复。

错误码：
- `RESOURCE_EXPIRED`：签名 URL 过期或 OSS 返回过期类错误。
- `DOWNLOAD_FAILED`：资源下载失败且无法用 `resourceId` 刷新恢复。

## noAuth 和占位图

以下都视为无效证据：
- URL 跳转到 `noAuth.png`。
- 多张不相关图片有相同字节数/hash。
- Content-Type 是图片，但内容是已知占位图。
- 图片尺寸符合占位图而非预期业务截图。

输出：
- 关键图片命中这些情况时，`完整性判断：partial（部分完整）`。
- 尽量给出 resourceId 或 block id。
- 记录已经尝试过的失败路径。

错误码：
- `RESOURCE_NO_AUTH`：资源跳转到 `noAuth.png` 或等价无权限占位图。
- `RESOURCE_PLACEHOLDER`：命中重复占位图哈希、尺寸或内容。

## 导出失败

仅对工具支持的文档类型使用导出，尤其是 `adoc`。

记录：
- 导出格式。
- job id。
- job 状态。
- 失败信息。
- 是否已有其他路径提供足够内容。

不要用通用导出伪装结构化读取 `axls` 或 `able`。

错误码：
- `EXPORT_FAILED`：导出任务失败、超时或导出结果不可下载。
- `ROUTE_UNSUPPORTED`：元信息类型不在当前路由矩阵内，或工具没有对应只读读取路径。

## 安全输出

不要输出完整密钥：
- 带 `key=` 的私有 MCP 网关 URL。
- Cookie。
- 鉴权 headers。
- 签名 OSS URL。
- 临时下载凭证。

使用脱敏示例：
- `https://.../file.png?Expires=<redacted>&Signature=<redacted>`
- `Authorization: <redacted>`

接入记录也必须脱敏：
- 可以写 `dingtalk-sheet：已配置，URL 已脱敏`。
- 可以写 `dingtalk-ai-table：已配置，URL 已脱敏`。
- 不要把 MCP 网关完整 URL 写入技能文件、提交信息、验证报告或用户可见输出。

## 安全执行

- 临时下载文件放在当前任务工作目录的临时子目录，不写入用户主目录。
- 不把 Cookie、鉴权 headers、OSS 签名 URL 或私有 MCP 网关 URL 写入用户可见产物。
- 解析 zip 或压缩包时只列出和读取安全路径；忽略绝对路径、`..`、`__MACOSX/` 和 `.DS_Store`。
- 大文件、未知二进制或外部链接超出当前任务需要时，只登记元信息和缺口，不强行下载。

## 状态判断

| 场景 | 状态 | 要求 |
| --- | --- | --- |
| 元信息失败，无法确认类型 | `failed` | 记录 `AUTH_FAILED`、`TOOL_CALL_FAILED` 或 `ROUTE_UNSUPPORTED` |
| 元信息成功，但必需专用工具缺失 | `partial` | 记录 `TOOL_MISSING` 和未读取的数据类型 |
| 正文/表格/记录按请求范围读完，关键资源已读或标非关键 | `complete` | 写明覆盖范围 |
| 只做抽样、分页未读完或范围受限 | `partial` | 记录 `PARTIAL_COVERAGE` 和未覆盖范围 |
| 表格工具可用但指定范围为空 | `complete` 或 `partial` | 若目标就是该范围则 `complete`；若无法判断全表则 `partial`，并写 `EMPTY_RESULT` |
| 关键图片、附件或文件恢复阶梯耗尽后仍失败 | `partial` | 记录资源错误码、`recovery_attempts` 和影响 |
| 只有非关键资源失败 | `complete` | 资源清单中标注未校验，不作为依据 |
| 所有读取路径都失败，没有可用内容 | `failed` | 给出可执行下一步 |

通用错误码：
- `PARTIAL_COVERAGE`：只覆盖了部分 block、sheet、range、table、record 或文件内容。
- `PARSE_FAILED`：文件已下载但无法解析。
- `USER_INPUT_REQUIRED`：必须由用户授权、刷新链接、提供文件或确认范围才能继续。
