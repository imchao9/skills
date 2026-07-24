# Codex Plugins Inventory

来源命令：

```bash
codex plugin list
```

采集时间：2026-07-07。

公司内源 marketplace 于 2026-07-24 单独复核；其来源、升级和验证方法见
[`plugins/cm-tool-marketplace.md`](plugins/cm-tool-marketplace.md)。

## 已安装并启用

| Plugin | Marketplace | Version | 用途 | 保留判断 |
|---|---|---:|---|---|
| `documents` | `openai-primary-runtime` | `26.630.12135` | Word / `.docx` 文档创建、编辑和渲染核验 | 保留 |
| `pdf` | `openai-primary-runtime` | `26.630.12135` | PDF 读取、生成、渲染和检查 | 保留 |
| `spreadsheets` | `openai-primary-runtime` | `26.630.12135` | Excel / CSV / 表格处理 | 保留 |
| `presentations` | `openai-primary-runtime` | `26.630.12135` | PowerPoint / Slides 生成和编辑 | 保留 |
| `template-creator` | `openai-primary-runtime` | `26.630.12135` | 创建可复用 Codex artifact template skill | 保留 |
| `browser` | `openai-bundled` | `26.623.141536` | 控制 in-app browser | 保留 |
| `chrome` | `openai-bundled` | `26.623.141536` | 控制本机 Chrome 登录态和标签页 | 保留 |
| `computer-use` | `openai-bundled` | `1.0.857` | 控制本机 Mac 应用 UI | 保留 |
| `record-and-replay` | `openai-bundled` | `1.0.857` | 录制操作并沉淀为 skill | 保留 |
| `codex-usage` | `codex-usage-local` | `0.1.33` | Codex usage 采集和状态检查 | 保留 |
| `codemao-fullstack-workflow` | `codex-usage-local` | `0.1.21` | 公司全栈交付工作流 skill bundle | 保留 |

## 公司内源 Marketplace

| Marketplace | Canonical source | 当前纳管插件 | 治理文档 |
|---|---|---|---|
| `codex-usage-local` | `git@gitlab.codemao.cn:backend/platform-informatization/tool/cm-tool-marketplace.git` | `codex-usage`、`codemao-fullstack-workflow` | [`cm-tool-marketplace`](plugins/cm-tool-marketplace.md) |

## 已安装但禁用

| Plugin | Marketplace | Version | 用途 | 处理建议 |
|---|---|---:|---|---|
| `vercel-plugin` | `plugins-cli` | `0.42.1` | Vercel 相关插件能力 | 暂时禁用保留，只有明确使用 Vercel 插件时再启用 |

## 可见但未安装

`openai-bundled` 中的 `latex` 当前未安装。

`openai-curated` marketplace 中有大量可选插件当前未安装。

这些未安装插件不进入 skill profile，也不在本文逐项维护。

需要启用某个插件时，先用 `codex plugin list` 或 marketplace 确认版本和用途，再单独记录到本文。
