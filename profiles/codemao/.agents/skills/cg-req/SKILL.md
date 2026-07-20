---
name: cg-req
description: Use when collecting requirements from DingTalk docs or local plans before producing an implementation-ready technical plan
---

# cg-req

## 目标
规范实现前的需求收集流程：
- 读取钉钉需求、本地方案，或两边都读。
- 钉钉来源先读元信息，再按可用 MCP 能力尽量解析在线文档、表格、AI 表、文件、图片和附件；表格/AI 表工具缺失时记录缺失工具并引导接入专用 MCP，不能用通用文档读取或导出伪装完整读取。
- 当钉钉和本地方案同时存在时，让使用者选择来源。
- 钉钉 URL 读取失败时，可在 MCP 支持检索的情况下按需求名称兜底。
- 支持用户明确要求通过对话整理需求；纯对话来源必须记录确认依据，不能伪装成已读取外部文档。
- 先生成通用 `需求清单`，再校准需求理解，最后按影响范围生成后端、前端或全栈技术方案。
- 生成可直接使用、也可供 `cg-gen` 消费的技术方案；后端使用 `方案设计单`，涉及前端改动时生成独立的 `前端技术方案`。
- 维护紧凑的 `RequirementContext`（需求上下文）作为交接元数据；默认不把完整 YAML 展示给普通使用者。

团队术语：
- `需求清单`: 可选择的需求列表，使用 `R1`, `R2`, `R3`...
- `需求收集单`: 需求收集摘要。
- `开发补充单`: 开发补充的实现信息或对话结果。
- `方案设计单`: 在 cg-req 阶段生成的技术方案，可直接作为实施依据，也可供 cg-gen 消费。
- `前端技术方案`: 在 cg-req 阶段生成的前端方案，覆盖页面、路由、组件、状态管理、前端接口使用、规范确认和验证计划。

## 快速开始
可直接复制以下任一说法开始：
```text
使用 $cg-req 读取这个钉钉需求：<钉钉链接>，项目在 <项目路径>
```
```text
使用 $cg-req 读取本地方案：<方案文件路径>，项目在 <项目路径>，生成技术方案
```
```text
使用 $cg-req 对比钉钉 <钉钉链接> 和本地 <方案文件路径>，项目在 <项目路径>，冲突先问我
```

默认走轻流程：能从资料中确认的信息直接记录；只在影响范围、写入、接口、时间规则、权限或验收时追问。未识别到复杂逻辑信号的简单需求不额外追问复杂逻辑，只记录按简单需求处理，不输出空的完整场景表。用户说“对比”“两边都读”“冲突先问我”时，视为已选择 `source_choice=mixed`。
如果用户只说“使用 $cg-req 帮我整理一个需求”且没有提供钉钉或本地来源，视为纯对话需求，先通过对话收集最小需求信息。

## 触发与范围

- 仅显式触发：`cg-req` 或 `$cg-req`。
- 编码过程中不要自动触发，除非用户明确要求做需求收集。
- 本技能不直接生成实现代码。
- 功能清单直接生成后端计划不属于本推广版本范围。若用户要求从独立功能清单生成后端计划，说明 `cg-req` 可以先把来源材料整理为 `需求清单`，但不能强制“一条需求对应一个接口”。如果团队需要更强的功能清单模式，应由单独技能承接。

## 输入约定
至少需要一个来源输入，或用户明确要求通过对话整理需求：
- `doc_url?: string`
- `requirement_name?: string`
- `local_plan_files?: string[]`
- `conversation_requirement?: boolean`（无外部来源、但用户明确要求 `$cg-req` 通过对话整理需求时使用，设置 `source_type=conversation`）
- `source_choice?: "dingtalk" | "local_plan" | "mixed"`（钉钉和本地方案都存在、且用户未选择时必填）
- `project_root?: string`（兼容旧入口；只提供该字段时必须先识别当前项目角色，再映射到对应端项目路径）
- `current_project_role?: "backend" | "frontend" | "fullstack" | "unknown"`（当前 `project_root` 或工作区项目角色）
- `backend_project_root?: string`（后端技术方案落盘项目；后端或全栈需求需要）
- `frontend_project_root?: string`（前端技术方案落盘项目；前端或全栈需求需要）
- `implementation_surface?: "backend" | "frontend" | "fullstack" | "unknown"`（可由用户指定，也可由需求内容、代码影响范围或对话确认推断）
- `developer_notes?: object`（收集阶段可选；完成前按需通过对话补齐）
  - `本期要做?: string[]` (legacy key: `include_scope`)
  - `本期不做?: string[]` (legacy key: `exclude_scope`)
  - `第三方对接信息?: object | "无"` (legacy key: `third_party_info`)
  - `内部改造点?: string[]` (legacy key: `internal_change_points`)
  - `验收口径?: string[]` (legacy key: `acceptance_notes`)
  - `需求理解确认?: object`
    - `已确认?: boolean`
    - `修正点?: string[]`
    - `补充说明?: string[]`

`source_choice` 只在已提供来源之间做选择，本身不算需求来源。

来源规则：
- 只有钉钉输入时，走钉钉流程。
- 只有 `requirement_name` 时，在钉钉 MCP 搜索/检索能力可用的情况下主动检索，并设置 `source_type=dingtalk`、`dingtalk_resolution=name`。
- 只有 `local_plan_files` 时，读取本地方案，并设置 `source_type=local_plan`。
- 没有钉钉输入、`requirement_name` 或 `local_plan_files`，但用户明确要求通过 `$cg-req` 对话整理需求时，设置 `source_type=conversation`，进入需求理解校准和纯对话依据记录流程。
- 钉钉输入和 `local_plan_files` 同时存在时，要求用户选择：
  - `读钉钉`: 只读钉钉，并设置 `source_type=dingtalk`。
  - `读本地方案`: 只读本地方案，并设置 `source_type=local_plan`。
  - `两边都读`: 合并两边来源，并设置 `source_type=mixed`。
- 多种来源同时存在时，不要静默替用户选择。
- 不要盲目搜索整个仓库。只读取用户提供的路径，或用户确认过的明确匹配项目文档。

## 规则优先级

- `SKILL.md` 是唯一规则源。
- `references/tech-template.md` 定义后端技术方案结构和字段细节；`references/frontend-tech-template.md` 定义前端技术方案结构和字段细节。
- `references/cases.md` 只提供示例和预期行为，不得新增本文件之外的隐藏门禁。

## 工作流程

