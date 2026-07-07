# PPT Profile

这个 profile 面向 PPT / deck 生产场景，安装态位于：

```text
/Users/cm/Documents/me/skills/profiles/ppt/.agents/skills/
```

## Included Skills

| Skill | 用途 | 备注 |
|---|---|---|
| `cm-presentation-style` | 个人技术演示稿 / 外部宣传 HTML 演示稿的风格总控、评分表、QA 标准 | 不负责渲染；先用它定模式和质量门槛，再串 `humanize-ppt` / `fireworks-tech-graph` / `html-ppt` |
| `technical-html-deck` | 从技术材料生成可评审 HTML 演示稿的生产线 | 编排 claim ledger、slide plan、diagram spec、HTML 渲染、GPT Image 视觉增强和 QA |
| `cyber-ppt` | 咨询风格 PPTX、SCR、逐页 QA 门禁 | 技术方案评审主推；本地版已去掉 upstream `SKILL.md` BOM |
| `ppt-master` | 通用可编辑 PPTX 生产 | 稳定可编辑稿，流程较重 |
| `gorden-ppt-skill` | 中文模板化 PPTX 生成/编辑 | 模板资源强；registry 风险提示为 High/Critical，真实项目使用前需复核 |
| `guizang-ppt-skill` | 中文网页 PPT / 横向翻页 HTML deck | 适合中文演讲、杂志风、瑞士风 |
| `html-ppt` | 多模板静态 HTML slides | 适合快速 HTML deck 和模板风格探索 |
| `ppt-agent` | 全流程 HTML 演示文稿生成 | registry 风险提示为 Med，适合研究完整流程 |
| `humanize-ppt` | 叙事大纲与渲染后演讲体检 | 编排/QA skill，不是独立 renderer；registry 风险提示为 Critical |
| `codex-ppt` | GPT image 风格统一的图片型 PPTX | 视觉统一但文本/图表不可对象级编辑 |
| `gpt-image2-ppt` | GPT image 2 风格幻灯片图像 + PPTX | 视觉实验候选；依赖图像生成能力 |
| `spacex-ppt-skill` | SpaceX 风格视觉 deck | 输出 HTML/PDF/PNG，不是可编辑 PPTX |
| `ian-handdrawn-ppt` | 中文手绘技术解释页/课件图 | 适合技术科普，不适合作为正式方案主稿 |
| `ppt-svg-generator` | Markdown 到可导入 PPT 的 SVG 页面 | 可在 PowerPoint 中转换为形状后编辑 |
| `image-to-editable-ppt` | 图片/扫描/PDF deck 重建为可编辑 PPTX | 转换类 skill，不用于从零生成新 PPT |

## Usage

方式一：在目标项目根目录创建软链：

```bash
ln -s /Users/cm/Documents/me/skills/profiles/ppt/.agents .agents
```

如果目标项目已经存在 `.agents`，先确认其中是否有项目私有 skill，再决定是否替换。

方式二：用 `npx skills` 复制安装到目标项目：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装单个 skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill ppt-master --yes --copy --full-depth
```

同步更新到目标项目时，重新运行同一条 `add` 命令覆盖安装。当前 `skills@latest` 对本地 profile source 的 `update --project` 不生效。

## Source Snapshot

基础 3 个 skill 来自 2026-07-01 的评估快照；2026-07-03 已追加一批 PPT skill：

```text
/Users/cm/Documents/me/skill_check/source-snapshots/
```

评估报告：

```text
/Users/cm/Documents/me/skills/evaluations/skill-evaluation-2026-07-01.md
/Users/cm/Documents/me/skills/evaluations/ppt-skill-evaluation-2026-07-03.md
```

## Selection Rule

- 个人风格沉淀 / 技术演示稿质量控制 / 外部宣传 HTML 风格控制：先用 `cm-presentation-style`。
- 从原始技术文档、HTML、架构图生成最终 HTML 演示稿：使用 `technical-html-deck`，并让它串 `cm-presentation-style` / `humanize-ppt` / `html-ppt` / `gpt-image2-ppt`。
- 技术方案评审：优先 `cyber-ppt`，备选 `ppt-master` / `gorden-ppt-skill`。
- 中文 HTML 演讲：优先 `guizang-ppt-skill` / `html-ppt`，需要叙事体检时串 `humanize-ppt`。
- 视觉实验或路演：优先 `spacex-ppt-skill` / `gpt-image2-ppt` / `codex-ppt`。
- 图片、PDF、扫描稿转可编辑：使用 `image-to-editable-ppt`。
- SVG 导入 PowerPoint 后再编辑：使用 `ppt-svg-generator`。
