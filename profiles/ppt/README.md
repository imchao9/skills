# PPT Profile

这个 profile 面向正式 PPT / HTML 演示稿生产链路，安装态位于：

```text
/Users/cm/Documents/me/skills/profiles/ppt/.agents/skills/
```

## Included Skills

| Skill | 用途 | 备注 |
|---|---|---|
| `cm-presentation-style` | 个人技术演示稿 / 外部宣传 HTML 演示稿的风格总控、评分表、QA 标准 | 自研；不负责渲染，负责风格和质量门槛 |
| `technical-html-deck` | 从技术材料生成可评审 HTML 演示稿的生产线 | 自研；编排 claim ledger、slide plan、diagram spec、HTML 渲染和 QA |
| `gpt-image2-ppt` | GPT Image 2 风格幻灯片图像 + PPTX | 视觉增强分支，不作为技术真相层 |
| `html-ppt` | 静态 HTML slides renderer | HTML 演示稿的轻量渲染候选 |
| `ppt-master` | 通用可编辑 PPTX 生产 | 可编辑 PPTX 主力候选，流程较重 |
| `image-to-editable-ppt` | 图片 / PDF / 扫描 deck 重建为可编辑 PPTX | 转换类 skill，不用于从零生成新 PPT |

其它 PPT skill 已移到：

```text
/Users/cm/Documents/me/skills/profiles/ppt-lab
```

## Usage

推荐方式：在目标项目根目录从 GitHub source 安装：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装单个 skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

本地路径安装只用于验证未推送改动：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add /Users/cm/Documents/me/skills/profiles/ppt \
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

## Selection Rule

- 默认 PPT / HTML PPT / 技术演示稿生产：先用 `technical-html-deck` 作为总控，再按需调用 `cm-presentation-style`、`html-ppt`、`ppt-master` 或视觉增强 skill。
- 技术演示稿默认：`technical-html-deck` + `cm-presentation-style`，并执行截图质量门槛，不能只交付能渲染但很丑的页面。
- 视觉增强 / 外宣封面 / 整页图片型 PPTX：`gpt-image2-ppt`。
- 静态 HTML deck：`html-ppt`。
- 可编辑 PPTX：`ppt-master`。
- 图片或 PDF deck 转可编辑：`image-to-editable-ppt`。

实验和对比时再安装 `ppt-lab`。