### 0) 需求来源确认（必须）
读取内容前：
- 判断请求包含钉钉输入、本地方案输入、纯对话需求，还是多种来源。
- 两者都有且缺少 `source_choice` 时，停止并要求用户选择 `读钉钉 / 读本地方案 / 两边都读`。
- 使用本地方案时，先确认每个路径存在且可读。
- 将每个本地来源路径记录到 `本地方案路径列表`。
- 纯对话需求没有外部读取步骤；记录 `source_type=conversation`，并在生成完成态技术方案前按“纯对话确认来源”记录用户选择。

### 0.5) MCP 健康检查（仅钉钉，必须）
读取钉钉内容前：
- 检查钉钉 MCP 是否可达、可调用。
- 至少满足以下一项：
  - resource/template 列表返回可用条目；
  - 至少一个读取或检索调用能执行。

若 MCP 不可用：
- 停止并返回可操作诊断：
  - `当前会话未加载钉钉 MCP`
  - 提醒用户启用 MCP 后重试。

安装后验证三步：
- 工具可见性：刷新/重开会话后，以当前会话实际可见工具名为准，确认工具列表出现预期工具名。
- 能力验证：先调用一个只读列表类接口，确认 MCP 可调用。
- 业务验证：对原始 nodeId/baseId 做最小读取，例如小范围表格或少量记录；成功后再继续需求抽取。

### 1) 钉钉链接优先读取
- 尽量从 `doc_url` 解析 node identifier。
- 始终先调用钉钉 `get_document_info`。
- 按返回元信息路由：
  - `contentType=ALIDOC, extension=adoc`: 通过 `get_document_content` 读取 Markdown 正文。
  - `contentType=ALIDOC, extension=axls`: 在表格 MCP 工具可用时，使用 `get_all_sheets` + `get_range` 读取相关范围；工具不可用时，只能保留元信息并记录缺失工具，不能用文档导出工具兜底。
  - `contentType=ALIDOC, extension=able`: 在 AI 表 MCP 工具可用时，使用 `get_tables` + `query_records` 查询记录；工具不可用时，只能保留元信息并记录缺失工具，不能用文档导出工具兜底。
  - `contentType!=ALIDOC` 且 `nodeType=file`: 使用 `download_file` 凭证下载文件内容。
- 若当前会话缺少返回类型所需的 MCP 工具，记录精确的未支持类型和缺失工具到 `待确认事项`，设置 `source_completeness=partial`（来源完整性：部分）。
- 若工具缺失但当前会话存在对应类型的专用导出/CLI 兜底，先尝试该兜底；兜底不可用或失败时，不要宣称完整读取。
- 路由后的内容可读且非空时，继续做需求抽取。

#### 1.0.0) 表格 / AI 表 MCP 缺失引导（必须）
当 `get_document_info` 返回 `extension=axls` 或 `extension=able`，但当前会话缺少对应专用工具时，输出必须包含接入引导：
- `extension=axls`: 提示安装钉钉表格 MCP，入口 `https://aihub.dingtalk.com/#/detail?instanceId=622409&detailType=instanceMcpDetail&mcpId=9704`，预期工具 `get_all_sheets` / `get_range`。
- `extension=able`: 提示安装钉钉 AI 表格 MCP，入口 `https://aihub.dingtalk.com/#/detail?instanceId=63080&detailType=instanceMcpDetail&mcpId=9555`，预期工具 `get_tables` / `query_records`。
- 安装或启用后必须刷新/重开 Codex 会话，再按“安装后验证三步”确认可用；工具仍不可见时保持 `source_completeness=partial`。
- 若用户提供私有 MCP 网关 URL，可协助接入本机 Codex MCP 配置；不要在用户可见输出、日志、技能文档、需求文档或交接产物中原样回显带 `key` 的完整 URL。

#### 1.0.1) 跨类型多路径拉取策略（必须）
钉钉来源不要因为单一路径失败就停止。按文档类型优先使用最结构化的读取方式，再逐级兜底：
- `adoc`: 先读 Markdown/正文和 jsonml/block；图片、附件和 file-like block 默认先做基础登记，关键资源再按 resourceId 刷新下载和解析。
- `axls`: 表格 MCP 工具可用时，先用 `get_all_sheets` + `get_range` 读取结构化表格；不要用 `get_document_content`、`download_file` 或 `submit_export_job` 读取在线表格，这些路径会被钉钉拒绝。表格 MCP 缺失时，记录缺失工具并设置 `source_completeness=partial`；只有当前会话另有表格专用导出/CLI 能力或用户提供导出文件时，才使用该兜底。
- `able`: AI 表 MCP 工具可用时，先用 `get_tables` + `query_records` 读取结构化记录；不要用 `get_document_content`、`download_file` 或 `submit_export_job` 读取 AI 表，这些路径会被钉钉拒绝。AI 表 MCP 缺失时，记录缺失工具并设置 `source_completeness=partial`；只有当前会话另有 AI 表专用导出/CLI 能力或用户提供导出文件时，才使用该兜底。
- 普通文件节点：先用 `download_file` 下载原文件；下载成功后按 MIME 和扩展名解析 docx/pdf/spreadsheet/zip/image/text。下载失败时保留文件元信息、凭证/响应摘要，并尝试可用导出或附件下载路径。
- 图片资源：默认记录来源位置、资源类型、resourceId/URL、名称、下载/解析状态和缺口；只有图片可能承载需求信息、影响范围/接口/数据写入/时间规则/权限/验收，或用户要求审计留痕时，才按 `jsonml/block -> extraData.resourceId -> download_doc_attachment` 下载、解析或完整校验。若关键图片 resourceId 缺失或下载失败，`adoc` 可再尝试导出产物或 docx 解包 `word/media/`。
- 附件资源：默认记录来源位置、名称、类型/扩展名、resourceId/file id、下载/解析状态和缺口；只有附件可能承载需求信息、影响范围/接口/数据写入/时间规则/权限/验收，或用户要求审计留痕时，才按 `jsonml/block -> extraData.resourceId -> download_doc_attachment` 下载和解析。resourceId 缺失或失败时，只尝试附件/普通文件下载凭证或专用导出路径，不把 docx 解包当作附件恢复证据。
- 导出产物：仅对工具实际支持的类型使用；当前 `submit_export_job` 适用于 `adoc`，不适用于 `axls/able`。`markdown` 可恢复正文和资源引用，但附件通常会变成 `/core/api/resources/.../detail` 内部路径；`docx` 可解包 `word/media/` 恢复文档内嵌图片，但不要假设它会保留附件；`zip` 或普通文件按内部目录和 MIME/扩展名继续解析。
- 任一路径失败时，必须记录失败路径、资源标识（nodeId/block id/resourceId/file id）、HTTP 状态或错误摘要、Content-Type（如有）、影响判断，并继续尝试下一条可用路径。

