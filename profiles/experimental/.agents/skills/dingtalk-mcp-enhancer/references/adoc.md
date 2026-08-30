# 钉钉文档 adoc 配方

## 读取

1. `get_document_info` 确认 `ALIDOC/adoc`。
2. `get_document_content(format=markdown)` 读取正文；精确结构、图片、附件或样式再读取 `list_document_blocks`、JsonML 和 `get_document_style`。
3. 默认覆盖完整正文；分页或响应裁剪时继续读取并在 `gaps` 说明缺口。
4. Markdown 缺内容时按 [diagnostics.md](diagnostics.md) 的结构恢复阶梯处理。

## 创建与修改

- 新建：`create_document`，随后读元信息和正文。
- 追加：`update_document(mode=append)`；用唯一 marker 验证新内容且旧内容仍在。
- 指定位置插入：刷新 block 列表后传明确 index。
- 精确修改：从最新 block 列表取得 blockId，再用 `update_document_block`。
- 全文覆盖：先 `save_doc_version`，展示影响并确认，再显式 `mode=overwrite`；覆盖后同时核对正文和结构。
- 单次正文遵守当前 schema 长度限制；历史实测单次 10000 字符。长内容分块时逐块回读，记录最后稳定 marker。

## 图片、附件和样式

1. 校验本地文件实际 MIME、字节数和 SHA-256，再调用 `get_doc_attachment_upload_info`，只使用这次准备响应的短时凭证。
2. 宿主具备不记录凭证的传输能力时立即 PUT；否则停止并返回 `partial`，丢弃这次准备响应，后续恢复安全通道时重新 prepare。
3. 历史稳定附件 block 使用最小字段 `name + resourceId`；额外字段按当前 schema 在隔离 block 最小复测。
4. 封面使用 `update_document_style(resourceId)`，用 `get_document_style` 回读。
5. 正文图片写入上传后的内部资源 URL，再用 JsonML 证明存在原生 `img` 节点；临时上传 URL 不得进入正文或报告。
6. 下载附件先用 `download_doc_attachment` 准备，随后遵守同样的短时凭证边界并校验大小、MIME 和 SHA-256。

## 导入、文件和导出

- 导入：`create_import_session` → 安全 PUT → `confirm_import` → `query_import_task`。
- 通用文件：`get_file_upload_info` → 安全 PUT → `commit_uploaded_file`；覆盖必须指明 `overwriteNodeId` 并确认。
- 导出：`submit_export_job` → 用真实 jobId 有界调用 `query_export_job`；不伪造任务 ID，不输出临时下载地址。
- 异步任务只按返回 ID 查询；不因等待而重复创建。

## 历史线索

- 附件 element 的显式 `size` 曾被错误序列化，`viewType=card` 曾触发枚举错误；当前正式写入优先使用最小稳定字段，并以当前 schema 为准。
- 全文覆盖曾首次超时且未生效；先读 marker 和旧内容，只有证明未生效时才允许一次有证据重试。
- 权限、所有权、移动、公开分享和版本回滚属于高影响操作，必须先做影响预览和确认。
