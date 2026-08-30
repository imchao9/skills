# 读取恢复、资源与诊断

## 恢复阶梯

只读路径一次失败不是最终缺口。按顺序尝试：

1. 同一读取或下载最多再试两次；记录尝试，不无限轮询。
2. 换等价路径：文档在 Markdown、JsonML、blocks 之间互补；表格在结构化范围、CSV、单元格信息之间互补。
3. 有 resourceId 时刷新附件凭证；普通文件重新调用 `download_file`。
4. 当前工具和类型支持时使用专用导出路线，并用真实 jobId 有界查询。
5. 区分网络、权限、过期签名、占位图、空内容、解析失败和覆盖不足。

非幂等写入不适用上述多次重试，遵守 `operations.md` 的读回后单次重试规则。

## 文档与分页

- Markdown 恢复正文，JsonML/blocks 恢复结构、card、图片和附件。
- `hasMore`、cursor 或范围返回部分数据时继续分页；记录 totalCount、已读取数量和嵌套缺口。
- `adoc` 可按当前 schema 导出 Markdown/docx/pdf；`axls` 只用表格命名空间导出，`able` 使用其专用数据导出。
- 不伪造 jobId，不用通用导出冒充结构化内容读取。

## OSS、图片和附件

- 下载前不改写或重组签名 query；失败时优先用 resourceId 刷新。
- `noAuth.png`、`403 application/xml`、过期 URL、重复占位图 hash、未下载的关键图片都不是有效证据。
- 关键图片记录 Content-Type、字节数、像素尺寸、sha256 和视觉结论。
- 关键附件记录名称、MIME/扩展名、字节数、sha256 和解析结论。
- 关键图片只有形成与任务相关的视觉结论才算内容覆盖；只验证 MIME、尺寸和哈希时仍是 `partial`。关键附件同理，任务需要其内容时必须完成相应解析。
- 临时文件使用任务专用临时目录；解析压缩包时拒绝绝对路径与 `..`，忽略 `__MACOSX` 和 `.DS_Store`。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `PARTIAL_COVERAGE` | 只覆盖部分 block、sheet、range、table、record 或文件 |
| `EMPTY_RESULT` | 目标存在但请求范围为空或字段未返回 |
| `RESOURCE_EXPIRED` | 临时签名过期 |
| `DOWNLOAD_FAILED` | 下载与刷新恢复均失败 |
| `RESOURCE_NO_AUTH` | 命中无权限占位资源 |
| `RESOURCE_PLACEHOLDER` | 内容、尺寸或 hash 证明是占位图 |
| `EXPORT_FAILED` | 导出失败、超时或产物不可下载 |
| `ROUTE_UNSUPPORTED` | 当前类型没有可靠路线 |
| `PARSE_FAILED` | 文件取得但无法解析 |
| `USER_INPUT_REQUIRED` | 必须由用户授权、提供文件或确认范围 |
| `TARGET_AMBIGUOUS` | 描述无法唯一解析为稳定目标 ID |
| `CONFIRMATION_REQUIRED` | 高影响操作仍缺精确影响预览或明确确认 |
| `ACCESS_STATE_UNVERIFIED` | 分享关闭/更新已有响应，但有界重试后仍无法独立读取最终访问状态 |
| `RESOURCE_STATE_INCONSISTENT` | 目录、详情或子资源归属互相冲突，无法安全据此修改目标 |
| `SAFE_TRANSFER_CHANNEL_UNAVAILABLE` | 宿主无法在任务轨迹、命令历史、进程参数、文件、日志、错误回显和用户输出之外安全承载短时凭证 |

关键内容恢复失败时返回 `partial`；全部路径无可用内容时返回 `failed`。只有非关键资源失败且不参与判断时，可以保持 `complete`，但必须标记“未校验，不作为依据”。