#### 1.0.2) 关键资源不可放弃门禁（必须）
当图片、附件、文件或导出资源可能承载需求信息，或暂时无法判断是否影响需求完整性时，按关键资源处理：
- `download_doc_attachment` 网关传输失败、超时、临时 URL 失效、`noAuth.png`、`403 application/xml`、统一占位图哈希、空文件或 Content-Type 异常，都视为可恢复失败；不能把首次失败当作最终结论。
- 关键资源或重要性未知资源失败时，不允许在用户确认项中提供“放弃”作为默认选项，也不要写成“已放弃”。必须继续尝试可用恢复路径，或把未恢复资源作为来源完整性缺口保留。
- 恢复路径至少包括：重新调用 `download_doc_attachment` 刷新临时 URL、检查 Markdown/jsonml/block 中是否存在替代 resourceId 或原始 OSS URL、识别无权限图和占位图、在 `adoc` 场景尝试导出 `markdown` 或 `docx`，并对 docx 解包 `word/media/` 恢复文档内嵌图片。
- 每个未恢复资源必须记录：资源位置、resourceId/file id/URL 摘要、失败路径、错误摘要、已尝试恢复路径、是否可能影响需求理解或实现决策。
- 若恢复耗尽后仍无法读取，设置 `source_completeness=partial`、`fetch_status=partial_with_gaps`、`source_gap_approval=pending`；只要可能影响需求理解或实现决策，必须写入 `blocking_source_gaps`，技术方案保持 `pending`。
- 询问用户时使用以下选项，不使用“放弃”：
  1. `继续尝试恢复资源`：继续尝试可用 MCP、导出或下载路径。
  2. `我补充原图/导出包/授权后重试`：保持待确认，等待用户补充材料。
  3. `按已记录缺口继续，但保留来源不完整风险`：仅表示用户接受缺口推进，设置 `source_gap_approval=approved`；`source_completeness` 仍保持 `partial`，技术方案第一节必须记录来源缺口和风险。
- 只有资源已明确为非关键，且不作为需求依据时，才允许不阻塞完成态；资源清单必须标注“未校验，不作为需求依据”。

#### 1.0.3) 引用来源处理（必须）
当需求正文、Markdown、jsonml、block、附件说明或普通文件内容中出现钉钉链接、TAPD 链接或其他需求来源链接时，按以下规则处理：
- 统一登记到 `引用资料清单`，字段包括：来源段落或 block、链接类型、链接摘要、是否读取、读取结论、未读取原因、是否影响需求。
- 钉钉引用文档按需读取，不默认展开所有链接。引用承载业务规则、接口字段、验收标准、权限说明、第三方对接、表格/AI 表数据来源、流程图或关键截图时，必须按钉钉读取流程读取；仅背景、历史资料、会议纪要、无关说明或明显不影响本期范围时，只登记不读取。
- 默认只读取主需求直接引用的一层钉钉文档。二级引用只有明确影响需求理解或实现决策时，登记为待确认，或在用户授权后继续读取。
- 引用钉钉文档读取时，同样先调用 `get_document_info`，再按 `adoc / axls / able / file` 路由；引用文档内的图片、附件、表格、AI 表仍遵守来源完整性和关键资源不可放弃门禁。
- TAPD 链接无论当前会话是否可读取，都必须进入 `引用资料清单`，并在技术方案第一节 `需求依据` 的 `引用需求资料` 中体现。
- 当前会话没有 TAPD 读取能力时，不要声称已读取 TAPD；只记录链接、上下文、能判断时记录疑似类型（需求/缺陷/任务/迭代等）和未读取原因。
- 若 TAPD 链接明显承载范围、验收、接口、优先级或其他实现决策信息但无法读取，设置 `source_completeness=partial`；影响实现决策时写入 `blocking_source_gaps`，技术方案保持 `pending`，除非用户明确授权按缺口风险推进。
- 若用户提供 TAPD 内容摘录、截图、导出文件或本地文件，则按本地方案/补充材料读取，并在 `引用资料清单` 和技术方案 `需求依据` 中关联原 TAPD 链接。

#### 1.1) 钉钉来源完整性检查（必须）
对钉钉来源，尽量保留原始需求证据；推广版默认不做审计级证据保全，图片/附件按需升级：
- 对 `adoc` Markdown 正文：
  - 抽取标题、段落、列表、表格、代码块、链接和引用。
  - 抽取正文中的钉钉链接、TAPD 链接和其他来源链接到 `引用资料清单`，按“引用来源处理”判断是否读取或只登记。
  - 抽取 Markdown 图片链接到 `图片资料清单`，默认只做基础登记。
  - Markdown 原始 OSS 签名 URL 可能已过期；不得把 `403 application/xml`、权限错误或无法视觉检查的图片当作已恢复证据。非关键图片可标注“未校验，不作为需求依据”后继续；关键图片按“钉钉资源获取决策顺序”升级处理。
- 对文档 blocks：
  - 可用时调用 `list_document_blocks`。
  - 若接口支持分页、范围或游标，必须继续读取直到没有下一页；若存在嵌套 block/table/callout，尽量展开读取，无法展开时记录 block id、类型和缺口。
  - 将 link/bookmark/reference 等引用型 blocks 写入 `引用资料清单`，其中钉钉和 TAPD 链接按“引用来源处理”判断是否读取、登记或进入缺口。
  - 将 image/media/file-like/attachment blocks 分别写入 `图片资料清单` 或 `附件资料清单`。基础登记字段包括来源位置、资源类型、resourceId/URL、名称、下载/解析状态和缺口说明。
  - 附件或图片明显承载需求信息时，尝试下载、解析或总结与需求相关的内容；不支持、加密、过大或下载失败时写入 `待确认事项`，不要静默丢弃。
- 对普通钉钉文件：
  - 使用文件下载凭证，再按扩展名用可用工具解析。
  - 可读类型优先覆盖 markdown/text/docx/pdf/spreadsheet/zip/image；图片至少保留 URL/文件名/下载状态，非关键图片无法视觉检查时标注“未校验，不作为需求依据”，关键图片无法校验时标记缺口。
  - 对 zip 压缩包，列出目录并解析内部可读文件；忽略 `__MACOSX/`、`.DS_Store` 等系统元数据。zip 内部不可读文件、嵌套 zip、加密/过大/损坏文件必须写入 `待确认事项`；若可能影响需求理解，设置 `source_completeness=partial`。
