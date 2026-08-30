# 钉钉 MCP 能力目录与证据

## 目录

- [快照](#快照)
- [如何使用本目录](#如何使用本目录)
- [钉钉文档 MCP](#钉钉文档-mcp)
- [钉钉表格 MCP](#钉钉表格-mcp)
- [钉钉 AI 表格 MCP](#钉钉-ai-表格-mcp)
- [推荐路线与历史观察](#推荐路线与历史观察)
- [2026-08-03 历史异常重新验证](#2026-08-03-历史异常重新验证)
- [2026-08-04 推广阻塞项双轮复测](#2026-08-04-推广阻塞项双轮复测)
- [覆盖摘要](#覆盖摘要)
- [维护规则](#维护规则)

## 快照

- 盘点日期：2026-08-03（Asia/Shanghai）；推广阻塞项最近复核：2026-08-04
- 来源：当时智能体会话实际可见工具 schema
- 钉钉文档：40 个工具
- 钉钉表格：74 个工具
- 钉钉 AI 表格：56 个工具
- 快照覆盖：当日 170 个可见工具均已登记；数量是带日期的历史快照，不是永久常量。已有证据用于推荐做法，没有证据的工具仍允许按探索协议尝试。

## 如何使用本目录

本目录是增强 MCP 使用体验的模板，不是白名单或能力门禁。它提供推荐路线和历史经验；执行时仍以当前 schema、用户授权和实际影响为准，并分开判断三个维度：

| 维度 | 取值 | 含义 |
| --- | --- | --- |
| 证据 | `recommended` | 已有写入与独立读回证据；优先复用记录的配方 |
| 证据 | `not-yet-tested` | 没有充分历史证据；允许最小尝试，不预先承诺 |
| 证据 | `observed-issue` | 某次环境/参数出现异常；它是排障线索，不能直接视为当前状态。先重新验证并尝试恢复，复现且恢复耗尽后才新增当前观察 |
| 证据 | `unavailable` | 当前会话没有工具；按可用性引导区分未安装、未启用和未热加载 |
| 风险 | `read` / `precise-write` | 读取，或精确创建/更新 |
| 风险 | `destructive` / `irreversible` | 可能清空、删除、覆盖或不可恢复 |
| 风险 | `access-control` | 权限、所有权、跨组织或公开范围 |
| 风险 | `external-impact` | 通知、工作流、AI 执行、同步或其他外部副作用 |

证据不决定能否调用。风险决定需要什么影响预览，授权决定能否执行。

## 钉钉文档 MCP

| 能力 | 工具 | 推荐做法或历史观察 | 风险 | 证据 |
| --- | --- | --- | --- | --- |
| 元信息、发现与搜索 | `get_document_info`, `get_recent_list`, `list_nodes`, `search_documents` | 现有 URL/ID 先确认类型、位置和同名资产 | `read` | `recommended` |
| 正文、结构与样式读取 | `get_document_content`, `get_document_style`, `list_document_blocks` | Markdown 看文本，JsonML/blocks/style 看结构、图片、附件和样式 | `read` | `recommended` |
| 模板发现 | `list_doc_templates`, `search_doc_templates` | 取得 templateId 后再应用 | `read` | `recommended` |
| 版本与权限读取 | `list_doc_versions`, `list_permission` | 版本用于恢复点；权限读取不等于变更授权 | `read` | `recommended` |
| 文件与附件下载 | `download_doc_attachment`, `download_file` | 返回地址和 headers 要脱敏 | `read` | `recommended` |
| 导出任务 | `submit_export_job`, `query_export_job` | 只使用真实 jobId 有界查询 | `read` | `recommended` |
| 创建文档/文件夹/多类型文件 | `create_document`, `create_file`, `create_folder` | 明确名称与位置；正式资产处理同名冲突 | `precise-write` | `recommended` |
| 模板创建 | `apply_doc_template` | templateId 和目标位置必填 | `precise-write` | `recommended` |
| 复制文档 | `copy_document` | 用稳定 nodeId；复制可能异步，按返回 ID 有界查询 | `precise-write` | `recommended` |
| 移动文档 | `move_document` | 确认源节点、目标位置和目录影响 | `destructive` | `recommended` |
| 重命名文档 | `rename_document` | 确认 nodeId、新名称和同名冲突 | `precise-write` | `recommended` |
| 文档正文更新 | `update_document` | 显式 append/overwrite；覆盖前保存版本 | `precise-write` / `destructive` | `recommended` |
| block 写入 | `insert_document_block`, `update_document_block`, `delete_document_block` | 刷新 blockId；删除需确认 | `precise-write` / `destructive` | `recommended` |
| 文档样式 | `update_document_style` | 先读现有样式，写后回读 | `precise-write` | `recommended` |
| 通用文件上传 | `get_file_upload_info`, `commit_uploaded_file` | prepare→PUT→commit；覆盖上传单独确认 | `precise-write` / `destructive` | `recommended` |
| 文档附件上传 | `get_doc_attachment_upload_info` | 立即 PUT；正文插入优先最小稳定字段 | `precise-write` | `recommended` |
| 文件导入 | `create_import_session`, `confirm_import`, `query_import_task` | 服从当前会话上传要求并查询转换结果 | `precise-write` | `recommended` |
| 版本保存与回滚 | `save_doc_version`, `revert_doc_version` | 保存版本可直接做；回滚需确认并验证全文结构 | `precise-write` / `destructive` | `recommended` |
| 删除文档 | `delete_document` | 精确预览目标、回收站/不可恢复语义 | `destructive` | `recommended` |
| 权限与所有权 | `add_permission`, `remove_permission`, `update_permission`, `transfer_owner` | 用户明确指定主体、权限变化和范围后可尝试 | `access-control` | `not-yet-tested` |

## 钉钉表格 MCP

| 能力 | 工具 | 推荐做法或历史观察 | 风险 | 证据 |
| --- | --- | --- | --- | --- |
| 工作簿/工作表发现 | `get_all_sheets`, `get_sheet` | 取得稳定 sheetId、范围和扩展属性 | `read` | `recommended` |
| 单元格与范围读取 | `find_cells`, `get_cell_infos`, `get_range`, `get_range_as_csv`, `table_get` | 优先结构化新工具，记录真实范围 | `read` | `recommended` |
| 模板发现 | `list_sheet_templates`, `search_sheet_templates` | 获取 templateId 和适用范围 | `read` | `recommended` |
| 规则读取 | `get_cond_format`, `get_dropdown_lists`, `get_filter`, `get_filter_views` | 写前保存现状，写后按对象 ID/范围回读 | `read` | `recommended` |
| 高级对象读取 | `get_float_image`, `list_float_images`, `list_float_charts`, `list_pivot_tables` | 取得对象 ID、位置和完整配置 | `read` | `recommended` |
| 公式验证 | `verify_formula` | 写公式后扫描目标范围 | `read` | `recommended` |
| 表格导出 | `submit_export_job`, `query_export_job` | 使用真实 jobId 有界查询；2026-08-03 已重新验证 xlsx 任务创建和完成查询 | `read` | `recommended` |
| 创建工作簿/工作表 | `create_workspace_sheet`, `create_sheet`, `apply_sheet_template` | 明确名称、位置和 templateId | `precise-write` | `recommended` |
| 复制工作表 | `copy_sheet` | 记录返回 sheetId 并重新枚举目录 | `precise-write` | `recommended` |
| 更新工作表属性 | `update_sheet` | 只传目标名称、顺序、可见性或冻结配置并回读 | `precise-write` | `recommended` |
| 删除工作表 | `delete_sheet` | 确认 sheetId、非空范围和恢复方式，删除后重新枚举目录 | `destructive` | `recommended` |
| 行追加与精确写值 | `append_rows`, `set_cell_range`, `update_range`, `table_put` | 二维范围对齐；2026-08-04 对象单元格 schema 两轮成功。检查外层状态、`structuredContent.success` 和独立读回；证明未写入后才可用 `update_range` 做同范围恢复 | `precise-write` | `recommended` |
| CSV 写入 | `set_range_from_csv` | 检查覆盖、单元格上限和合并区域 | `precise-write` / `destructive` | `recommended` |
| 批量原子写入 | `batch_update` | continueOnError=false 并读回证明回滚 | `precise-write` / `destructive` | `recommended` |
| 范围清理与变换 | `clear_range`, `copy_range`, `fill_range`, `move_range`, `sort_range` | 先读精确范围；移动同时验证源和目标 | `precise-write` / `destructive` | `recommended` |
| 全文替换 | `replace_all` | 2026-08-03 曾假成功；2026-08-04 两轮精确范围复测均成功。仍须双向查 marker 和独立回读，当前失败且目标已知时才用精确覆盖恢复 | `destructive` | `recommended` |
| 维度操作 | `add_dimension`, `delete_dimension`, `insert_dimension`, `move_dimension`, `update_dimension`, `group_dimension`, `ungroup_dimension` | 保存行列/分组现状；移动删除需确认 | `precise-write` / `destructive` | `recommended` |
| 合并单元格 | `merge_cells`, `unmerge_range` | 先确认区域值与公式 | `destructive` | `recommended` |
| 下拉与数据校验 | `set_dropdown_lists`, `delete_dropdown_lists` | 设置与删除分开授权，按范围回读 | `precise-write` / `destructive` | `recommended` |
| 普通筛选 | `create_filter`, `update_filter`, `clear_filter_criteria`, `sort_filter`, `delete_filter` | sort_filter 只确认可见行语义 | `precise-write` / `destructive` | `recommended` |
| 筛选条件直设 | `set_filter_criteria` | 2026-08-04 两轮连同各一次重试均为 `SERVICE_NOT_FOUND`；保存完整筛选现状后，同范围同条件的 `update_filter` 是两轮验证通过的回退路线 | `precise-write` | `observed-issue` |
| 筛选视图 | `create_filter_view`, `set_filter_view_criteria`, `update_filter_view`, `clear_filter_view_criteria`, `delete_filter_view` | 创建、更新、清除和删除均按 viewId 回读 | `precise-write` / `destructive` | `recommended` |
| 网格线 | `set_gridline_visibility` | 写响应成功但当时缺少状态读回；可探索当前读回方式 | `precise-write` | `not-yet-tested` |
| 条件格式 | `create_cond_format`, `update_cond_format`, `delete_cond_format` | 按 ruleId 创建、更新和删除后回读 | `precise-write` / `destructive` | `recommended` |
| 图片 | `create_float_image`, `update_float_image`, `delete_float_image`, `write_image` | 上传后用资源/对象 ID 回读 | `precise-write` / `destructive` | `recommended` |
| 浮动图表 | `create_float_chart`, `update_float_chart`, `delete_float_chart` | 完整配置更新并逐字段回读 | `precise-write` / `destructive` | `recommended` |
| 透视表 | `create_pivot_table`, `update_pivot_table`, `delete_pivot_table` | 同时验证对象配置、结果区域和目标 sheet 保留语义 | `precise-write` / `destructive` | `recommended` |

## 钉钉 AI 表格 MCP

| 能力 | 工具 | 推荐做法或历史观察 | 风险 | 证据 |
| --- | --- | --- | --- | --- |
| Base 发现与读取 | `list_bases`, `search_bases`, `get_base` | 取得 table/dashboard/document 目录 | `read` | `recommended` |
| 主键文档映射 | `get_base_primary_doc_id` | 2026-08-03 对同表全部 8 条查询可见记录仍返回 no record；不能代替记录存在性检查 | `read` | `observed-issue` |
| Table/field/view 读取 | `get_tables`, `get_fields`, `get_views`, `search_field_options` | 复杂写入前读取 schema、option 和 view 配置 | `read` | `recommended` |
| 记录与统计查询 | `query_records`, `query_records_stats`, `query_stats` | 显式 recordIds/fieldIds/limit/cursor | `read` | `recommended` |
| Chart 读取与分享状态 | `get_chart`, `get_chart_share`, `get_dashboard_config_example`, `get_dashboard_widgets_example` | 创建/更新后按稳定 ID 回读；分享 URL 始终脱敏 | `read` | `recommended` |
| Dashboard 读取与分享状态 | `get_dashboard`, `get_dashboard_share` | 目录与详情、子 chart 归属交叉核对；详情可能混入其他 Dashboard 的 chart，分享读取可能持续 404 | `read` | `observed-issue` |
| 模板与导出 | `search_templates`, `export_data` | 查找模板或导出数据 | `read` | `recommended` |
| Base 生命周期 | `create_base`, `copy_base`, `update_base`, `delete_base` | 名称/位置明确；删除不可逆 | `precise-write` / `irreversible` | `recommended` |
| Table 生命周期 | `create_table`, `update_table`, `delete_table` | 创建字段数遵守当前 schema；删除需确认 | `precise-write` / `destructive` | `recommended` |
| Field 生命周期 | `create_fields`, `update_field`, `delete_field` | 批量创建可能部分成功，重读 schema | `precise-write` / `destructive` | `recommended` |
| Record 生命周期 | `create_records`, `update_records`, `delete_records` | fieldId 写入，只更新指定字段；删除不可逆 | `precise-write` / `irreversible` | `recommended` |
| 附件上传 | `prepare_attachment_upload` | PUT 成功后写 fileToken，并有界重查 | `precise-write` | `recommended` |
| 数据导入 | `prepare_import_upload`, `import_data` | 小型唯一 marker 验证；覆盖模式需确认 | `precise-write` / `destructive` | `recommended` |
| View | `create_view`, `update_view`, `set_view_fill_color_rule`, `delete_view` | 按 viewId 回读；删除前确保不是最后视图 | `precise-write` / `destructive` | `recommended` |
| Chart 创建 | `create_chart`, `create_charts` | 2026-08-04 两轮均在创建后立即出现 `enabled=true`；创建按访问控制操作确认，随后立刻读取、按授权关闭并回读 | `access-control` | `observed-issue` |
| Chart 更新与删除 | `update_chart`, `delete_chart` | 写响应可能是旧快照，以 `get_chart` 为准；删除前确认目标和级联影响 | `precise-write` / `destructive` | `recommended` |
| 关闭 Chart 分享 | `update_chart_share` | 2026-08-04 两轮均写入 `enabled=false` 并独立回读最终关闭 | `access-control` | `recommended` |
| 开启 Chart 分享 | `update_chart_share` | PUBLIC/ORG 模式在用户授权后按当前 schema 探索并回读范围 | `access-control` | `not-yet-tested` |
| Dashboard | `create_dashboard`, `update_dashboard`, `delete_dashboard` | 完整配置更新；空 Dashboard 可能读到其他 Dashboard 的 chart，修改/删除前必须以 Base 目录和子资源归属交叉核对 | `precise-write` / `destructive` | `observed-issue` |
| 关闭 Dashboard 分享 | `update_dashboard_share` | 写响应不是最终证据；2026-08-04 一轮经有界重试读到关闭，另一轮持续 404，无法回读时返回 `ACCESS_STATE_UNVERIFIED` | `access-control` | `observed-issue` |
| 开启 Dashboard 分享 | `update_dashboard_share` | PUBLIC/ORG 模式在用户授权后按当前 schema 探索并回读范围 | `access-control` | `not-yet-tested` |
| Guide Document 创建与更新 | `create_guide_document`, `update_guide_document` | 用 Base 目录回读 | `precise-write` | `recommended` |
| Guide Document 删除 | `delete_guide_document` | 双重回读；2026-08-03 仍出现 API 已删除但文档可读/目录残留。若用户已授权清理精确测试文档，可用通用 `delete_document` 移入回收站，仍把目录残留报告为 `partial` | `destructive` | `observed-issue` |
| Workflow | `create_workflow`, `update_workflow`, `edit_workflow_example` | 会发布；缺少独立 list/get/delete/disable，授权后可尝试并按读回缺口报告 | `external-impact` | `not-yet-tested` |
| AI 与数据源执行 | `run_ai_field`, `run_datasource_sync` | 用户明确目标、记录范围、成本和外部影响后做最小运行 | `external-impact` | `not-yet-tested` |

## 推荐路线与历史观察

本节记录可复用的推荐路线和有复测价值的历史观察。历史租户结果不是未来会话保证，也不构成工具禁令。

| 类型 | 能力 | 写入工具 | 读回工具 | 状态 | 环境与结论 |
| --- | --- | --- | --- | --- | --- |
| `adoc` | 创建、初始 Markdown、追加、精确 block 更新 | `create_document`, `update_document(mode=append)`, `update_document_block` | `get_document_info`, `get_document_content`, `list_document_blocks` | `recommended` | 2026-07-31，当前调用者“我的文档”；元信息确认为 `ALIDOC/adoc`，追加不影响原内容，目标 paragraph 更新后 Markdown 回读一致 |
| `adoc` | 手动版本保存 | `save_doc_version` | 工具返回的版本号 | `recommended` | 成功创建 `USER_SAVE` 恢复点；版本回滚已在下一行的覆盖/回滚组合路径中完成实测 |
| `adoc` | 全文覆盖与版本回滚 | `update_document(mode=overwrite)`, `revert_doc_version` | `get_document_content`, `list_document_blocks`, `get_document_style` | `recommended` | 覆盖前保存新版本；首次覆盖超时且回读证明未生效，单次安全重试成功；回滚后正文、附件、原生图片、封面和背景均恢复 |
| `adoc` | 精确 block 删除 | `insert_document_block`, `delete_document_block` | `list_document_blocks` | `recommended` | 只删除本轮新插入且按唯一 marker 重新定位的一级 paragraph；删除后 marker 不再存在 |
| `adoc` | 文本附件上传与附件 block | `get_doc_attachment_upload_info`, HTTP PUT, `insert_document_block` | `list_document_blocks` | `recommended` | PUT 返回 200；附件 block 回读包含夹具名称与稳定 resourceId。当前 MCP 只有最小附件字段 `name + resourceId` 成功；显式 `size/viewType` 分别触发数值序列化和枚举错误 |
| `adoc` | 图片上传、封面和原生正文图片 | `get_doc_attachment_upload_info`, HTTP PUT, `update_document_style`, `update_document(mode=append)` | `get_document_style`, `get_document_content(format=jsonml)` | `recommended` | 上传图片可设为封面并回读；把上传后的内部资源 URL 作为 Markdown 图片追加后，JsonML 回读存在原生 `img` 节点 |
| `axls` | 创建、发现、范围值/公式/样式、精确单元格写入、追加行 | `create_workspace_sheet`, `update_range`, `set_cell_range`, `append_rows` | `get_all_sheets`, `get_range`, `get_cell_infos` | `recommended` | 2026-07-31 已验证完整范围；2026-08-04 两轮独立隔离资产再次证明 `set_cell_range` 接受对象单元格 schema，业务状态成功且 A1:B3 回读一致 |
| `axls` | 数据校验与公式检查 | `set_dropdown_lists` | `get_dropdown_lists`, `verify_formula` | `recommended` | 下拉选项与颜色回读一致；扫描 12 个单元格、2 个公式，错误数为 0 |
| `axls` | 精确范围清空 | `clear_range(type=all)` | `get_cell_infos` | `recommended` | 先在隔离范围 `Z1:Z2` 写入唯一 marker；清空后值与格式均为空，其他范围不在调用目标中 |
| `axls` | 工作表删除 | `create_sheet`, `delete_sheet` | `get_all_sheets` | `recommended` | 只删除本轮新建并按 sheetId 确认的 delete-only sheet；删除后目录不再包含该 sheetId |
| `axls` | 严格批处理失败回滚 | `batch_update(continueOnError=false)` | `get_cell_infos` | `recommended` | 第一个操作写 `AA1`，第二个操作使用不存在的 sheetId 故意失败；返回明确说明已回滚，`AA1` 回读仍为空 |
| `axls` | 单元格图片上传 | `get_doc_attachment_upload_info`, HTTP PUT, `write_image` | `get_cell_infos` | `recommended` | 文档上传准备工具对 `axls` 可用；图片回读为 richText image，尺寸与 resourceId 一致 |
| `axls` | 浮动图片创建与精确更新 | `create_float_image`, `update_float_image` | `list_float_images`, `get_float_image` | `recommended` | 创建后可读取稳定图片对象 ID；宽高和偏移更新后回读一致；另建的删除专用图片已完成删除验证 |
| `axls` | 条件格式创建与更新 | `create_cond_format`, `update_cond_format` | `get_cond_format` | `recommended` | 对隔离范围使用公式规则；更新样式后按 ruleId 回读一致；删除专用规则也已完成删除验证 |
| `axls` | 浮动图表创建与更新 | `create_float_chart`, `update_float_chart` | `list_float_charts` | `recommended` | series 名称必须使用单元格引用；column→line、标题、尺寸和偏移回读成功，但请求把 legend 改为 top 后回读仍为 bottom，因此每个字段都必须逐项核对 |
| `axls` | 透视表创建与更新 | `create_pivot_table`, `update_pivot_table` | `list_pivot_tables`, `get_range` | `recommended` | 从隔离数据源创建后服务端自动新增目标 sheet；字段配置、小计/总计开关和透视结果公式/汇总值均已回读；删除透视对象后目标 sheet 保留 |
| `axls` | 筛选、筛选视图与精确删除 | `clear_filter_criteria`, `clear_filter_view_criteria`, `delete_filter`, `delete_filter_view` | `get_filter`, `get_filter_views` | `recommended` | 清除指定列条件后其他条件保留；删除后筛选 criteria 为空、筛选视图列表为空 |
| `axls` | 排序、移动与删空白行 | `sort_filter`, `sort_range`, `move_range`, `delete_dimension` | `get_cell_infos`, `get_sheet` | `recommended` | `sort_range` 完整降序且表头保留；`move_range` 目标获得值且源清空；删除两行后 rowCount 减 2。`sort_filter` 只确认当前可见行排序，隐藏行保持原位 |
| `axls` | 高级对象精确删除 | `delete_cond_format`, `delete_dropdown_lists`, `delete_float_chart`, `delete_float_image`, `delete_pivot_table` | 对应 `get_*` / `list_*` | `recommended` | 五类对象均在隔离目标删除后回读为 0/不存在；透视目标 sheet 仍保留 |
| `axls` | 全文替换 | `replace_all`; 必要时恢复用 `set_range_from_csv` | `get_cell_infos`, `find_cells` | `recommended` | 2026-08-03 曾两次返回计数但旧值仍在；2026-08-04 两轮独立精确范围复测均返回 `replaceCount=1`，且只把目标 `OLD` 改为 `NEW`、保留 `KEEP`。仍强制写前标记与写后回读 |
| `able` | 创建 Base、table 和代表性字段 | `create_base`, `create_table`, `create_fields` | `get_base`, `get_tables`, `get_fields` | `recommended` | 2026-07-31，当前调用者“我的文档”；11 个初始字段和 6 个补充字段均成功，字段目录与完整配置回读一致 |
| `able` | 多类型记录创建、精确更新、按 ID/筛选/关键词查询 | `create_records`, `update_records` | `query_records` | `recommended` | 文本、数字、货币、单选、多选、日期、复选框、URL、富文本、邮箱、电话、评分、进度、位置和条码写入可回读；只更新已传字段，筛选与关键词查询命中预期记录 |
| `able` | 文本附件与图片附件直传 | `prepare_attachment_upload`, HTTP PUT, `create_records`, `update_records` | `query_records` | `recommended` | 两种 MIME 的 PUT 均返回 200；文本附件与图片附件均回读到文件名、大小、类型和 resourceId；首轮立即查询曾暂时为空，随后有界重查成功 |
| `able` | 记录删除 | `create_records`, `delete_records` | `query_records` | `recommended` | 只删除本轮创建返回的 recordId；删除计数为 1，后续按 ID 查询为空。创建后的首次立即查询存在短暂可见性延迟 |
| `able` | 字段删除 | `create_fields`, `delete_field` | `get_tables` | `recommended` | 新建 delete-only 文本字段，删除前按 fieldId 确认存在，删除后字段目录不再包含该 fieldId |
| `able` | Table 删除 | `create_table`, `delete_table` | `get_base` | `recommended` | 新建 delete-only table，删除前按 tableId 确认存在，删除后 Base 目录不再包含该 tableId |
| `adoc/axls` | 整个资产移入回收站 | `create_document` / `create_workspace_sheet`, `delete_document` | `get_document_info` | `recommended` | 分别创建 delete-only 资产；删除后读取返回 recycled/notFound；工具声明 30 天内可从回收站恢复 |
| `able` | Base 删除 | `create_base`, `delete_base` | `get_base` | `recommended` | 使用不超过 50 字符的 delete-only Base 名；删除后读取返回 Base 不存在或不可访问。超长名称的创建请求被拒绝且未产生资产 |
| `able` | 公式字段配置 | `create_table` | `get_fields` | `recommended` | 公式字符串 `[单价] * [数量]` 的字段配置回读一致 |
| `able` | 公式计算值读取 | `create_records`, `update_records` | `query_records(fieldIds=...)`, `query_records_stats`, `query_stats` | `observed-issue` | 2026-08-03 重新显式请求公式 fieldId、同值更新依赖字段触发重算，并尝试两种统计读取，仍没有公式值；按部分结果处理，不用客户端计算冒充钉钉结果 |
| `able` | View 创建与更新 | `create_view`, `update_view` | `get_views` | `recommended` | Grid 视图名称、字段宽度和金额 SUM 聚合配置均按 viewId 回读一致；额外删除专用视图已完成删除验证 |
| `able` | 仪表盘创建与更新 | `create_dashboard`, `update_dashboard` | `get_base`, `get_dashboard`, `get_chart` | `observed-issue` | 完整配置更新可持久化；但 2026-08-04 两轮中，Base 目录均显示空 Dashboard 的 chartCount=0，而详情持续混入另一个 Dashboard 的 chart。修改前必须核对子资源 dashboardId，冲突时停止 |
| `able` | 图表创建 | `create_chart`, `create_charts` | `get_chart`, `get_chart_share` | `observed-issue` | 2026-08-04 两轮均在创建后立即读到分享 `enabled=true`。创建必须按访问控制操作预览并确认，随后立即检查；用户未授权分享时关闭并回读 |
| `able` | 图表更新 | `update_chart` | `get_chart` | `recommended` | BAR 图更新响应曾带旧配置，但随后按 chartId 读取出现新名称、配色、排序、图例和布局，不能以更新响应代替读回 |
| `able` | 关闭图表分享 | `update_chart_share(enabled=false)` | `get_chart_share` | `recommended` | 2026-08-04 两轮均在发现隐式分享后立即关闭，独立回读最终均为 `enabled=false`；不得输出返回的分享 URL |
| `able` | 关闭仪表盘分享 | `update_dashboard_share(enabled=false)` | `get_dashboard_share` | `observed-issue` | 2026-08-04 一轮经有界重试最终两次读到 `enabled=false`，另一轮在关闭响应成功后仍持续 404。最多两次只读重试，仍不确定则 `partial` |
| `able` | 图表、空仪表盘与额外视图删除 | `delete_chart`, `delete_dashboard`, `delete_view` | `get_base`, `get_dashboard`, `get_chart`, `get_views` | `recommended` | 既有隔离删除证据仍有效；执行新删除前必须先通过 Base 目录和子 chart 的 dashboardId 排除详情串数据，无法唯一确认时不得删除 |
| `able` | 说明文档删除 | `delete_guide_document`; 物理清理可回退 `delete_document` | `get_base`, `get_document_info` | `observed-issue` | 2026-08-03 新建精确测试文档后删除：专用工具首次 success，重试称 not found，但文档仍可读且目录残留；通用删除可将该文档移入回收站，文档读取随后为 recycled，Base 目录仍残留，整体只算 `partial` |

### 2026-08-03 历史异常重新验证

- 本轮只使用当前调用者私有的既有验证资产、新建隔离 sheet 和新建后精确删除的说明文档；没有分享、通知、权限或协作者变更。
- 表格导出旧问题已修复：当前 schema 明确支持 axls→xlsx，提交返回真实 jobId，查询返回完成状态；临时下载地址未记录。
- `set_filter_criteria` 仍因下游服务不存在失败；使用相同筛选范围和条件调用 `update_filter` 后，`get_filter` 回读列条件一致，因此任务级恢复路线可用。
- `replace_all` 两次均报告替换 1 格，但独立读取仍是旧 marker；精确 `set_range_from_csv` 覆盖同一单格后读回新 marker，证明恢复路线可用，但不能把原工具写响应当成功。
- `get_base_primary_doc_id` 已对目标表全部 8 条查询可见记录重试，均返回 no record；记录存在性仍由 `query_records` 判断。
- AI 表公式值在显式 fieldId、依赖字段同值更新、记录查询与两类统计查询后仍缺失；配置本身可读取，结果保持部分验证。
- `delete_guide_document` 的 API 状态、文档物理状态和 Base 目录不一致；通用文档删除能让精确测试文档进入回收站，但 Base 目录仍有陈旧条目，因此只形成有边界的当前观察。

### 2026-08-04 推广阻塞项双轮复测

- 两轮分别使用独立的新建 axls 和 able 验证资产；资产名称、位置、用途和后续清理方式已先取得授权。本次结论不包含清理授权，四个顶层资产仍保留。
- `set_cell_range` 两轮均按当前对象单元格 schema 成功，业务层 `structuredContent.success=true`，随后 A1:B3 独立回读一致；2026-08-03 的 primitive 形状冲突不再代表当前稳定状态。
- `set_filter_criteria` 两轮连同各一次有证据重试均返回 `SERVICE_NOT_FOUND`，筛选条件仍为空；同范围同条件的 `update_filter` 两轮均成功并回读一致，形成当前稳定回退路线。
- `replace_all` 两轮均在精确范围内返回替换 1 格并由独立读取证明新值出现、保留值不变；历史假成功仍作为回读必要性的证据，不再把工具永久标为当前异常。
- `create_chart` 两轮均在创建后立即读到分享开启；两轮都随即关闭并独立回读为 `enabled=false`。因此 Chart 创建本身按 `access-control` 处理，不能等同普通精确写入。
- Dashboard 分享关闭后的可见性不稳定：一轮经有界重试读到 `enabled=false`，另一轮在两次重试后仍为 404。写响应不能证明最终关闭，未读到最终状态时返回 `ACCESS_STATE_UNVERIFIED`。
- 两轮中，Base 目录均显示空 Dashboard 的 chartCount=0，但 `get_dashboard` 持续返回另一个 Dashboard 的 chart，且子资源 dashboardId 指向外部目标。发现该冲突时不得更新或删除，并返回 `RESOURCE_STATE_INCONSISTENT`。
- 静态触发评估显示，原“普通文件、图片和附件”描述可能误匹配本地 PNG/CSV；触发描述已收窄为钉钉空间与钉钉内容。运行时匹配器不可用，因此仍需在推广观察中收集真实触发样本。
- `create_base` 对超出当前 50 字符上限的验证名称干净返回 `NAME_TOO_LONG` 且未创建资产；后续 able 夹具使用 `-a1`、`-a2` 紧凑后缀。

## 覆盖摘要

- 2026-07-31 的全量运行覆盖当时 170 个工具：89 个完成新增真实调用，4 个只能部分验证，5 个失败，1 个依赖阻断，6 个因协作者、所有权、计费或外部数据影响而安全停止；其余已有前序证据。
- `create_workflow` / `update_workflow` 缺少独立回读、停用和删除，`set_gridline_visibility` 缺少状态读回，`sort_filter` 只确认筛选可见行语义。
- Chart 分享关闭已有两轮独立读回，Dashboard 分享关闭仍可能无法读取最终状态；开启 PUBLIC/ORG 是独立的 `not-yet-tested` 能力。
- 空 Dashboard 详情在两轮中稳定混入其他 Dashboard 的 charts；删除或更新前必须用 Base 目录的稳定 ID、名称、chartCount 和子资源 dashboardId 交叉核对。

## 2026-08-03 精确工具清单

以下完整名仅用于把当日 schema 与能力记录做一一映射；后续会话应重新盘点，不能用本快照否定新工具。

### 文档工具（40）

```text
mcp__dingtalk__add_permission
mcp__dingtalk__apply_doc_template
mcp__dingtalk__commit_uploaded_file
mcp__dingtalk__confirm_import
mcp__dingtalk__copy_document
mcp__dingtalk__create_document
mcp__dingtalk__create_file
mcp__dingtalk__create_folder
mcp__dingtalk__create_import_session
mcp__dingtalk__delete_document
mcp__dingtalk__delete_document_block
mcp__dingtalk__download_doc_attachment
mcp__dingtalk__download_file
mcp__dingtalk__get_doc_attachment_upload_info
mcp__dingtalk__get_document_content
mcp__dingtalk__get_document_info
mcp__dingtalk__get_document_style
mcp__dingtalk__get_file_upload_info
mcp__dingtalk__get_recent_list
mcp__dingtalk__insert_document_block
mcp__dingtalk__list_doc_templates
mcp__dingtalk__list_doc_versions
mcp__dingtalk__list_document_blocks
mcp__dingtalk__list_nodes
mcp__dingtalk__list_permission
mcp__dingtalk__move_document
mcp__dingtalk__query_export_job
mcp__dingtalk__query_import_task
mcp__dingtalk__remove_permission
mcp__dingtalk__rename_document
mcp__dingtalk__revert_doc_version
mcp__dingtalk__save_doc_version
mcp__dingtalk__search_doc_templates
mcp__dingtalk__search_documents
mcp__dingtalk__submit_export_job
mcp__dingtalk__transfer_owner
mcp__dingtalk__update_document
mcp__dingtalk__update_document_block
mcp__dingtalk__update_document_style
mcp__dingtalk__update_permission
```

### 表格工具（74）

```text
mcp__dingtalk_sheet__add_dimension
mcp__dingtalk_sheet__append_rows
mcp__dingtalk_sheet__apply_sheet_template
mcp__dingtalk_sheet__batch_update
mcp__dingtalk_sheet__clear_filter_criteria
mcp__dingtalk_sheet__clear_filter_view_criteria
mcp__dingtalk_sheet__clear_range
mcp__dingtalk_sheet__copy_range
mcp__dingtalk_sheet__copy_sheet
mcp__dingtalk_sheet__create_cond_format
mcp__dingtalk_sheet__create_filter
mcp__dingtalk_sheet__create_filter_view
mcp__dingtalk_sheet__create_float_chart
mcp__dingtalk_sheet__create_float_image
mcp__dingtalk_sheet__create_pivot_table
mcp__dingtalk_sheet__create_sheet
mcp__dingtalk_sheet__create_workspace_sheet
mcp__dingtalk_sheet__delete_cond_format
mcp__dingtalk_sheet__delete_dimension
mcp__dingtalk_sheet__delete_dropdown_lists
mcp__dingtalk_sheet__delete_filter
mcp__dingtalk_sheet__delete_filter_view
mcp__dingtalk_sheet__delete_float_chart
mcp__dingtalk_sheet__delete_float_image
mcp__dingtalk_sheet__delete_pivot_table
mcp__dingtalk_sheet__delete_sheet
mcp__dingtalk_sheet__fill_range
mcp__dingtalk_sheet__find_cells
mcp__dingtalk_sheet__get_all_sheets
mcp__dingtalk_sheet__get_cell_infos
mcp__dingtalk_sheet__get_cond_format
mcp__dingtalk_sheet__get_dropdown_lists
mcp__dingtalk_sheet__get_filter
mcp__dingtalk_sheet__get_filter_views
mcp__dingtalk_sheet__get_float_image
mcp__dingtalk_sheet__get_range
mcp__dingtalk_sheet__get_range_as_csv
mcp__dingtalk_sheet__get_sheet
mcp__dingtalk_sheet__group_dimension
mcp__dingtalk_sheet__insert_dimension
mcp__dingtalk_sheet__list_float_charts
mcp__dingtalk_sheet__list_float_images
mcp__dingtalk_sheet__list_pivot_tables
mcp__dingtalk_sheet__list_sheet_templates
mcp__dingtalk_sheet__merge_cells
mcp__dingtalk_sheet__move_dimension
mcp__dingtalk_sheet__move_range
mcp__dingtalk_sheet__query_export_job
mcp__dingtalk_sheet__replace_all
mcp__dingtalk_sheet__search_sheet_templates
mcp__dingtalk_sheet__set_cell_range
mcp__dingtalk_sheet__set_dropdown_lists
mcp__dingtalk_sheet__set_filter_criteria
mcp__dingtalk_sheet__set_filter_view_criteria
mcp__dingtalk_sheet__set_gridline_visibility
mcp__dingtalk_sheet__set_range_from_csv
mcp__dingtalk_sheet__sort_filter
mcp__dingtalk_sheet__sort_range
mcp__dingtalk_sheet__submit_export_job
mcp__dingtalk_sheet__table_get
mcp__dingtalk_sheet__table_put
mcp__dingtalk_sheet__ungroup_dimension
mcp__dingtalk_sheet__unmerge_range
mcp__dingtalk_sheet__update_cond_format
mcp__dingtalk_sheet__update_dimension
mcp__dingtalk_sheet__update_filter
mcp__dingtalk_sheet__update_filter_view
mcp__dingtalk_sheet__update_float_chart
mcp__dingtalk_sheet__update_float_image
mcp__dingtalk_sheet__update_pivot_table
mcp__dingtalk_sheet__update_range
mcp__dingtalk_sheet__update_sheet
mcp__dingtalk_sheet__verify_formula
mcp__dingtalk_sheet__write_image
```

### AI 表格工具（56）

```text
mcp__dingtalk_ai_table__copy_base
mcp__dingtalk_ai_table__create_base
mcp__dingtalk_ai_table__create_chart
mcp__dingtalk_ai_table__create_charts
mcp__dingtalk_ai_table__create_dashboard
mcp__dingtalk_ai_table__create_fields
mcp__dingtalk_ai_table__create_guide_document
mcp__dingtalk_ai_table__create_records
mcp__dingtalk_ai_table__create_table
mcp__dingtalk_ai_table__create_view
mcp__dingtalk_ai_table__create_workflow
mcp__dingtalk_ai_table__delete_base
mcp__dingtalk_ai_table__delete_chart
mcp__dingtalk_ai_table__delete_dashboard
mcp__dingtalk_ai_table__delete_field
mcp__dingtalk_ai_table__delete_guide_document
mcp__dingtalk_ai_table__delete_records
mcp__dingtalk_ai_table__delete_table
mcp__dingtalk_ai_table__delete_view
mcp__dingtalk_ai_table__edit_workflow_example
mcp__dingtalk_ai_table__export_data
mcp__dingtalk_ai_table__get_base
mcp__dingtalk_ai_table__get_base_primary_doc_id
mcp__dingtalk_ai_table__get_chart
mcp__dingtalk_ai_table__get_chart_share
mcp__dingtalk_ai_table__get_dashboard
mcp__dingtalk_ai_table__get_dashboard_config_example
mcp__dingtalk_ai_table__get_dashboard_share
mcp__dingtalk_ai_table__get_dashboard_widgets_example
mcp__dingtalk_ai_table__get_fields
mcp__dingtalk_ai_table__get_tables
mcp__dingtalk_ai_table__get_views
mcp__dingtalk_ai_table__import_data
mcp__dingtalk_ai_table__list_bases
mcp__dingtalk_ai_table__prepare_attachment_upload
mcp__dingtalk_ai_table__prepare_import_upload
mcp__dingtalk_ai_table__query_records
mcp__dingtalk_ai_table__query_records_stats
mcp__dingtalk_ai_table__query_stats
mcp__dingtalk_ai_table__run_ai_field
mcp__dingtalk_ai_table__run_datasource_sync
mcp__dingtalk_ai_table__search_bases
mcp__dingtalk_ai_table__search_field_options
mcp__dingtalk_ai_table__search_templates
mcp__dingtalk_ai_table__set_view_fill_color_rule
mcp__dingtalk_ai_table__update_base
mcp__dingtalk_ai_table__update_chart
mcp__dingtalk_ai_table__update_chart_share
mcp__dingtalk_ai_table__update_dashboard
mcp__dingtalk_ai_table__update_dashboard_share
mcp__dingtalk_ai_table__update_field
mcp__dingtalk_ai_table__update_guide_document
mcp__dingtalk_ai_table__update_records
mcp__dingtalk_ai_table__update_table
mcp__dingtalk_ai_table__update_view
mcp__dingtalk_ai_table__update_workflow
```


## 维护规则

- 当前会话出现新工具：加入目录并标 `not-yet-tested`；允许按最小探索协议使用，不等待历史评审放行。
- 工具或 schema 改变：只使相关历史配方失效，重新阅读当前 schema 并做最小复测。
- 历史异常：不能直接刷新为当前 `observed-issue`。每次相关任务都先按当前 schema 复测并尝试安全恢复；只有再次复现且恢复路径耗尽，才记录日期、环境、参数、读回证据和边界明确的新观察。
- 权限失败：记录为当前主体和目标的结果，不推断其他租户或资源。
- 上传、异步、公式或渲染无法充分读回：该次操作最高为 `partial`，但不限制以后继续验证。
- 能力矩阵是建议和证据，不是白名单；用户授权与安全协议始终独立判断。
- 不记录私有 MCP URL、临时 OSS URL、Cookie、Token、headers 或个人标识。
