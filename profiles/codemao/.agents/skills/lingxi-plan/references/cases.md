# 灵犀·需求方案推广版行为示例

本文件只提供示例和预期行为，不新增 `SKILL.md` 之外的隐藏门禁。用户可见内容优先中文；机器交接字段必要时保留英文。

机器字段中文含义：
- `source_type`: 来源类型。
- `dingtalk_resolution`: 钉钉解析方式。
- `fetch_status`: 来源读取状态。
- `requirements_stage_gate`: 需求收集门禁。
- `technical_plan_status`: 技术方案状态。
- `source_completeness`: 来源完整性。
- `source_gaps`: 来源缺口清单。
- `blocking_source_gaps`: 阻塞实现的来源缺口。
- `source_gap_approval`: 来源缺口是否已获授权。

通用资料清单：
- `图片资料清单`: 图片来源、下载/校验状态和缺口。
- `附件资料清单`: 附件来源、下载/解析状态和缺口。
- `引用资料清单`: 钉钉引用文档、TAPD 链接或其他需求来源链接的上下文、读取状态和影响判断。

## 推广样例：钉钉需求

用户话术：

```text
使用 $lingxi-plan 读取这个钉钉需求：https://docs.dingtalk.com/i/nodes/<nodeId>，项目在 /path/to/project
```

期望流程：
- 先调用钉钉元信息，再按文档类型读取正文、表格、AI 表、文件、图片和附件。
- 图片和附件默认做基础登记；非关键资源未校验时标注“未校验，不作为需求依据”。
- 表格/AI 表专用工具缺失时，记录缺口并提示接入专用 MCP，不能用通用导出伪装完整读取。
- 生成 `需求清单`，用中文复述需求理解。
- 未识别复杂逻辑信号时，不询问复杂逻辑选择，技术方案记录按简单需求处理。
- 按 `implementation_surface` 生成后端技术方案、前端技术方案或两者；每份方案第一节引用原始钉钉链接、钉钉标题或节点信息。

## 推广样例：本地方案

用户话术：

```text
使用 $lingxi-plan 读取本地方案：docs/features/foo_需求清单.md，项目在 /path/to/project，生成技术方案
```

期望流程：
- 读取用户提供的本地文件，不盲目搜索仓库。
- 将本地方案作为需求/设计证据，不等同于实现授权。
- 生成或刷新 `需求清单`，完成必要确认后按 `implementation_surface` 生成涉及端的技术方案。
- 每份技术方案第一节引用本地方案、需求清单和需求收集单路径。

## 推广样例：混合来源

用户话术：

```text
使用 $lingxi-plan 对比钉钉 https://docs.dingtalk.com/i/nodes/<nodeId> 和本地 docs/features/foo_技术方案.md，冲突先问我
```

期望流程：
- 用户说“对比”“两边都读”“冲突先问我”时，视为 `source_choice=mixed`。
- 同时保留钉钉和本地证据引用。
- 事实冲突写入 `待确认事项`；高影响冲突未确认前不输出完成态技术方案。
- 每份技术方案第一节同时引用钉钉链接和本地整理文档，并记录主依据、补充依据和冲突处理结论。

## 来源读取示例

## 示例 1：钉钉链接读取成功（通过）

输入：
- 提供 `doc_url`，且可通过钉钉 MCP 读取。

期望：
- `source_type=dingtalk`
- `dingtalk_resolution=url`
- `fetch_status=success`
- 继续抽取需求并生成 `需求清单`。

## 示例 2：URL 失败后按需求名称兜底（通过）

输入：
- 提供 `doc_url`，但不可读或无法解析 node id。
- 提供 `requirement_name`。
- 当前会话存在钉钉搜索/检索 MCP 能力。

期望：
- 按需求名称搜索并读取。
- `source_type=dingtalk`
- `dingtalk_resolution=name`
- `fetch_status=fallback_to_name`
- 找到内容后继续抽取。

## 示例 3：URL 失败且缺少需求名称（待确认）

输入：
- 提供 `doc_url`，但不可读。
- 缺少 `requirement_name`。

期望：
- 要求用户提供 `requirement_name`。
- 不生成技术方案。
- `fetch_status=awaiting_requirement_name`
- `technical_plan_status=pending`

## 示例 4：钉钉 MCP 未加载（失败）

输入：
- 已选择钉钉来源。
- 当前会话没有可达的钉钉 MCP 能力。