- 若直接 Markdown 或 block 解析看起来不完整，或关键图片/附件缺失，且来源是 `adoc` 时，支持时尝试文档导出（`submit_export_job` + `query_export_job`，格式优先 `markdown` 或 `docx`）；导出产物下载、内部路径和 docx 解包边界按“钉钉资源获取决策顺序”处理。
- `原始需求留存单` 一旦创建，必须包含正文来源、图片资料清单、附件资料清单、导出/下载尝试结果，以及来源完整性说明。钉钉来源存在关键资源、导出兜底、`source_completeness=partial` 或用户要求审计留痕时，原始需求留存单是完成态交接的必需文件；普通非关键图片/附件只需在 `需求收集单` 保留清单和缺口摘要。

#### 1.1.1) 钉钉资源获取决策顺序（必须）
当钉钉文档包含图片、附件、表格、AI 表记录、普通文件或导出资源时，按以下顺序处理：
1. 首选结构化读取：`adoc` 读正文/jsonml/block，`axls` 读 sheet/range，`able` 读 table/record，普通文件用 `download_file`。
2. 基础登记资源：图片和附件优先从 Markdown、jsonml 或 block 读取来源位置、资源类型、resourceId/URL、名称、下载/解析状态和缺口说明；若只能拿到原始 Markdown 图片 URL，保留完整 query string，不要先改写、解码后重组或丢弃签名参数。
3. 判断是否升级：资源影响范围、接口、数据写入、时间规则、权限、验收，明显承载需求信息，或用户明确要求审计留痕时，视为关键资源并升级；否则可标注“未校验，不作为需求依据”后继续。
4. 下载、解析或完整校验：关键资源优先调用 `download_doc_attachment(nodeId, resourceId)` 获取新的临时 `downloadUrl`，普通文件优先使用文件下载凭证。关键图片完整校验时记录 HTTP 状态、Content-Type、字节数、像素尺寸和 sha256；关键附件/文件完整校验时记录文件名、MIME/扩展名、字节数、sha256 和解析结论。
5. 识别无效证据：原始 Markdown OSS 签名 URL 返回 `403 application/xml`、导出 Markdown 内部路径 302 到 `noAuth.png`、多张图片得到相同占位图哈希，或关键图片缺少完整校验信息时，都不能作为完整图片证据；非关键图片可保留缺口但不得作为需求依据。
6. 尝试导出兜底：`adoc` 内容不完整、关键 resourceId 不可用或关键资源下载失败时，尝试导出 `markdown` 或 `docx`；docx 解包 `word/media/` 只用于文档内嵌图片兜底，不保证恢复附件。`axls/able` 必须使用表格/AI 表专用 MCP 或专用导出/CLI；当前只有文档导出工具时，不得把 `submit_export_job` 当作它们的兜底。
7. 失败后保留缺口：关键资源所有可用路径都失败，或资源重要性未知且可能影响需求理解或实现决策时，设置 `source_completeness=partial`、`fetch_status=partial_with_gaps`、`source_gap_approval=pending`，将资源节点、resourceId/file id、失败响应、已尝试路径和业务影响写入 `待确认事项` 和 `blocking_source_gaps`；非关键资源缺口只记录在资源清单中，并标注“未校验，不作为需求依据”。

### 2) 钉钉名称兜底
以下情况触发名称兜底：
- URL node id 无法解析。
- URL 解析成功但读取结果为空。
- 权限不足、未授权或被禁止访问。
- 节点不存在。

兜底行为：
- 缺少 `requirement_name` 时，要求用户提供需求名称。
- 只有当前会话存在钉钉 MCP 检索/搜索能力时，才使用 `requirement_name` 进行 search/retrieval。
- 若没有搜索/检索能力，返回“缺少钉钉搜索/检索 MCP 能力”，记录到失败态或待确认，不要宣称名称兜底成功。
- 找到相关结果后，读取最相关内容并继续抽取。

### 2.5) 本地方案读取
适用于 `source_choice=local_plan`、`source_choice=mixed`，或只提供 `local_plan_files` 的情况：
- 读取 `local_plan_files` 中的每个路径。
- 将本地方案作为需求/设计证据，不等同于实现授权。
- 抽取可复用业务点、范围、验收说明、开放问题和已有设计决策。
- 本地路径缺失或不可读时，停止并返回失败态，列出失败路径。
- 与钉钉混合读取时，保留两边证据引用；事实冲突时写入 `待确认事项`。

### 3) 失败退出
选定来源全部失败时：
- 返回结构化失败结果，包含失败原因和最小下一步输入。
- 不进入方案生成阶段。

### 4) 需求抽取
从已读取内容中，只抽取下游规划所需的最小集合：
- 标题
- 摘要
- 约束
- 验收口径
- 开放问题
- 图片证据（`图片资料清单`）：钉钉 Markdown、block 或导出内容包含图片时记录
- 附件证据（`附件资料清单`）：钉钉 blocks、下载文件或导出内容包含附件时记录
- 引用证据（`引用资料清单`）：正文、block、附件说明或普通文件内容包含钉钉、TAPD 或其他需求来源链接时记录
- 证据引用：node/section anchors、本地路径、图片 URL、附件名称/resourceIds

保持输出简洁，避免整篇复制原文。

### 4.5) 通用需求清单生成（必须）
- 生成通用 `需求清单`，固定包含以下部分：
  - `背景`
  - `需求要点`
  - `需求注意事项`
  - `第三方对接`
  - `需实现部分`
- `需实现部分` 必须用可选择编号：`R1`, `R2`, `R3`...
- 默认落盘路径：
  - `docs/features/<requirement_title>_需求清单.md`
- 文件名冲突时追加 `_YYYYMMDD_HHMM` 后缀。

### 5) 对话补齐流程（生成技术方案前）
按需要对话，不机械追问。

1. `需求理解校准`（必须）：
   - 技术方案前，用直白语言复述需求。
   - 包含：
     - `我理解的目标`
     - `关键业务规则`
     - `涉及对象/来源`
     - `主要场景`
     - `不确定点`
   - 仅当已读取内容或开发补充不清楚、缺失、冲突，或可能影响范围、验收、用户可见行为、数据行为、实现决策时，才使用 `澄清检查项（可选）`。
   - 已明确的信息直接记录为已确认，不重复追问。
   - 高影响不确定项影响范围、数据写入、接口行为、时间规则、权限或验收时，除非用户明确同意按命名假设推进，否则不要生成完成态技术方案。
   - 将澄清答案记录到 `需求理解确认.补充说明` 或 `修正点`。
   - 确认后记录 `需求理解确认`；修正影响需求项时，更新 `需求清单`。

