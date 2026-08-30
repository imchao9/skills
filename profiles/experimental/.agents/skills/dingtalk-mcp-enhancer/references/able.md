# 钉钉 AI 表格 able 配方

## 读取与 schema

1. 文档 URL/nodeId 用 `get_document_info` 确认 `ALIDOC/able`；明确 baseId 直接用 `get_base`，tableId/recordId 不交给文档元信息工具。
2. `get_base` 读取 table、dashboard 和 document 目录；`get_tables`、`get_fields`、`get_views` 展开 schema。
3. 默认每个 table 前 100 条记录，显式控制 fieldIds、limit、cursor，并报告未覆盖页。

## Base、Table、Field 和 Record

- 无链接新建使用 `create_base`，随后读 `get_base`；不要要求用户先建空 Base。
- 创建 table/field 遵守当前 schema 数量限制；批量字段可能部分成功，解析逐项结果并重读目录，只处理明确失败项。
- 记录 cell key 使用 fieldId，并按字段 type 校验值形状。更新只发送指定 recordId 和用户要求的字段。
- 选择字段使用名称或经 `get_fields` 验证的 option 对象。
- 已知记录优先按 recordIds 查询；附件用 `prepare_attachment_upload` → 安全 PUT → fileToken 写入字段，并按同一 recordId/fieldId 有界重查。
- 删除 record/field/table/Base 前按稳定 ID 重读，展示影响并确认；删除后从对应目录或查询证明消失。

## 导入、View、Dashboard 和 Chart

- 导入：带唯一 marker 的小 CSV → `prepare_import_upload` → 安全 PUT → `import_data`；用字段目录和记录查询验证结果。
- View：按 viewId 回读名称、列、宽度、聚合、筛选和颜色规则。
- Dashboard：更新前读并携带完整配置，写后 `get_dashboard`；只传名称曾返回成功但未持久化。
- `get_dashboard` 可能混入其他 Dashboard 的 chart。先用 Base 目录的稳定 ID、名称和 chartCount 确认目标，再用 `get_chart` 核对每个 chart 自身的 dashboardId。空 Dashboard 出现外来 chart 时忽略这些条目，不得据此更新或删除；返回 `partial` 和 `RESOURCE_STATE_INCONSISTENT`。
- Chart：更新后用 `get_chart`；历史 `update_chart` 响应曾是旧快照。
- `create_chart` / `create_charts` 创建前先读取配置示例，预览“可能短暂启用分享”的当前副作用并确认。创建后立即 `get_chart_share`；用户未要求分享且 `enabled=true` 时立刻 `update_chart_share(enabled=false)`，再独立回读。关闭或回读失败时返回 `partial`，不得宣称私有，也不得输出分享 URL。
- Dashboard 分享关闭响应不是最终证据。`get_dashboard_share` 可能短暂返回 404；最多做两次有界只读重试，仍不能读到 `enabled=false` 时返回 `partial` 和 `ACCESS_STATE_UNVERIFIED`。
- 开启 Chart 或 Dashboard 的 PUBLIC/ORG 分享仍需明确授权并独立回读最终范围。

## 已验证缺口与恢复

- 公式字段配置可回读，但 2026-08-03 显式公式 fieldId、依赖字段同值更新、`query_records_stats` 和 `query_stats` 均未返回计算值。当前任务先重试；仍缺值则 `partial`，不以客户端计算冒充钉钉结果。
- `get_base_primary_doc_id` 曾对同表 8 条可见记录均返回 no record。它不是记录存在性检查；记录以 `query_records` 为准。
- `delete_guide_document` 曾出现 API 已删除、文档仍可读、Base 目录残留的状态分裂。必须同时回读 `get_base` 和 `get_document_info`；用户明确授权精确清理时可用 `delete_document` 移入回收站，但目录仍残留则只算 `partial`。

## Workflow、AI 和数据源

- `create_workflow` 会发布流程；当前历史环境缺少独立 list/get/delete/disable。执行前预览 trigger/action、触发范围、通知、数据改写和清理路径并确认。
- 未验证能力不是禁令；用户授权后可按当前 schema 最小尝试。缺少独立读回、停用或删除证据时如实返回 `partial`。
- `run_ai_field`、`run_datasource_sync` 只在用户明确指定 Base/table/field/records、成本和外部影响后运行最小记录集并回读结果。
