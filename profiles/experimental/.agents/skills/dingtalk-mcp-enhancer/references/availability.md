# 钉钉 MCP 可用性与安装引导

## 判断顺序

1. 检查当前任务实际可见的工具，不以历史配置代替。
2. 有 URL 时先检查 `get_document_info`；无链接创建时直接检查目标类型的“创建工具 + 独立回读工具”。
3. 工具可见但调用失败时区分权限、参数、网络和服务错误，不引导重复安装。

## 无链接创建

| 目标 | 创建工具 | 必需回读 |
| --- | --- | --- |
| 文档 `adoc` | `create_document` | `get_document_info`, `get_document_content` |
| 表格 `axls` | `create_workspace_sheet` | `get_all_sheets` + 范围读取 |
| AI 表格 `able` | `create_base` | `get_base`, `get_tables` / `query_records` |

没有链接不妨碍创建，也不应要求用户手工创建空资料。用户已明确类型时，保留原始创建意图并补齐名称、位置和内容/schema。

## 稳定错误码

主错误码按已知事实选择：已确认配置存在但当前任务没暴露工具时，优先 `TOOL_NOT_HOT_LOADED`；类型已确认的读取路由缺专用工具时用 `ROUTE_TOOL_MISSING`；无链接创建且无法证明创建/回读工具已安装或启用时用 `CREATE_TOOL_MISSING`；一般核心工具不可见才用 `TOOL_MISSING`。工具可见后的权限或调用错误不再使用“缺工具”类错误码。

| 错误码 | 判断 | 处理 |
| --- | --- | --- |
| `TOOL_MISSING` | 对应核心工具完全不可见 | 引导安装或启用精确 MCP |
| `TOOL_NOT_HOT_LOADED` | 已知配置存在，但当前任务未暴露工具 | 刷新工具列表或重开任务后复验 |
| `ROUTE_TOOL_MISSING` | 类型已确认，但专用 MCP 缺失 | 指出缺少的文档/表格/AI 表能力 |
| `CREATE_TOOL_MISSING` | 创建或必要回读工具缺失 | 安装/启用后从原创建意图继续 |
| `TOOL_CALL_FAILED` | 工具可见但调用失败 | 诊断参数、网络或服务，不重复安装 |
| `AUTH_FAILED` | 返回 401/403/noAuth/无权限 | 请求资源授权，不误报为未安装 |

## 安装与恢复

- 优先使用宿主提供的官方 MCP/连接器安装动作或可信设置入口。
- 没有可调用安装动作时，引导用户打开当前客户端或 Agent runtime 的 MCP 管理界面，安装或启用精确的钉钉文档、钉钉表格或钉钉 AI 表格服务。
- 预期名称可能显示为 `dingtalk-sheet` 或 `dingtalk-ai-table`；最终以当前产品实际工具列表为准。
- 不要求用户在对话中粘贴 key、私有网关 URL、Cookie、Token 或鉴权头。
- 安装或启用后刷新工具列表或重开任务，再从原链接或原创建意图继续。

恢复后只补问当前 schema 必填、或会实质改变业务结果的字段。服务明确提供安全默认位置时可以采用并在结果中说明；位置、初始 schema、同名策略没有可靠默认且会改变结果时再向用户确认。

不能立即恢复时，读取任务按已有内容返回 `partial/failed`；写入任务不得声称完成，并在 `next_actions` 保留缺失工具和续作点。