期望：
- 读取前停止。
- 返回 `当前会话未加载钉钉 MCP`。
- `fetch_status=failed`
- `requirements_stage_gate=failed`
- 进入独立失败输出。

## 示例 5：钉钉表格 / AI 表专用工具缺失（部分读取）

输入：
- `get_document_info` 返回 `contentType=ALIDOC, extension=axls` 或 `extension=able`。
- 当前会话没有对应表格 MCP 或 AI 表 MCP 工具。

期望：
- 不声称已结构化读取表格或 AI 表。
- 不使用 `get_document_content`、`download_file` 或 `submit_export_job` 读取在线表格 / AI 表。
- `axls` 提示钉钉表格 MCP 入口：`https://aihub.dingtalk.com/#/detail?instanceId=622409&detailType=instanceMcpDetail&mcpId=9704`，安装后验证 `get_all_sheets` / `get_range`。
- `able` 提示钉钉 AI 表格 MCP 入口：`https://aihub.dingtalk.com/#/detail?instanceId=63080&detailType=instanceMcpDetail&mcpId=9555`，安装后验证 `get_tables` / `query_records`。
- 没有专用兜底时，设置 `source_completeness=partial`，并将缺失工具和业务影响写入 `source_gaps`。

## 图片和附件示例

## 示例 6：非关键图片/附件基础登记（通过）

输入：
- `adoc` 正文或 blocks 包含图片和附件。
- 资源不影响范围、接口、数据写入、时间规则、权限或验收。

期望：
- 将资源写入 `图片资料清单` 或 `附件资料清单`。
- 基础登记字段包含来源位置、资源类型、resourceId/URL、名称、下载/解析状态和缺口说明。
- 未下载或未校验时标注“未校验，不作为需求依据”。
- 不因为非关键资源缺少 HTTP 状态、尺寸或 sha256 阻塞完成态。

## 示例 7：关键资源失败（待确认）

输入：
- 图片或附件承载接口字段、业务规则、验收截图、权限说明、时间规则或数据写入规则。
- resourceId 下载、附件解析或可用兜底失败。

期望：
- 将失败路径、资源标识、错误摘要和业务影响写入 `待确认事项`。
- 设置 `source_completeness=partial`。
- 若影响实现决策，写入 `blocking_source_gaps`。
- `technical_plan_status=pending`，不推荐进入实现或 `$lingxi-code`。
- 不输出“放弃”选项；确认项只能引导继续恢复、等待补充材料，或由用户明确授权按缺口风险继续。

## 示例 7A：多张图片部分成功、部分网关传输失败（待确认）

输入：
- 钉钉 `adoc` 中识别到 7 张图片。
- 其中 5 张图片通过 `download_doc_attachment` 拿到临时下载 URL。
- 另外 2 张图片的下载调用发生网关传输失败。
- 无法确认失败图片是否只是不影响需求的装饰图片。

期望：
- 5 张成功图片写入 `图片资料清单`，记录下载状态、HTTP 状态、Content-Type、字节数、像素尺寸和 sha256（如已完成校验）。
- 2 张失败图片不能写成“已放弃”，也不能从需求依据中静默删除。
- 对 2 张失败图片继续尝试恢复：重新调用 `download_doc_attachment` 刷新临时 URL，检查 Markdown/jsonml/block 中的替代 resourceId 或原始 OSS URL，识别 `noAuth.png` / 403 / 占位图，必要时对 `adoc` 尝试导出 `markdown` 或 `docx` 并解包 `word/media/`。
- 若恢复仍失败，记录资源位置、resourceId、失败路径、错误摘要、已尝试恢复路径和业务影响。
- 设置 `source_completeness=partial`、`fetch_status=partial_with_gaps`、`source_gap_approval=pending`。
- 将这 2 张图片写入 `blocking_source_gaps`，因为它们可能影响需求完整性。
- `technical_plan_status=pending`，不推荐进入实现或 `$lingxi-code`。
- `请你确认` 只能包含：
  1. `继续尝试恢复资源`
  2. `我补充原图/导出包/授权后重试`
  3. `按已记录缺口继续，但保留来源不完整风险`

## 示例 7B：失败图片被确认非关键（通过）

输入：
- 有 2 张图片下载失败。
- 用户或需求上下文明确确认这 2 张图片不承载需求信息，不影响范围、接口、数据写入、时间规则、权限或验收。

期望：
- 失败图片保留在 `图片资料清单`。
- 标注“未校验，不作为需求依据”。
- 不写入 `blocking_source_gaps`。
- 若没有其他来源缺口，可继续完成需求收集和技术方案。