2. `第三方对接确认`（仅按需询问）：
   - 需求内容已确认存在第三方对接时，收集/读取已提供文档；文档缺失则写入 `待确认事项`。
   - 内容明确没有第三方对接时，直接标记 `第三方对接=无`，不要重复询问。
   - 不清楚且可能影响范围或接口设计时，再询问是否存在第三方对接。

3. `实现范围确认`（仅按需询问）：
   - 用户明确表示只做部分需求、但未提供 `本期要做` / `本期不做` 时，使用已生成的 `R*` 条目要求选择。
   - 根据选中/未选中的需求项生成 `本期要做` 和 `本期不做`。
   - `需求清单` 已生成后，范围细节缺失不是读取失败，而是进入待确认。

4. `参考模板确认`（仅有用时询问）：
   - 仅当用户提到复用、相似历史工作、本地示例，或需求明显受益于已知实现模式时，才询问是否导入已有模板/示例。
   - 若需要，收集模板路径/链接并抽取可复用点。

5. `方案生成准备完成`:
   - 输出可直接使用、也可交给 cg-gen 的完成输入：需求清单 + 对话结果 + 模板引用。

### 5.5) 实施端类型判断（生成技术方案前，必须）
在生成技术方案前，判断 `implementation_surface`：
- `backend`: 仅涉及后端接口、数据、任务、服务链路、权限、缓存、MQ、定时任务或后端配置。
- `frontend`: 仅涉及页面、路由、组件、前端状态、前端配置、前端第三方库、前端体验或前端工程改造。
- `fullstack`: 同时涉及后端接口/数据/链路和前端页面/组件/状态/接口使用。
- `unknown`: 需求材料无法判断是否涉及前端或后端，且方案类型会影响交付范围。

判断依据优先级：
1. 用户明确说明。
2. 需求内容、本地方案或对话确认。
3. 已扫描代码的真实影响范围。
4. 未扫描代码时的需求推断。

规则：
- `frontend` 只生成前端技术方案，不强制生成后端方案。
- `backend` 只生成后端技术方案，沿用现有后端模板。
- `fullstack` 同时生成后端技术方案和前端技术方案，两份方案第一节都引用同一需求依据。
- `unknown` 且影响是否生成前端/后端方案时，进入待确认，不输出完成态，不推荐进入实现或 cg-gen。

### 5.6) 项目角色与跨项目路径判断（生成技术方案前，必须）
如果提供了 `project_root`、`backend_project_root` 或 `frontend_project_root`，先确认路径可写。只提供 `project_root` 时，识别 `current_project_role` 并映射项目路径：
- 后端信号：`pom.xml`、`build.gradle`、`settings.gradle`、`src/main/java`、`src/main/kotlin`、Spring/Java/Kotlin 服务结构。
- 前端信号：`package.json` 且包含 React/Vue/Next/Vite/Webpack 等前端依赖，或存在 `src/pages`、`src/components`、路由目录。
- 同时命中后端和前端信号，设置 `current_project_role=fullstack`。
- 无法识别时，设置 `current_project_role=unknown`；如果影响方案落盘，进入待确认。

路径映射规则：
- `current_project_role=backend` 时，`project_root` 只能默认映射为 `backend_project_root`。
- `current_project_role=frontend` 时，`project_root` 只能默认映射为 `frontend_project_root`。
- `current_project_role=fullstack` 时，`project_root` 可同时作为 `backend_project_root` 和 `frontend_project_root`。
- 不把另一端方案静默落到当前项目，除非当前项目明确是 `fullstack`。

### 5.7) 核心代码声明核验（生成技术方案前，必须）
当技术方案引用现有接口、URL、Controller、DTO、Service、Mapper、表、字段、数据来源、关联键或导出能力时，必须先做 targeted repository inspection，不能把基于命名或习惯的推断写成事实。

核验范围只覆盖核心实现事实：
- 接口路径
- Controller / Service / DTO / Mapper
- 表、字段、数据来源
- 关联键、过滤条件、排序字段
- 既有导出能力或异步导出入口

权限、日志、回滚、测试覆盖暂不作为本阶段硬门禁；如能顺手确认可记录为非阻塞建议，不能因为未覆盖这些项阻止完成态。

每个影响实现的代码声明必须标注核验状态：
- `confirmed`: 已用仓库文件和行号确认。
- `refuted`: 仓库证据与方案假设冲突。
- `unverified`: 针对性搜索后仍无法确认。

`confirmed` 必须在技术方案的影响范围、接口设计、数据方案或实施映射中写明 repo-relative 文件路径和行号。`refuted` / `unverified` 如影响实现范围、数据正确性、接口契约或核心数据链路，必须写入 `待确认事项`；未获用户明确授权前，不得把依赖该声明的方案标记为完成态。

必须核验：
1. API URL：读取 Controller 类级 Mapping、方法 Mapping 和常量定义，还原真实路径。
2. 请求 / 响应字段：读取 DTO、Request、Response 类，确认字段存在，或明确标注为本次目标新增。
3. 数据来源与关联键：读取 Entity、Mapper、XML、Service，确认表、字段、关联键、过滤条件、排序字段。
4. 既有导出能力：读取现有导出接口和导出服务签名，确认复用方式、任务模型和返回方式。

### 6) 需求资料落盘
抽取成功后，如果目标项目路径已知或已确认，则落盘有用文档。没有任何可写项目路径时，只能输出预览或待确认结果；不要输出完成态，也不要推荐进入实现或 cg-gen。

需求资料落盘根目录：
- 优先使用显式 `project_root`。
- 没有 `project_root` 时，纯后端需求使用 `backend_project_root`，纯前端需求使用 `frontend_project_root`。
- 全栈需求没有 `project_root` 但同时提供前后端目录时，默认把通用需求资料落到 `backend_project_root`，并在两份技术方案第一节引用同一需求资料路径。
- 全栈需求只知道一端目录时，通用需求资料落到已知端项目；未知端方案保持预览态。

- `需求清单`（完成交接必须）：
  - 默认目录：`docs/features/`
  - 文件名：`<requirement_title>_需求清单.md`
  - 冲突规则：追加 `_YYYYMMDD_HHMM` 后缀
