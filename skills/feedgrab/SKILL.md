---
name: feedgrab
description: 抓取并读取网页、社交平台、视频、RSS、论坛和文档链接，返回带来源与失败状态的结构化内容；适用于用户说“抓取、读取、采集、批量抓链接”或直接提供 URL 的场景。
x-provenance: local
x-owner: cm
x-source-note: created from local workflow
---

# Feedgrab 信息抓取

把 URL 或 URL 列表交给 feedgrab，完成平台识别、内容抓取、Markdown 产物保存和结果回读。这个 Skill 只负责获取与整理原文；用户要求总结、分析或改写时，在真实抓取成功后再进入对应的内容处理流程。

## 运行前检查

先检查 CLI 是否存在：

```bash
command -v feedgrab
```

如果不存在，停止抓取并给出安装命令；不要用“页面能打开”替代 feedgrab 的真实结果：

```bash
python3 -m pip install "feedgrab[all] @ git+https://github.com/iBigQiang/feedgrab.git"
feedgrab setup
feedgrab doctor
```

安装后重新检查 `command -v feedgrab`。需要浏览器、字幕或私有内容时，再按 `feedgrab doctor <platform>` 的结果处理登录或可选依赖。

## 选择调用方式

- 当前 Codex 浏览器可用且用户要求读取网页时，优先用 Codex 浏览器打开 URL 并回读页面正文；需要登录时沿用当前浏览器登录态。浏览器登录态不会自动写入 feedgrab 的 `sessions/*.json`，不能把浏览器已登录推断为 CLI 已登录。
- 单个 URL：`feedgrab "<url>"`
- 多个 URL：`feedgrab "<url1>" "<url2>" ...`；CLI 会并发处理并逐项报告失败。
- 用户明确说“批量、搜索、全部、收藏、作者文章、知识库”：读取 [references/batch.md](references/batch.md)，使用仓库对应的专用命令。
- 用户说“从剪贴板抓取”：使用 `feedgrab clip`，不要把含 `&` 的 URL 直接拼进 shell。
- 用户要求平台登录、刷新 Cookie 或诊断：先运行只读的 `feedgrab doctor`；只有用户明确要求登录时才运行 `feedgrab login <platform>`。

始终把用户提供的 URL 作为一个完整 shell 参数传入，避免 `&`、`?`、`#` 等字符被 shell 解释。

## 结果验收

1. 记录 CLI 的退出码和 stdout/stderr；退出成功不等于内容完整。
2. 从 CLI 输出或 `OUTPUT_DIR` 中定位实际生成的 `.md` 文件。默认输出目录是 `./output/`，平台通常位于 `output/<Platform>/`。
3. 读取生成的 Markdown，确认至少有来源 URL、标题或正文；若只有错误信息、空文件或登录提示，标记为失败/需认证。
4. 向用户返回：抓取状态、平台、标题、来源 URL、产物绝对路径，以及必要的正文或摘要。批量任务逐项列出成功和失败，不把部分成功写成全部成功。
5. 对 401/403、429、Cookie 过期、浏览器未启动、Jina 超时、缺少 API Key 等错误，保留原始错误类别并给出下一步；不要猜测正文，也不要用搜索摘要冒充原文。

## 输出约定

优先返回结构化 JSON 或 Markdown 中的明确字段：`title`、`url/source`、`author`、`published`、`content`、`platform`、`artifact_path`、`status`。对于 CLI 只打印标题而没有正文的情况，必须继续读取产物文件再回答。

通过 Codex 浏览器读取的内容，使用 `extracted_via: Codex 浏览器` 标记并保存为本地 Markdown；通过 feedgrab CLI 读取的内容，保留 CLI 生成的 artifact 路径。两种结果分别报告来源和认证状态。

## 图片内容识别

feedgrab 的图片下载和图片理解是两个阶段：

1. 先取得原图资源。CLI 模式在已有平台登录态时可设置 `XHS_DOWNLOAD_MEDIA=true`，图片会保存到 Markdown 所在目录的 `attachments/`；Codex 浏览器模式优先读取页面中的原图资源，只有拿不到原图时才使用放大后的页面截图。
2. 再把每张本地图片作为视觉输入交给模型，按图片序号保留来源和页码。下载图片本身不会产生 OCR 或图像理解结果。
3. 对小图、模糊图、遮挡图或只拿到缩略图的情况，标记“图片文字未完全验收”，不要补写看不清的文字。

GitHub README 中的相对图片链接可以由 feedgrab 补全为 raw GitHub URL，但 GitHub 抓取器同样只负责取得图片链接或保存图片，不自动理解图片内容。

默认不下载媒体、不执行发布、不修改远端内容。只有用户明确要求下载图片/视频、登录或写入指定知识库时，才启用对应选项，并在结果中说明实际产物和未验证部分。

## 支持范围

feedgrab 会自动识别并路由到 X/Twitter、微信公众号、小红书、YouTube、B 站、GitHub、Telegram、RSS、Discourse、飞书、金山文档、知乎、Reddit 等平台；未匹配的平台走通用网页读取。平台能力、登录要求和环境变量以当前安装版本的 `feedgrab doctor` 与官方仓库为准。

## 失败边界

- `feedgrab` 未安装：只报告安装阻塞，不自行改写为另一套抓取器。
- 需要登录而当前没有认证：报告需要登录的平台和命令，不把空结果解释为“没有内容”。
- 生成了文件但正文为空、被截断或仅有错误：标记“产物已生成但内容未验收”，并保留路径。
- 多 URL 中有部分失败：按 URL 分项报告，保留成功项，不重试无关项。