## 示例 7C：用户授权按缺口推进（通过但来源部分完整）

输入：
- 有关键图片或重要性未知图片恢复失败。
- 助手已记录失败资源、已尝试路径和业务影响。
- 用户明确选择 `按已记录缺口继续，但保留来源不完整风险`。

期望：
- 设置 `source_gap_approval=approved`。
- `source_completeness` 仍保持 `partial`，不能改成 `complete`。
- 技术方案第一节 `需求依据` 必须记录失败图片缺口和来源不完整风险。
- 可以生成完成态技术方案，但 `下一步建议` 需要提示后续实现以已记录缺口为风险前提。

## 示例 8：关键资源完整校验升级（通过或待确认）

输入：
- 用户要求审计留痕，或图片/附件影响范围、接口、数据写入、时间规则、权限或验收。

期望：
- 关键图片记录 HTTP 状态、Content-Type、字节数、像素尺寸、sha256 和下载结论。
- 关键附件/文件记录文件名、MIME/扩展名、字节数、sha256 和解析结论。
- `noAuth.png`、过期 OSS URL、统一占位图哈希不能作为业务截图证据。
- 校验失败且影响实现决策时，进入待确认；校验成功时可作为需求依据。

## 示例 9：普通文件节点读取成功（通过）

输入：
- `get_document_info` 返回 `contentType!=ALIDOC` 且 `nodeType=file`。
- `download_file` 返回可下载文件。

期望：
- 下载原文件，并记录文件名、MIME/扩展名、下载/解析状态。
- 按类型解析 docx/pdf/spreadsheet/zip/image/text。
- 关键文件按完整校验升级；非关键图片可只基础登记。
- 加密、损坏、过大或不支持的关键文件写入 `待确认事项`，必要时设置 `source_completeness=partial`。

## 示例 9A：关键钉钉引用文档读取成功（通过）

输入：
- 主需求钉钉文档正文引用另一篇钉钉接口说明文档。
- 引用上下文说明该文档包含接口字段、验收标准或权限规则。

期望：
- 将引用写入 `引用资料清单`，记录来源段落、链接类型、链接摘要、读取状态和影响判断。
- 对引用钉钉文档先调用 `get_document_info`，再按 `adoc / axls / able / file` 路由读取。
- 引用文档读取成功后，将关键规则纳入需求抽取和需求依据。
- 技术方案第一节 `引用需求资料` 列出该引用文档和读取结论。

## 示例 9B：非关键钉钉引用只登记不读取（通过）

输入：
- 主需求钉钉文档引用历史背景、会议纪要或无关说明文档。
- 引用上下文明确不影响本期范围、接口、验收、权限或实现决策。

期望：
- 将引用写入 `引用资料清单`。
- 标注“未读取，不影响本期需求依据”或等价说明。
- 不设置 `source_completeness=partial`。
- 不阻塞需求收集和技术方案完成态。

## 示例 9C：TAPD 链接登记到来源信息（通过）

输入：
- 主需求钉钉文档包含 TAPD 链接。
- 当前会话没有 TAPD 读取能力。
- 链接上下文无法判断其承载关键规则，或明确只是关联需求/任务追溯。

期望：
- TAPD 链接必须写入 `引用资料清单`。
- 记录链接上下文、能判断时记录疑似类型（需求/缺陷/任务/迭代等）和未读取原因。
- 不声称已读取 TAPD 内容。
- 技术方案第一节 `引用需求资料` 包含该 TAPD 链接和读取状态。

## 示例 9D：TAPD 关键内容无法读取（待确认）

输入：
- 主需求钉钉文档包含 TAPD 链接。
- 链接上下文说明 TAPD 承载验收标准、优先级、范围、接口或关键业务规则。
- 当前会话没有 TAPD 读取能力，且用户没有提供摘录或导出文件。

期望：
- TAPD 链接写入 `引用资料清单`。
- 设置 `source_completeness=partial`。
- 将 TAPD 不可读及业务影响写入 `source_gaps`。
- 若影响实现决策，写入 `blocking_source_gaps`，`technical_plan_status=pending`，不推荐进入实现或 `$lingxi-code`。
- 询问用户补充 TAPD 内容摘录、导出文件、截图或授权可读来源。

## 示例 9E：用户提供 TAPD 导出或摘录（通过）

输入：
- 主需求包含 TAPD 链接。
- 用户提供 TAPD 内容摘录、截图、导出文件或本地文件。