- `需求收集单`（完成交接必须）：
  - 默认目录：`docs/features/`
  - 文件名：`<requirement_title>.md`
  - 冲突规则：追加 `_YYYYMMDD_HHMM` 后缀
  - 内容必须包含来源链接/id、抽取摘要/约束/验收/开放问题、`需求理解确认`、原始证据引用、`图片资料清单`、`附件资料清单`、`引用资料清单`、`本期要做` / `本期不做`，以及第三方信息状态（`已提供` / `无` / `待补充`）。
- `原始需求留存单`（按需）：
  - 默认目录：`docs/features/raw/`
  - 文件名：`<requirement_title>_原始需求.md`
  - 冲突规则：追加 `_YYYYMMDD_HHMM` 后缀
  - 钉钉来源：推荐保留原始 Markdown 快照或摘录范围说明。
  - 本地方案来源：如果源文件已在仓库内，可不重复留存。
  - 带图片/附件的钉钉来源：包含图片 URL、附件元信息、下载/导出尝试结果、已解析附件摘要，以及不支持内容的缺口说明。
  - 钉钉来源存在关键资源、导出兜底、`source_completeness=partial`，或用户要求审计留痕时，完成态必须包含该文件路径；普通非关键图片/附件只需在 `需求收集单` 保留清单和缺口摘要。

只有 `需求清单` 和 `需求收集单` 都成功后，才能设置 `requirements_stage_gate=captured`。若完成态要求原始需求留存单，也必须成功落盘。

### 6.5) 技术方案生成（cg-req 阶段）
`需求清单`、必要对话补齐和 `implementation_surface` 判断完成后，在 cg-req 阶段生成并落盘涉及端的方案：
- 后端技术方案默认路径：
  - `<backend_project_root>/docs/features/<requirement_title>_技术方案.md`
- 前端技术方案默认路径：
  - `<frontend_project_root>/docs/features/<requirement_title>_前端技术方案.md`
- 文件名冲突时追加 `_YYYYMMDD_HHMM` 后缀。
- 后端模板来源：
  - 使用 `references/tech-template.md`。
  - 默认使用简版。
  - 当需求存在跨模块联动、外部依赖调用、数据写入或异步一致性设计时，升级为完整版。
- 前端模板来源：
  - 使用 `references/frontend-tech-template.md`。
  - 涉及页面、路由、组件、前端状态、前端配置、前端第三方库、前端体验或前端工程改造时生成。
- 生成规则：
  - `implementation_surface=backend`: 需要 `backend_project_root`；只生成后端技术方案。
  - `implementation_surface=frontend`: 需要 `frontend_project_root`；只生成前端技术方案。
  - `implementation_surface=fullstack`: 分别需要 `backend_project_root` 和 `frontend_project_root`；已知端落盘，未知端只输出预览并询问目录。
  - 采用“当前+询问”策略：当前项目对应端方案先落盘；另一端路径未知时，设置对应端 `*_plan_status=preview_only`，并在待确认事项中要求补充目录。

需求依据门禁：
- 每份技术方案第一节必须是 `需求依据`，先于目标、范围、接口、场景、数据、组件或风险内容。
- 钉钉 URL 来源必须引用原始 `doc_url`、文档标题或 node 信息；URL 失败后按名称兜底时，记录检索到的钉钉文档信息、`dingtalk_resolution=name` 和来源完整性。
- 整理后文档来源必须引用已生成或已提供的 `需求清单`、`需求收集单`、按需生成的 `原始需求留存单`，以及用户提供的本地需求文档路径或链接。
- 需求中识别到钉钉引用文档、TAPD 链接或其他外部来源时，第一节必须增加 `引用需求资料`：列出已读取的关键引用、未读取但已登记的非关键引用，以及 TAPD 链接的上下文和读取状态。
- 混合来源必须同时列出原始钉钉链接和整理后文档，标明主依据、补充依据和冲突处理结论。
- 前后端同时生成时，两份方案必须引用同一主需求依据，并分别记录 `implementation_surface=fullstack`。
- 纯对话确认来源指没有钉钉链接、没有本地方案、也没有已整理需求文档，只通过对话确定需求。此时在生成完成态技术方案前，必须先询问是否整理为需求文档：
  - `整理为需求文档`: 先生成或更新 `需求收集单` 和 `需求清单`，再在技术方案中引用这些文档。
  - `不整理，按对话确认推进`: 技术方案第一节写明 `需求依据：对话确认（用户确认不整理需求文档）`。
  - `暂停，补充需求材料`: 保持待确认，不输出完成态技术方案，不推荐进入实现或 cg-gen。
- 如果询问是否整理为需求文档，仍遵守输出顺序：先列已生成文件或可用摘要，再列待确认问题，最后给用户选择。
- 不新增必填 `RequirementContext` 机器字段；在默认交接摘要中补充可读的需求依据路径或链接即可。

设计约束：
- `需求理解校准` 未确认、且用户未明确同意按命名假设推进时，不要生成完成态技术方案。
- `implementation_surface=unknown` 且影响是否生成前端/后端方案时，不要生成完成态技术方案。
- 涉及端的项目路径缺失时，不要把方案落到错误端项目；只能输出预览并进入待确认。
- 通用模板叙述不要包含具体项目名。
- 新增或改造 API 时，包含 URL、Method、Auth、请求字段、响应字段和错误码映射。
- API 写数据、触发副作用、跨服务或外部消费时，补充幂等、超时/重试、请求示例和响应示例。
- 既有 API 改造优先写变更 diff，避免重复全量结构。
- 先用直白语言说明，只有编码需要时才保留技术术语。
- 只有识别到复杂逻辑信号时，才输出信号、推荐选择，并让用户选择是否命中复杂逻辑。未识别到复杂逻辑信号时，不额外打断用户，在技术方案中记录 `复杂逻辑信号：未识别；是否命中复杂逻辑：否（按简单需求处理）`。
  - `是`: 在接口/数据细节前包含 `场景清单`。
  - `否`: 跳过完整场景表，但记录用户不按复杂逻辑处理的原因；简单需求不得输出空场景表。
  - `不确定`: 将不确定性记录到 `待确认事项`；若影响范围、数据写入、接口行为、时间规则、权限或验收，技术方案保持待确认。
