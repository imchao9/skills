# 钉钉资源与类型路由

## 标识分流

- 钉钉 URL、文档 nodeId 或类型不明的顶层资源：先调用 `get_document_info`。
- 已明确是 baseId：先调用 `get_base`；不要把 tableId 或 recordId 交给文档元信息工具。
- sheetId、tableId、recordId、fieldId、viewId、dashboardId、chartId、blockId：结合父级稳定标识，使用对应类型的目录或读取工具确认。
- 无法识别的标识只做最小只读探测；不得为了识别而创建占位资产。

## 类型矩阵

| 元信息 | 类型 | 首选读取路线 | 禁止的错误兜底 |
| --- | --- | --- | --- |
| `ALIDOC/adoc` | 在线文档 | `get_document_content` + `list_document_blocks` | 无结构证据却宣称图片/附件完整 |
| `ALIDOC/axls` | 钉钉表格 | `get_all_sheets` + 范围读取 | `get_document_content`、通用文件下载 |
| `ALIDOC/able` | 钉钉 AI 表格 | `get_base/get_tables` + `query_records` | `get_document_content`、通用文件下载 |
| `contentType!=ALIDOC` 且 `nodeType=file` | 普通文件 | `download_file` 后按 MIME/扩展名解析 | 把元信息当成文件正文 |

## 默认读取覆盖

- `adoc`：读取完整 Markdown；结构或资源重要时补 JsonML 和一级 blocks，并分页到没有更多数据。
- `axls`：列出全部 sheet；未指定范围时读取每个 sheet 的表头与前 100 行非空区域，更多内容记 `PARTIAL_COVERAGE`。
- `able`：列出全部 table 与字段目录；未指定范围时查询每个 table 前 100 条记录，更多内容记 `PARTIAL_COVERAGE`。
- 普通文件：下载后按类型解析；大型未知二进制只登记元信息和缺口。
- 被其他技能调用时不因抽样范围不明立即追问；先执行默认范围，把需要决策的问题放入 `next_actions`。

写入任务不执行上述全量默认扫描，只读取目标变更所需的最小现状和验证范围。

## 类型冲突与未知类型

- 用户描述与元信息冲突时以元信息为准，并说明实际路由。
- 文件夹、快捷链接、未知导出物或无法展开的卡片不猜内容；记录 `ROUTE_UNSUPPORTED`。
- 类型专用工具缺失时保留已取得元信息，转到 [availability.md](availability.md)。