期望：
- 按本地方案/补充材料读取用户提供内容。
- 在 `引用资料清单` 中关联原 TAPD 链接和补充材料路径或说明。
- 技术方案第一节 `引用需求资料` 同时列出原 TAPD 链接和已读取的补充材料。
- 若补充材料足以覆盖关键规则，不因 TAPD 原链接不可直接读取而阻塞完成态。

## 对话和范围示例

## 示例 10：纯对话需求（通过或待确认）

输入：
- 用户没有提供钉钉链接、本地方案或已整理需求文档。
- 用户明确要求 `$lingxi-plan` 通过对话整理需求。

期望：
- 设置 `source_type=conversation`。
- 通过对话收集目标、业务规则、范围、验收和不确定点。
- 完成态技术方案前记录用户选择：`整理为需求文档`、`不整理，按对话确认推进` 或 `暂停，补充需求材料`。

## 示例 11：部分交付但缺少范围清单（待选择）

输入：
- 用户表示只做部分需求。
- `需求清单` 包含 `R1..Rn`。
- 缺少 `本期要做` / `本期不做`。

期望：
- 不设置 `fetch_status=failed`。
- 要求用户选择 `R*` 编号。
- 根据选中/未选中的需求项生成 `本期要做` 和 `本期不做`。
- 选择完成前 `technical_plan_status=pending`。

## 示例 12：第三方对接已明确（通过）

输入：
- 需求内容明确存在第三方对接并提供文档。

期望：
- 不重复询问是否存在第三方对接。
- 解析关键对接信息。
- 填写 `第三方对接`。

## 技术方案示例

## 示例 13：纯前端需求只生成前端方案（通过）

输入：
- 用户说明“新增一个页面和公共组件，不改后端”。
- 需求读取和需求理解已确认。

期望：
- `implementation_surface=frontend`
- 生成 `<frontend_project_root>/docs/features/<requirement_title>_前端技术方案.md`。
- 不强制生成后端技术方案。
- 前端方案第一节引用需求依据，并包含目录、组件设计、数据管理、技术规范确认和验证计划。

## 示例 14：全栈需求同时生成两份方案（通过）

输入：
- 需求包含新增或改造接口、页面展示、Redux/Store 状态或组件改造。
- 需求理解已确认。
- 已提供 `backend_project_root` 和 `frontend_project_root`，或当前项目明确是 `fullstack`。

期望：
- `implementation_surface=fullstack`
- 后端技术方案和前端技术方案分别落到对应端项目；当前项目明确是 `fullstack` 时可落到同一项目。
- 两份方案第一节引用同一主需求依据。
- 完成态 `落盘结果` 同时列出两份方案路径。

## 示例 15：纯后端需求保持现状（通过）

输入：
- 需求只涉及接口、数据、异步任务、权限、缓存、MQ、定时任务或后端链路。

期望：
- `implementation_surface=backend`
- 只生成 `<backend_project_root>/docs/features/<requirement_title>_技术方案.md`。
- 不强制生成前端技术方案。

## 示例 16：无法判断端类型（待确认）

输入：
- 用户只说“实现这个需求”。
- 来源材料无法判断是否涉及前端或后端。

期望：
- `implementation_surface=unknown`
- 如果方案类型会影响交付范围，进入待确认。
- 不输出完成态技术方案，不推荐进入实现或 `$lingxi-code`。

## 示例 16A：当前是后端项目但需求含前端（待确认）

输入：
- 当前只提供 `project_root`。
- 该目录命中 Java/Kotlin/Spring 后端信号。
- 需求同时包含接口改造和页面/组件改造。

期望：
- `current_project_role=backend`
- `implementation_surface=fullstack`
- 将 `project_root` 映射为 `backend_project_root`。
- 后端技术方案落盘到后端项目。
- 前端技术方案只输出预览，不落到后端项目。
- `technical_plan_status=pending`
- `backend_plan_status=generated`
- `frontend_plan_status=preview_only`
- `missing_fields` 包含 `frontend_project_root`，并询问用户提供前端项目目录。

## 示例 16B：当前是前端项目但需求含后端（待确认）

输入：
- 当前只提供 `project_root`。
- 该目录命中 React/Vue/Next/Vite/Webpack 等前端信号。
- 需求同时包含页面/组件改造和后端接口或数据改造。

