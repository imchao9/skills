# 钉钉表格 axls 配方

## 读取

1. `get_document_info` 确认 `ALIDOC/axls`，再用 `get_all_sheets` 取得稳定 sheetId。
2. 默认每个 sheet 读取前 100 行，并报告实际列范围、公式、合并和 gaps；用户指定范围时只读该范围。
3. 优先 `get_range` / `get_range_as_csv`，需要富文本、图片、样式或精确单元格证据时用 `get_cell_infos`。

## 精确范围写入

1. 写前读取目标 A1 范围及值、公式、合并、校验和样式。
2. 普通值、公式和富文本使用当前 schema 推荐的精确范围工具；`set_cell_range` 的二维 cells 必须与范围完全对齐。2026-08-04 两次隔离实测均成功接受形如 `{type: "text", text: "..."}` 的对象单元格。
3. 同时检查工具调用外层状态和业务层 `structuredContent.success`，再独立回读；响应文本或无异常退出都不能单独证明写入成功。历史 primitive 形状冲突只作排障线索，当前 schema 优先。
4. 追加行使用唯一业务键；响应不明确时先搜索键，不盲目追加。
5. 写后分别回读 values、displayValues、formulas 和 styles；公式范围再用 `verify_formula`。

## CSV、批处理和维度

- `set_range_from_csv` 遵守 RFC 4180；覆盖前确认范围、单元格数和合并区域影响。
- `batch_update(continueOnError=false)` 才能作为严格事务；失败后仍读回首项范围证明回滚。
- 插入、移动、删除或分组行列前读取行列数量和非空范围。`move_range` 同时验证源为空、目标一致。
- `sort_range` 要求精确矩形、sortKeys 和 hasHeader；`sort_filter` 可能只排序当前可见行。

## 下拉、筛选、图片与高级对象

- 下拉：读 `get_dropdown_lists`，写后核对选项、颜色和多选设置。
- 筛选：读 `get_filter` / `get_filter_views`，更新后证明未请求条件仍保留。
- 条件格式按 ruleId 回读；删除后证明规则不存在。
- 单元格图片：安全准备上传 → PUT → `write_image` → `get_cell_infos` 验证 richText image。
- 浮动图片/图表按对象 ID 回读；图表更新使用完整配置并逐字段核对。
- 透视表同时验证对象配置、结果区域和服务端可能新增的目标 sheet；删除透视对象不等于删除 sheet。

## 当前恢复路线

- `set_cell_range` 在 2026-08-04 两轮均按当前对象 schema 成功并由 `get_cell_infos` 回读。若当前业务状态失败或读回证明未写入，只允许一次隔离最小重试，或在同一精确范围改用 `update_range`；读回无法判断时停止。
- `set_filter_criteria` 在 2026-08-04 两轮中连同各一次有证据重试均返回 `SERVICE_NOT_FOUND`，且 `get_filter` 证明条件为空；同范围同条件的 `update_filter` 两轮均成功并由 `get_filter` 回读。当前优先把它作为已验证回退路线。
- `replace_all` 在 2026-08-03 曾两次假成功，但 2026-08-04 两次独立精确范围复测均成功，`replaceCount=1` 且读回证明只替换目标值。当前可按 schema 使用，但始终保存替换前 marker 并回读新旧值；只有当前失败且目标位置完全已知时，才用 `set_range_from_csv` 或精确写入恢复。
- 表格导出路线已在 2026-08-03 恢复：`submit_export_job` 生成 axls→xlsx jobId，`query_export_job` 可读完成状态；仍须按当前 schema 有界查询并脱敏下载凭证。
- `set_gridline_visibility` 曾缺少状态读回；若当前仍无独立读取证据，结果只能是 `partial`。