- 技能可以推荐 `是` 或 `否`，但识别到复杂逻辑信号时，最终 `是否命中复杂逻辑` 必须来自用户选择。
- 用户选择 `是否命中复杂逻辑=是` 时，先输出已识别场景覆盖，再询问是否需要补充场景：
  - `不需要补充`: 使用当前 `场景清单` 继续。
  - `需要补充`: 收集补充场景或缺失分支，更新 `场景清单` 后继续。
  - `不确定`: 将场景缺失风险记录到 `待确认事项`；若影响范围、数据写入、接口行为、时间规则、权限或验收，技术方案保持待确认。
- 在技术方案中记录用户选择为 `复杂逻辑命中确认`。
- 在技术方案中记录场景补充结果为 `场景补充确认`。
- 在 `风险评估` 前包含 `影响范围`。
  - 如果提供了 `project_root` 且已扫描代码，引用真实代码证据。
  - 未扫描代码时，将影响范围标记为 `基于需求推断，未做代码扫描验证`；不要声称来自真实代码证据。
- 主体设计后增加简洁的 `风险评估`。仅风险较高时才使用风险分级表。

#### 6.5.1) 轻量方案生成自检（完成态前必须）
技术方案落盘前必须执行轻量自检，并在方案末尾或交接摘要中记录。自检只覆盖能决定方案是否可直接实施的核心项：

| 自检项 | 通过标准 |
| --- | --- |
| 需求上下文是否清楚 | 目标、范围、验收、关键约束已能支撑实现；缺口已记录。 |
| 实施端是否完整 | 已判断 `backend` / `frontend` / `fullstack`，涉及端方案均已生成或明确为预览待补目录。 |
| 核心代码声明是否已验证 | 影响实现的接口路径、DTO、Service、表字段、数据来源、关联键、导出能力已按 5.7 标注 `confirmed` / `refuted` / `unverified`。 |
| 数据链路 / 接口契约是否闭环 | 读写来源、关联键、排序/时间规则、请求字段、响应字段、兼容策略能串起来；无法串起来的点已进入待确认。 |

完成态门禁：
- 任一核心项为否，且影响实现范围、数据正确性、接口契约或核心数据链路时，设置 `technical_plan_status=pending`，不推荐直接实施或进入 `cg-gen`。
- 待确认事项必须说明需要补齐的证据或决策，例如“确认需求部门取 `purchaseDepartmentCode` 还是 `internalDepartmentCode`”。
- 权限、日志、回滚、测试覆盖暂不作为本阶段硬门禁，可作为非阻塞建议记录。

输出必须保持可直接实施，也可供 cg-gen 映射实现；涉及端的方案文件都生成后，才允许推荐直接实施或进入 cg-gen。

## 复杂逻辑场景规则
复杂逻辑信号（技能只给建议，最终由使用者选择 `是否命中复杂逻辑`）:
- 多种状态流转
- 多个判断分支
- 异常处理会影响业务结果
- 异步处理或最终一致性
- 第三方对接
- 权限差异
- 批量处理
- 多来源合并、初始化、补录、迁移、历史复刻、兜底取值

`场景清单` 固定字段：
- `场景ID`
- `什么时候发生`
- `当前状态`
- `输入内容`
- `怎么处理`
- `处理结果`
- `异常情况`
- `怎么验证`

场景拆分方法：
- 先找会改变结果的维度：来源类型、来源是否存在、时间顺序、第一条/最新一条、初始化、重放、兜底、跳过。
- 按结果拆分：如果 `是否写入`、`写入类型`、`写入值`、`时间取值` 或 `处理结果` 不同，使用独立场景。
- 补充边界场景：同一时间排序、空值/非法值、目标记录已存在、重复执行、来源冲突、兜底时间不确定。

场景质量门禁：
- 不要只列来源、角色或状态；必须写判断条件、处理动作、结果和验证点。
- 规则提到 `第一条`、`最新一条`、`早于`、`晚于` 或 `按时间线复刻` 时，场景里必须写时间规则。
- 规则提到 `初始化`、`补录`、`迁移` 或 `兜底` 时，说明重复执行如何避免重复生成。
- 存在兜底逻辑时，说明值来源、时间来源和验证方法；不要默认使用脚本执行时间。

存在场景清单时，`实施映射` 必须引用相关 `场景ID`，供直接实施或 cg-gen 消费。

## 输出契约
用户可见内容优先使用中文。少量机器交接字段可以保留英文，但必须在字段说明或标题里给出中文含义，例如 `source_completeness（来源完整性）`。

默认展示规则：
- 普通用户首先关心“生成了什么文件、还差什么确认、下一步怎么做”。因此用户可见输出必须先展示已生成文件/内容，再展示待确认事项和确认问题。
- 完整 `RequirementContext` 是机器交接元数据，不是默认用户内容。只有在以下情况才展示完整 YAML，且必须放在回复最后：
  - 用户明确要求查看交接元数据；
  - 准备把结果交给 `cg-gen` 或作为实施交接；
  - 调试、复盘或失败诊断需要完整字段。
- 未展示完整 YAML 时，改用一行 `交接摘要`，例如：`需求收集：已完成；技术方案：待确认；来源完整性：部分，存在 2 个阻塞缺口`。

来源完整性门禁：
- `source_completeness=complete` 表示已按当前 MCP 能力读完所需来源，且没有影响需求理解或实现决策的已知来源缺口；非关键图片/附件未完整校验时，需在资源清单标注“未校验，不作为需求依据”，不单独导致 partial。
- `source_completeness=partial` 时，必须填写 `source_gaps`、`blocking_source_gaps` 和 `source_gap_approval`。
- 只有 `blocking_source_gaps` 为空，或用户明确同意按命名假设/缺口推进时，才能生成完成态技术方案。
- `blocking_source_gaps` 非空且未获用户授权时，必须保持 `technical_plan_status=pending`，不要推荐进入实现或 cg-gen。
- 关键资源或重要性未知资源未恢复时，不能通过“放弃”消除缺口；用户选择“按已记录缺口继续，但保留来源不完整风险”后，只能把 `source_gap_approval` 设为 `approved`，`source_completeness` 仍保持 `partial`，并在技术方案第一节 `需求依据` 写明来源不完整风险。

### 待确认输出
适用于来源读取和需求抽取成功，但仍有必要确认项的情况。

输出顺序：
1. `已生成内容`（需求清单、需求收集单、原始需求留存单、后端技术方案、前端技术方案等实际生成路径；如未落盘则给摘要）
2. `待确认事项`（只列会影响范围、写入、接口、时间规则、权限或验收的问题）
3. `请你确认`（给出清晰选项或需要补充的信息；关键资源缺口只能给 `继续尝试恢复资源`、`我补充原图/导出包/授权后重试`、`按已记录缺口继续，但保留来源不完整风险`，不能给“放弃”）
4. `交接摘要`（默认一行摘要；完整 `RequirementContext` 仅按默认展示规则放在最后）

