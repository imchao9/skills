# 钉钉 MCP 路由

收到 `get_document_info` 的元信息后使用本参考。

## 通用第一步

对每个钉钉 URL 或 nodeId：

1. 调用 `get_document_info(nodeId)`。
2. 读取 `contentType`、`extension`、`nodeType`、`name`、`nodeId`、`docUrl`。
3. 根据下面规则选择读取路径。
4. 在最终报告中记录实际路径和不可用工具。

默认范围：
- 未指定范围时，在线文档优先读取完整 Markdown，并读取一级 blocks 到工具返回无更多数据。
- 未指定范围时，表格先列出全部 sheet，再读取每个 sheet 的表头和前 100 行非空区域；更多数据标记为 `PARTIAL_COVERAGE`。
- 未指定范围时，AI 表格先列出全部 table，再读取每个 table 的字段目录和前 100 条记录；更多数据标记为 `PARTIAL_COVERAGE`。
- 被其他技能调用时不直接询问用户；无法判断相关性时按默认范围抽样，并把需确认问题写入 `next_actions`。

## 在线文档：`contentType=ALIDOC`，`extension=adoc`

首选路径：
- `get_document_content(nodeId, format=markdown)` 读取 Markdown 正文。
- Markdown 丢结构且工具支持时，使用 `get_document_content(nodeId, format=jsonml)`。
- `list_document_blocks(nodeId, format=jsonml)` 发现块结构、卡片、表格和资源。
- 对附件类 card 或关键图片/文件资源，使用 `download_doc_attachment(nodeId, resourceId)`。

正文恢复：
- `markdown` 失败但 `jsonml` 或 blocks 成功时，不要停止；用 JsonML/blocks 恢复正文结构，并记录 Markdown 路径为已恢复的错误。
- `jsonml` 失败但 Markdown 成功时，继续用 blocks 补资源和结构。
- Markdown、JsonML、blocks 任一路径失败时，按诊断恢复阶梯重试；至少两条正文路径失败后，才把正文列为未恢复。

block 分页：
- 如果 `list_document_blocks` 返回 `hasMore`、游标或部分范围，继续读取直到没有更多 block。
- 如果只支持 `startIndex`/`endIndex`，按小批次读取，并按返回数量或请求范围推进。
- 记录 `totalCount`、已返回数量，以及未展开的嵌套 block/table/card 缺口。

导出路径：
- 仅在当前工具声明支持时，对 `adoc` 使用 `submit_export_job(nodeId, exportFormat=markdown|docx|pdf)`。
- `markdown` 适合恢复文本和资源引用；`docx` 适合恢复文档内嵌图片；`pdf` 仅在需要版式视觉或其他格式被拒绝时使用。
- 使用 `query_export_job(jobId)` 轮询导出结果。
- docx 解包可恢复 `word/media/` 中的内嵌图片，但不要假设能恢复附件。

完整性判断：
- 正文和所有关键资源都已读取，或明确标为非关键时，输出 `complete`。
- 关键资源、block 或导出路径失败且影响使用判断时，输出 `partial`。

## 钉钉表格：`contentType=ALIDOC`，`extension=axls`

必需路径：
- 使用钉钉表格 MCP。
- 预期已接入 server：`dingtalk-sheet`。
- 核心读取工具：`get_all_sheets(nodeId)`，然后 `get_range(nodeId, sheetId, range)`。
- 辅助读取工具：`get_sheet`、`get_range_as_csv`、`get_cell_infos`、`find_cells`、`get_filter`、`get_filter_views`、`list_float_images`、`get_float_image`、`submit_export_job`、`query_export_job`。
- 列出 sheet 后，如果用户指定目标，优先读取相关 sheet；如果未指定，按默认范围抽样读取表头和非空范围，并记录未覆盖 sheet/range。
- 大表格按有界范围分批读取，并说明抽样/完整覆盖范围，不要暗示已读完整工作簿。

默认不要使用写入/变更工具：
- `append_rows`、`set_cell_range`、`set_range_from_csv`、`update_range`
- `create_sheet`、`delete_sheet`、`copy_sheet`、`update_sheet`
- `add_dimension`、`insert_dimension`、`delete_dimension`、`move_dimension`、`update_dimension`
- `clear_range`、`copy_range`、`move_range`、`fill_range`
- `create_*`、`update_*`、`delete_*`、`set_*`、`replace_all`、`sort_*`、`write_image`

不要用这些通用路径伪读表格：
- `get_document_content`
- `download_file`