期望：
- `current_project_role=frontend`
- `implementation_surface=fullstack`
- 将 `project_root` 映射为 `frontend_project_root`。
- 前端技术方案落盘到前端项目。
- 后端技术方案只输出预览，不落到前端项目。
- `technical_plan_status=pending`
- `frontend_plan_status=generated`
- `backend_plan_status=preview_only`
- `missing_fields` 包含 `backend_project_root`，并询问用户提供后端项目目录。

## 示例 16C：当前项目角色无法识别（待确认）

输入：
- 当前只提供 `project_root`。
- 目录无法识别为后端、前端或全栈项目。
- 需求涉及方案落盘。

期望：
- `current_project_role=unknown`
- 不静默把技术方案落到当前项目。
- 进入待确认，要求用户确认当前项目角色，或提供 `backend_project_root` / `frontend_project_root`。
- 不输出完成态，不推荐进入实现或 `$lingxi-code`。

## 示例 17：完成输出顺序（通过）

输入：
- 需求读取成功。
- 需求理解已确认，或用户授权按假设推进。
- 涉及端技术方案已生成并落盘。
- 若 `source_completeness=partial`，所有 `blocking_source_gaps` 已被解决，或用户已明确授权按命名缺口推进。

期望：
- 输出顺序：`技术方案预览`、`落盘结果`、`下一步建议`、`交接摘要`。
- `requirements_stage_gate=captured`
- `technical_plan_status=generated`
- `implementation_surface=backend | frontend | fullstack`
- 涉及端方案路径都存在；未涉及端方案路径可为空。
- 涉及端 `*_plan_status` 均为 `generated`；`preview_only` 不满足完成态。
- 完成态必须满足 `blocking_source_gaps=[]`，或 `source_gap_approval=approved`。
- 默认不展示完整 `RequirementContext` YAML。

## 示例 18：待确认输出顺序（通过）

输入：
- 需求读取成功。
- 仍有必要确认项。

期望：
- 输出顺序：`已生成内容`、`待确认事项`、`请你确认`、`交接摘要`。
- `technical_plan_status=pending`
- 不推荐进入实现或 `$lingxi-code`。
- 确认问题必须出现在已生成文件列表之后。

## 示例 19：缺少可写项目路径（待确认）

输入：
- 需求读取和理解校准完成。
- 未提供可写 `project_root`、`backend_project_root` 或 `frontend_project_root`，无法落盘 `需求清单`、`需求收集单`、后端技术方案或前端技术方案。

期望：
- 只输出预览或待确认结果。
- 不输出完成态。
- 不推荐进入实现或 `$lingxi-code`。
- `missing_fields` 包含缺失的 `project_root`、`backend_project_root` 或 `frontend_project_root`。

## 复杂逻辑示例

## 示例 20：简单需求不询问复杂逻辑（通过）

输入：
- 简单 CRUD 类需求，没有复杂逻辑信号。

期望：
- 不询问复杂逻辑选择。
- 技术方案记录 `复杂逻辑信号：未识别；是否命中复杂逻辑：否（按简单需求处理）`。
- 不输出空的完整场景表。

## 示例 21：复杂逻辑包含场景清单和补充确认（通过）

输入：
- 技术方案包含状态流转、分支规则、异步处理、第三方对接、权限差异、批处理、初始化、补录、重放或兜底规则。

期望：
- 助手展示 `复杂逻辑信号` 和推荐选择。
- 用户选择 `是否命中复杂逻辑=是`。
- 写接口/数据细节前，助手展示已识别场景覆盖，并记录 `场景补充确认`。
- `场景清单` 字段为 `场景ID | 什么时候发生 | 当前状态 | 输入内容 | 怎么处理 | 处理结果 | 异常情况 | 怎么验证`。
- `实施映射` 引用相关 `场景ID`。

## 示例 22：用户不确定是否命中复杂逻辑（待确认）

输入：
- 助手展示可能的复杂逻辑信号。
- 用户选择 `是否命中复杂逻辑=不确定`。

期望：
- 将不确定性记录到 `待确认事项`。
- 若影响范围、数据写入、接口行为、时间规则、权限或验收，技术方案保持待确认。

## 影响范围示例

## 示例 23：已做代码扫描的影响范围（通过）

输入：
- 提供 `project_root`。
- 助手写影响范围前扫描了相关代码。

期望：
- 影响范围可说明来自真实代码扫描证据。
- 受影响模块/接口/数据/调用链可追溯。

## 示例 24：未做代码扫描的影响范围（带说明通过）

输入：
- 未提供 project root，或未扫描代码。

期望：
- 影响范围标记 `基于需求推断，未做代码扫描验证`。
- 方案不声称来自真实代码证据。
