---
name: dingtalk-mcp-reader
description: 用于只读读取和诊断钉钉资料，并把钉钉文档、表格、AI 表格、文件、图片、附件转换为脱敏、可追溯、可被下游技能消费的读取证据包；当其他技能需要消费钉钉内容或判断 MCP/权限/资源完整性时使用。
---

# dingtalk-mcp-reader

## 概览

本技能的目标是把钉钉资料变成可信读取证据包：资料是什么类型、读到了什么、覆盖到哪里、哪些证据可信、哪里仍未恢复、是否足够继续后续任务。核心倾向是恢复优先：一次工具失败不是结论，必须继续尝试可用兜底路径。

默认只读：除非用户明确要求写入，否则不要调用更新、插入、删除、导入、上传等写入类工具。本技能不生成需求清单、需求收集单、技术方案、测试用例或其他业务交付物；下游技能可以基于证据包继续处理。

## 下游调用契约

当其他技能引用本技能时，按子程序使用：

- 输入：一个或多个钉钉 URL、nodeId、导出文件或资源线索；可附带调用方任务、目标范围、是否允许抽样、资源校验策略、最大读取范围、是否需要审计证据。
- 输出：正文摘要、结构化表格/记录摘要、资源清单、覆盖范围、完整性状态、未恢复项、恢复尝试、错误和下一步建议。
- 保证：先 `get_document_info`，只按 `contentType`、`extension`、`nodeType` 路由；只用可见只读工具；敏感 URL、Cookie、签名、鉴权头必须脱敏。
- 不做：伪造未读取内容、把 `partial` 当 `complete`、用通用文档工具伪读 `axls` 或 `able`。
- 非交互组合模式：被其他技能调用时，不因范围不明直接追问用户；先按默认读取/抽样策略执行，把需要上游决策的问题放入 `gaps` 或 `next_actions`。

## 执行流程

1. 识别来源：抽取每个钉钉 URL 或 nodeId；完成条件是每个来源都有待调用标识或被记录为不可识别。
2. 获取元信息：每个钉钉 URL 或 nodeId 都先调用 `get_document_info`；失败时读取 [references/diagnostics.md](references/diagnostics.md) 并记录错误。
3. 类型路由：根据 `contentType`、`extension`、`nodeType` 读取 [references/routing.md](references/routing.md) 并选择只读路径。
4. 恢复内容：读取正文、sheet、记录或文件；任一路径失败时按 [references/diagnostics.md](references/diagnostics.md) 的恢复阶梯继续尝试，不要过早输出缺口。
5. 资源取证：登记图片、附件、card 和外链；关键资源必须升级为下载、哈希、尺寸或解析校验，失败时继续刷新和换源。
6. 输出证据包：给出稳定字段和中文报告；完成条件是状态、覆盖范围、未恢复项、恢复尝试和脱敏情况清楚。

## 核心规则

- 任何钉钉 URL 或 nodeId 都必须先调用 `get_document_info`。
- 只根据 `contentType`、`extension`、`nodeType` 路由，不要只凭 URL 文本猜类型。
- 尽量使用当前可见的只读 MCP 能力；缺少必需的专用工具时，不要声称完整读取。
- 不要用通用文档工具伪装结构化读取钉钉表格或钉钉 AI 表格。
- 对正文、表格、记录、关键图片和关键附件执行恢复优先策略；只有所有可用恢复路径耗尽后，才把内容列入 `gaps`。
- 不要泄露密钥：用户可见输出中必须脱敏私有 MCP 网关 URL 的 `key`、临时 OSS 签名、Cookie、鉴权头和下载凭证。
- 表格和 AI 表格 MCP 暴露了大量写入/删除工具；本技能默认只允许读取、查询、导出类工具，写入、创建、更新、删除、导入、上传类工具必须视为禁用。

## 类型路由

判断 `adoc`、`axls`、`able`、普通文件、图片、附件或导出产物该调用哪个 MCP 时，读取 [references/routing.md](references/routing.md)。

快速路由表：

| 钉钉类型 | 首选路径 | 禁止的错误兜底 |
| --- | --- | --- |
| `ALIDOC/adoc` | `get_document_content`、`list_document_blocks`、附件下载、导出 | 无；失败路径要记录 |
| `ALIDOC/axls` | 表格 MCP：`get_all_sheets` + `get_range` | `get_document_content`、`download_file`、通用导出 |
| `ALIDOC/able` | AI 表格 MCP：`get_tables` + `query_records` | `get_document_content`、`download_file`、通用导出 |
| `contentType!=ALIDOC` 且 `nodeType=file` | `download_file` 后按 MIME/扩展名解析 | 把元信息当成文件内容 |

