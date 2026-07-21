# PPT Profile

这个 profile 面向正式 PPT / HTML 演示稿生产。`technical-html-deck` 是唯一默认生产入口；其它 Skill 是按需执行器。

## Included Skills

| Skill | 角色 | 使用边界 |
| --- | --- | --- |
| `technical-html-deck` | 技术 PPT/HTML 总控 | 负责事实、派生数据、叙事、风格、`diagram_spec`、renderer 路由和最终 QA |
| `drawio-skill` | 可编辑技术图 renderer | 需要 `.drawio`、人工接手或长期维护时调用；不自行决定事实 |
| `fireworks-tech-graph` | 语义 SVG renderer | C4、云部署、事件流、可观测性等高完成度 SVG；不自行决定事实 |
| `gpt-image2-ppt` | 视觉增强 renderer | 仅用于封面、章节、氛围和视觉隐喻，不承载精确技术关系 |
| `html-ppt` | 静态 HTML renderer | 总控完成 plan/spec 后按需调用 |
| `ppt-master` | 可编辑 PPTX renderer | 用户明确需要 PowerPoint 原生编辑时调用 |
| `image-to-editable-ppt` | 转换执行器 | 图片、PDF、扫描 deck 重建为可编辑 PPTX |

原 `cm-presentation-style` 的视觉规范、内外部模式、tokens、scorecard 和静态评分脚本已内置到 `technical-html-deck`，不再作为并列控制 Skill。

## Default Flow

```text
technical-html-deck
  -> claim_ledger + slide_plan + style_brief
  -> diagram_spec.json
       -> native HTML/SVG       (简单图)
       -> drawio-skill          (可编辑交接)
       -> fireworks-tech-graph  (语义 SVG)
  -> HTML/PPTX renderer
  -> desktop/mobile screenshots + semantic/style QA
```

技术图 renderer 默认不隐式触发。用户明确点名，或 `technical-html-deck` 完成 `diagram_spec.json` 后，才调用对应分支。

## Installation

在目标项目根目录从 GitHub source 安装完整 profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装总控：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

本地路径安装只用于验证未推送改动：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/Me/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

## Runtime Notes

- `drawio-skill` 的 `.drawio` 生成和结构校验可独立工作；本地导出需要 draw.io Desktop，复杂自动布局可选 Graphviz。
- `fireworks-tech-graph` 的 SVG 主路径使用 Python；PNG 推荐 CairoSVG。GIF 动效依赖较重，不进入普通 PPT 默认路径。
- 外部 Skill 必须完整安装并保留 `scripts/`、`references/`、schemas/templates 和 LICENSE；只复制 `SKILL.md` 视为安装失败。
- `skills-lock.json` 记录上游安装快照。升级 renderer 时先安装到临时目录并审查 diff，再重新应用本 profile 的窄触发 wrapper 与 `allow_implicit_invocation: false`；不要用上游 `SKILL.md` 直接覆盖本地边界。
- 实验性 PPT Skill 继续放在 `profiles/ppt-lab`，不进入默认入口。
