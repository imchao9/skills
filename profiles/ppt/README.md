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

方式一：在目标项目根目录创建软链：

```bash
ln -s /Users/cm/Documents/me/skills/profiles/ppt/.agents .agents
```

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
  --agent codex --skill technical-html-deck --yes --copy --full-depth
```

## Selection Rule

- 技术演示稿默认：`technical-html-deck` + `cm-presentation-style`。
- 视觉增强 / 外宣封面 / 整页图片型 PPTX：`gpt-image2-ppt`。
- 静态 HTML deck：`html-ppt`。
- 可编辑 PPTX：`ppt-master`。
- 图片或 PDF deck 转可编辑：`image-to-editable-ppt`。

实验和对比时再安装 `ppt-lab`。