如果当前会话看不到必需工具、权限失败、资源过期、命中 `noAuth.png`、OSS 失败、导出失败或疑似 MCP 未热加载，输出 `partial（部分完整）` 或 `failed（失败）`，列出缺失工具和错误码，并读取 [references/diagnostics.md](references/diagnostics.md)。

## 资源处理

- 从 Markdown、JsonML、blocks、cards、文件节点中登记图片和附件。
- 基础登记字段：来源位置、资源类型、resourceId 或脱敏 URL、名称、下载状态、解析状态、恢复尝试或未恢复说明。
- 仅当资源影响内容理解、字段、数据、权限、时间规则、验收，或用户要求审计留痕时，才升级为下载和完整校验。
- 关键图片需记录 HTTP 状态、Content-Type、字节数、像素尺寸（可取得时）、sha256、视觉或校验结论。
- 关键文件或附件需记录文件名、MIME 或扩展名、字节数、sha256（可取得时）、解析结论。
- 关键资源的下载失败必须先重试和换源；没有完成恢复阶梯时，不要最终报告为未恢复。
- `noAuth.png`、过期 OSS URL、`403 application/xml`、重复占位图哈希、未下载或未视觉校验的关键图片，都不能作为真实证据。
- 长文档或大表格必须说明实际覆盖范围：页数、block 范围、sheet 范围、表名、记录页，以及未查询的剩余部分。

## 输出契约

先给稳定字段，再给中文标题；保持紧凑。下游技能优先消费稳定字段：

```json
{
  "status": "complete | partial | failed",
  "sources": [
    {
      "input": "<redacted-or-nodeId>",
      "nodeId": "",
      "name": "",
      "source_type": "adoc | axls | able | file | unknown",
      "route": "",
      "coverage": "",
      "content_summary": "",
      "tables": [],
      "records": [],
      "resources": [],
      "gaps": [],
      "errors": [],
      "recovery_attempts": [],
      "redactions": [],
      "next_actions": []
    }
  ]
}
```

中文报告包含：

1. `读取结果`：已确认的正文、表格、记录、文件、图片、附件摘要。
2. `资料清单`：来源位置、resourceId 或脱敏 URL、下载状态、解析状态。
3. `完整性判断`：`complete（完整）`、`partial（部分完整）` 或 `failed（失败）`。
4. `未恢复项与影响`：所有恢复路径耗尽后仍未读到的内容、已尝试路径，以及是否影响使用判断。
5. `下一步建议`：安装或启用 MCP、授权访问、提供导出文件/原始文件、刷新链接、补充资源，或由上游技能向用户确认范围。

不要输出完整临时 OSS URL 或签名下载凭证。使用脱敏形式，例如：`https://.../sample.png?...Signature=<redacted>`。

最小报告示例：

```md
## 读取结果
- 正文：已读取 Markdown，共 6 个标题、2 个表格、5 个附件/图片线索。
- 表格/记录：未读取，当前会话缺少 `get_all_sheets/get_range`。

## 资料清单
| 类型 | 位置 | 标识 | 下载状态 | 解析状态 |
| --- | --- | --- | --- | --- |
| 图片 | block 13 | resourceId: xxx | 302 到 noAuth.png | 不能作为真实图片证据 |

## 完整性判断
partial（部分完整）

## 未恢复项与影响
- 关键图片未恢复，可能影响对截图规则的判断。

## 下一步建议
- 开启对应 MCP 或提供原始导出文件/图片。
```

## 维护验证

实现或更新本技能时：

- 若存在校验脚本，运行脚本；若没有脚本，执行下面的静态清单并记录无法验证的原因。
- 检查关键词覆盖：`adoc`、`axls`、`able`、`noAuth.png`、`OSS`、`resourceId`、`get_all_sheets`、`get_range`、`get_tables`、`query_records`。
- 至少做一次只读钉钉 MCP 连通性验证，例如 `list_nodes`；当前会话没有工具或权限时，记录为未验证，不要写成已验证。
- 有可访问样本时，验证 `get_document_info` 和对应类型路由。
- 确认技能目录中没有 `.bak`、`*~`、`.DS_Store`。

## 参考文件

- 类型路由使用 [references/routing.md](references/routing.md)。
- 失败诊断和安全输出使用 [references/diagnostics.md](references/diagnostics.md)。
- 只有维护、评审或修改本技能时读取 [references/cases.md](references/cases.md)；普通读取任务不要加载它。
