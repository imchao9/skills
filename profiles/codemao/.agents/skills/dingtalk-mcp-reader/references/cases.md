# 验收场景

本文件只提供示例，不新增隐藏规则。规则源是 `SKILL.md`。

本文件仅供维护、评审或修改技能时使用。不要把“已验证”历史状态写入本文件；当前会话是否可读只以实际工具调用结果为准。

## 场景 1：可读 adoc

输入：
- 钉钉节点元信息返回 `contentType=ALIDOC`、`extension=adoc`。

期望：
- 调用 `get_document_content`。
- 资源或结构重要时，调用 `list_document_blocks`。
- 持续分页或按范围读取 block，直到没有更多 block。
- 登记 Markdown 链接、图片、card 和附件。
- 对关键 resourceId 使用 `download_doc_attachment`。
- 只有关键资源已读取或明确为非关键时，才能输出 `complete`。

## 场景 2：axls 缺少表格 MCP

输入：
- 元信息返回 `contentType=ALIDOC`、`extension=axls`。
- 当前会话缺少 `get_all_sheets` 和 `get_range`。

期望：
- 不调用 `get_document_content`、`download_file` 或通用导出。
- 输出 `partial（部分完整）`。
- 明确说明结构化表格内容未读取。
- 建议启用钉钉表格 MCP，并列出预期工具。
- 如果工具可用，按有界范围读取 sheet，并记录抽样/完整覆盖范围。
- 即使表格 MCP 已接入，也只默认使用读取工具；写入、更新、删除、筛选变更、排序变更等工具不得在读取任务中调用。

## 场景 3：able 缺少 AI 表格 MCP

输入：
- 元信息返回 `contentType=ALIDOC`、`extension=able`。
- 当前会话缺少 `get_tables` 和 `query_records`。

期望：
- 不调用 `get_document_content`、`download_file` 或通用导出。
- 输出 `partial（部分完整）`。
- 明确说明结构化 AI 表记录未读取。
- 建议启用钉钉 AI 表格 MCP，并列出预期工具。
- 如果工具可用，按分页/字段覆盖查询记录，并记录未查询的 table 或字段。
- 即使 AI 表格 MCP 已接入，也只默认使用读取/查询/导出工具；创建、更新、删除、导入、运行同步等工具不得在读取任务中调用。

## 场景 3.1：专用 MCP 已接入但会话未热加载

输入：
- 本机配置中已有表格/AI 表格 MCP。
- 协议级 `tools/list` 能看到专用工具。
- 当前 Codex 会话工具列表仍未暴露对应命名空间。

期望：
- 输出“已接入，当前会话未热加载”。
- 建议刷新或重开 Codex 会话后再验证。
- 保持读取结论为 `partial`，直到工具可在当前会话中实际调用并读到数据。

## 场景 4：noAuth 或过期 OSS 图片

输入：
- Markdown 或导出资源路径跳转到 `noAuth.png`，返回 `403 application/xml`，或得到重复占位图字节。

期望：
- 不把图片当作业务证据。
- 如果是关键图片，输出 `partial` 并列出尝试过的 resource id/path。
- 有 resourceId 时，优先通过 MCP 刷新下载。

## 场景 5：普通文件

输入：
- 元信息返回 `contentType!=ALIDOC` 且 `nodeType=file`。

期望：
- 调用 `download_file`。
- 使用签名 URL 和 headers 发起 HTTP GET。
- 按 MIME/扩展名解析。
- 输出时脱敏凭证。

## 场景 6：安全报告

输入：
- 任何包含临时 URL、私有网关 URL 或凭证类 headers 的报告。

期望：
- 脱敏密钥和签名 query 参数。
- 保留 node id、resource id、文件名、content type 和高层错误摘要。
- 不输出需求清单、需求收集单、技术方案等业务交付物。