如果表格工具不可见：
- 输出 `partial`。
- 明确说明结构化表格内容未读取。
- 建议安装或启用钉钉表格 MCP。
- 预期工具名：`get_all_sheets`、`get_range`。

## 钉钉 AI 表格：`contentType=ALIDOC`，`extension=able`

必需路径：
- 使用钉钉 AI 表格 MCP。
- 预期已接入 server：`dingtalk-ai-table`。
- 核心读取工具：`get_base`、`get_tables(nodeId)`，然后 `query_records(nodeId, tableId)`。
- 辅助读取工具：`list_bases`、`search_bases`、`get_fields`、`get_views`、`query_records_stats`、`query_stats`、`get_dashboard`、`get_chart`、`export_data`。
- 工具要求 baseId 时，将 `nodeId` 作为 baseId。
- 列出 table 后，优先查询相关 table；无法判断相关性时，先抽样 table 名、字段和初始记录，并记录未覆盖 table/record。
- 如果工具支持分页、筛选或字段选择，按用户请求需要继续翻页，并记录未查询的 table 或字段。

默认不要使用写入/变更工具：
- `create_base`、`copy_base`、`update_base`、`delete_base`
- `create_table`、`update_table`、`delete_table`
- `create_fields`、`update_field`、`delete_field`
- `create_records`、`update_records`、`delete_records`
- `create_view`、`update_view`、`delete_view`
- `create_dashboard`、`update_dashboard`、`delete_dashboard`
- `create_chart`、`update_chart`、`delete_chart`
- `prepare_*`、`import_data`、`run_*`、`set_*`

不要用这些通用路径伪读 AI 表：
- `get_document_content`
- `download_file`
- `submit_export_job`

如果 AI 表格工具不可见：
- 输出 `partial`。
- 明确说明结构化 AI 表记录未读取。
- 建议安装或启用钉钉 AI 表格 MCP。
- 预期工具名：`get_tables`、`query_records`。

## 普通文件：`contentType!=ALIDOC` 且 `nodeType=file`

首选路径：
- 调用 `download_file(nodeId)`。
- 使用返回的 `resourceUrl` 和签名 headers 发起 HTTP GET。
- 在凭证过期前完成下载。

按类型解析：
- text/markdown：直接读取。
- docx/pdf/spreadsheet：使用可用的本地文档工具。
- zip：先列目录；忽略 `__MACOSX/` 和 `.DS_Store`；解析内部可读文件。
- image：登记元信息；仅在需要时做视觉检查。

下载失败时：
- 记录 HTTP 状态、Content-Type、错误摘要、凭证过期风险和下一步建议。

## 未支持或不可路由类型

适用场景：
- `get_document_info` 成功，但 `contentType`、`extension`、`nodeType` 组合不在本文件覆盖范围内。
- 来源是文件夹、快捷链接、未知导出产物或 URL 无法解析成 nodeId。
- 混合型 `adoc` 中包含无法展开的外部卡片或嵌入对象。

处理：
- 不猜测内容，不用相近工具伪读。
- 输出 `partial` 或 `failed`，错误码使用 `ROUTE_UNSUPPORTED`。
- 记录已知元信息、不可路由字段和建议的补充输入。

## 图片、附件和卡片

发现来源：
- Markdown 链接和图片。
- JsonML 节点。
- `list_document_blocks` 返回的 card block。
- attachment/file-like block 元信息。

处理方式：
- 下载时内部保留完整签名 URL；输出时必须脱敏。
- 优先使用 `resourceId` + `download_doc_attachment` 刷新临时 URL。
- `download_doc_attachment` 失败时，尝试 Markdown 中的 OSS URL、JsonML `src` 对应资源、blocks 中的 `resourceId` 重新刷新；只有所有来源都失败后才标记未恢复。
- 关键资源需要下载和解析/校验。
- 非关键资源可以只做基础登记，并标注 `未校验，不作为依据`。
- 关键图片校验使用本地 HTTP 下载和可用图片检查能力，记录 Content-Type、字节数、像素尺寸、sha256，以及是否是真实业务图片或占位图。
- 关键附件校验时，下载文件、尽量计算 sha256、识别 MIME/扩展名，并用可用本地文档/表格/pdf/zip/image 工具解析或摘要。

无效证据：
- `noAuth.png`
- 过期 OSS URL
- `403 application/xml`
- 不相关图片得到相同占位图 hash
- 关键图片没有下载或视觉校验