待确认上下文：
```yaml
RequirementContext:
  source_type: "dingtalk" | "local_plan" | "mixed" | "conversation"
  dingtalk_resolution: "url" | "name" | null
  requirement_title: string
  implementation_surface: "backend" | "frontend" | "fullstack" | "unknown"
  current_project_role: "backend" | "frontend" | "fullstack" | "unknown" | null
  backend_project_root: string | null
  frontend_project_root: string | null
  backend_plan_status: "generated" | "preview_only" | "pending" | null
  frontend_plan_status: "generated" | "preview_only" | "pending" | null
  需求理解状态: "pending"
  图片资料清单: string[]
  附件资料清单: string[]
  source_completeness: "complete" | "partial"
  source_gaps: string[]
  blocking_source_gaps: string[]
  source_gap_approval: "not_needed" | "approved" | "pending"
  requirements_stage_gate: "captured" | "pending"
  technical_plan_status: "pending"
  fetch_status: "success" | "fallback_to_name" | "awaiting_requirement_name" | "partial_with_gaps"
  missing_fields: string[]
```

### 完成输出
仅在需求收集完成且技术方案已生成后使用。

响应顺序：
1. `技术方案预览`（按涉及端展示后端方案、前端方案或两者预览）
2. `落盘结果`（需求清单、需求收集单、后端技术方案、前端技术方案等实际生成路径 + 写入状态；如创建原始留存也给出路径）
3. `下一步建议`（是否可以直接实施或进入 cg-gen，以及推荐入口）
4. `交接摘要`（默认一行摘要；完整 `RequirementContext` 仅按默认展示规则放在最后）

完成上下文：
```yaml
RequirementContext:
  source_type: "dingtalk" | "local_plan" | "mixed" | "conversation"
  dingtalk_resolution: "url" | "name" | null
  requirement_title: string
  implementation_surface: "backend" | "frontend" | "fullstack"
  current_project_role: "backend" | "frontend" | "fullstack" | "unknown" | null
  backend_project_root: string | null
  frontend_project_root: string | null
  backend_plan_status: "generated" | null
  frontend_plan_status: "generated" | null
  需求理解状态: "confirmed" | "assumptions_recorded"
  本地方案路径列表: string[]
  需求清单路径: string
  原始需求文件路径: string | null
  需求收集单路径: string
  后端技术方案路径: string | null
  前端技术方案路径: string | null
  图片资料清单: string[]
  附件资料清单: string[]
  source_completeness: "complete" | "partial"
  source_gaps: string[]
  blocking_source_gaps: string[]
  source_gap_approval: "not_needed" | "approved"
  requirements_stage_gate: "captured"
  technical_plan_status: "generated"
  fetch_status: "success" | "fallback_to_name"
  missing_fields: string[]
```

### 失败输出
适用于来源读取失败，或需求资料已落盘但技术方案生成/落盘失败的情况。失败态必须独立输出，不要伪装成待确认或完成态。

输出顺序：
1. `失败原因`
2. `已完成内容`（如有）
3. `下一步需要输入`
4. `交接摘要`（默认一行摘要；完整 `RequirementContext` 仅按默认展示规则放在最后）

失败上下文：
```yaml
RequirementContext:
  source_type: "dingtalk" | "local_plan" | "mixed" | "conversation"
  dingtalk_resolution: "url" | "name" | null
  requirement_title: string | null
  implementation_surface: "backend" | "frontend" | "fullstack" | "unknown" | null
  current_project_role: "backend" | "frontend" | "fullstack" | "unknown" | null
  backend_project_root: string | null
  frontend_project_root: string | null
  backend_plan_status: "generated" | "preview_only" | "pending" | null
  frontend_plan_status: "generated" | "preview_only" | "pending" | null
  failure_reason: string
  failed_source: string
  next_inputs: string[]
  source_completeness: "partial"
  source_gaps: string[]
  blocking_source_gaps: string[]
  source_gap_approval: "pending"
  requirements_stage_gate: "failed" | "captured"
  technical_plan_status: "pending" | "failed"
  fetch_status: "failed" | "success" | "fallback_to_name"
  missing_fields: string[]
```

失败规则：
- 来源读取失败时，设置 `fetch_status=failed`、`requirements_stage_gate=failed`、`technical_plan_status=pending`，不生成技术方案。
- URL 读取失败且缺少 `requirement_name` 时，设置 `fetch_status=awaiting_requirement_name`，进入待确认输出。
- 需求文档已落盘但任一已知项目路径的涉及端技术方案生成/落盘失败时，保留 `requirements_stage_gate=captured`，设置 `technical_plan_status=failed`，不要推荐进入实现或 cg-gen。
- 一端已落盘、另一端缺目录时，设置 `technical_plan_status=pending`，不要当作失败；`missing_fields` 写入 `backend_project_root` 或 `frontend_project_root`。
- 只有同时满足 `requirements_stage_gate=captured`、`technical_plan_status=generated`、涉及端方案文件都存在，且没有未授权的 `blocking_source_gaps` 时，才推荐直接实施或进入 cg-gen。

## 交接与使用
完成时：
- 先输出技术方案预览和落盘结果。
- 默认输出一行交接摘要；只有准备交给 cg-gen、作为实施交接、用户要求或调试需要时，才在最后输出完整 `RequirementContext`。
- 仅在以下条件满足时推荐直接实施或进入 cg-gen：
  - `requirements_stage_gate=captured`
  - `technical_plan_status=generated`
  - `blocking_source_gaps=[]`，或 `source_gap_approval=approved`
  - `需求收集单路径` + `需求清单路径` + 涉及端方案路径都存在，保证可追溯；预览态方案不满足完成交接。
- 本技能不修改代码、不直接生成实现。
- 直接实施时，以已落盘技术方案为主依据；使用 cg-gen 时，cg-gen 应优先消费已落盘的后端/前端技术方案，再把 `RequirementContext` 作为元数据使用。

## 参考文件使用
需要行为示例时读取 [references/cases.md](references/cases.md)。
生成后端技术方案时读取 [references/tech-template.md](references/tech-template.md)。
生成前端技术方案时读取 [references/frontend-tech-template.md](references/frontend-tech-template.md)。
