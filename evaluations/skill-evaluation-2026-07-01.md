# GitHub Skill 评估报告

评估日期：2026-07-01

目标仓库：

- https://github.com/kangarooking/cangjie-skill
- https://github.com/LearnPrompt/ai-news-radar/blob/master/skills/ai-news-radar/README.md
- https://github.com/abxxvrv/spacex-ppt-skill
- https://github.com/crazyykhllc-bit/CyberPPT
- https://github.com/hugohe3/ppt-master

检查过程与快照：`/Users/cm/Documents/me/skill_check`

## 总结建议

如果只选一个“可长期使用的 PPT 生产 skill”，优先看 `hugohe3/ppt-master`。它是完整工程系统，能生成真正可编辑 PPTX，也有模板、图片、音频、SVG 到 PPTX 等链路，但体积和复杂度最高。

如果你要“咨询风格 PPT 的流程门禁和质量约束”，`CyberPPT` 很有价值，但当前 `SKILL.md` 带 UTF-8 BOM，官方 `quick_validate.py` 严格校验失败，安装前建议先去掉 BOM。

如果你只想快速做 SpaceX 风格视觉稿，`spacex-ppt-skill` 简洁好用，但它输出 HTML/PDF/PNG，不是可编辑 PPTX。

如果目标是 AI 新闻雷达和信源治理，`ai-news-radar` 是这批里工程闭环最完整的垂直 skill。

如果目标是“把书、长视频、播客蒸馏成可调用 skill”，`cangjie-skill` 方法论完整，适合作为元 skill，不适合作为直接产出型工具。

## 综合评分排序

| 排名 | Skill | 综合评分 | 推荐级别 | 最适合场景 |
|---:|---|---:|---|---|
| 1 | `ai-news-radar` | 88/100 | 强推荐，垂直场景 | AI 新闻雷达、信源接入、GitHub Pages 自动更新 |
| 2 | `ppt-master` | 86/100 | 推荐，但需接受复杂度 | 通用、可编辑、可复用模板的 PPTX 生产 |
| 3 | `cangjie-skill` | 82/100 | 推荐，元 skill | 把书/长内容蒸馏成一组可调用 skills |
| 4 | `CyberPPT` | 80/100 | 修 BOM 后推荐 | 咨询风格 PPTX 的流程、门禁、QA |
| 5 | `spacex-ppt-skill` | 72/100 | 条件推荐 | SpaceX 风格 HTML/PDF/PNG 视觉 deck |

说明：评分按“作为 Codex/Agent skill 的可安装性、可执行性、质量闭环、维护风险和场景匹配度”综合判断。若只看 PPT 生产场景，`ppt-master` 优先于 `ai-news-radar`。

## 逐项评估

### 1. kangarooking/cangjie-skill

定位：元 skill，用 RIA-TV++ 流程把书、长视频、播客、访谈等内容蒸馏成多个可调用 skill。

优点：

- 官方 `quick_validate.py` 通过。
- 结构清晰：`SKILL.md`、`methodology/`、`extractors/`、`templates/` 都比较完整。
- 有明确质量门：三重验证、RIA++、Zettelkasten、压力测试、`test-prompts.json`。
- 适合沉淀方法论，不只是做摘要。

主要风险：

- 没有自动化脚本，执行质量依赖 agent 严格遵守流程。
- 对输入材料要求高，长内容需要先解决转写、分段、证据定位。
- 产物是否真的“可调用”需要后续实际测试，不是仓库本身能保证。

建议：适合安装为“知识蒸馏工作流”。如果要批量拆书，先用一本材料试跑并保存 `test-results.md`，不要直接批量化。

### 2. LearnPrompt/ai-news-radar - skills/ai-news-radar

定位：AI 新闻雷达/信源治理 skill，帮助分类、接入、验证 RSS/OPML/GitHub feeds/Newsletter 等来源，并部署静态日报。

优点：

- 官方 `quick_validate.py` 通过。
- 不只是 prompt：仓库有真实站点、数据产物、GitHub Actions、测试、文档和 source-intake 方法。
- 安全边界写得清楚：API key、cookies、邮箱正文、私有 OPML 不应提交。
- `scripts/update_news.py` 语法检查通过；仓库已有较完整 pytest 测试集合。

主要风险：

- 完整使用依赖 fork、GitHub Pages、Actions，属于“小产品”而不只是 skill。
- 进阶源如 X、TikHub、AgentMail 需要密钥和预算控制。
- 用户若只想“读新闻”，不需要安装维护侧 `ai-news-radar`，可以用消费侧雷达或在线页面。

建议：如果你要维护自己的 AI 情报源，值得用。验收重点放在 `source-status.json`、`latest-24h.json`、Actions 更新链路，而不是只看 Skill 是否触发。

### 3. abxxvrv/spacex-ppt-skill

定位：生成 SpaceX 风格高视觉冲击 deck，HTML 幻灯片渲染为 PDF 和逐页 PNG。

优点：

- 官方 `quick_validate.py` 通过。
- skill 目录小，结构直接：`SKILL.md`、设计系统、HTML 模板、图片抓取、渲染脚本。
- `fetch_images.py` 和 `render_deck.py` 语法检查通过。
- 风格约束明确，适合做统一视觉风格的演示稿。

主要风险：

- 明确不是可编辑 `.pptx`。如果交付物要求 PowerPoint 可编辑，这个不合适。
- 图片抓取依赖 Pexels API key；仓库支持 `scripts/pexels_key.txt`，实际使用时要避免把 key 放进会被同步/提交的位置。
- Headless Chrome、字体、图片质量会影响最终渲染。

建议：用于快速做视觉型 PDF/PNG deck 很合适；不要把它当通用 PPTX skill。若要进内部交付流，最好加一层“是否必须可编辑”的触发判断。

### 4. crazyykhllc-bit/CyberPPT

定位：高密度、可编辑、咨询风格 PowerPoint 生产流程，强调 SCR、证据表、ImageGen 蓝图、逐页验收、PPTX 严格 QA。

优点：

- 流程门禁非常强：证据分析、故事线、视觉系统、PPTX 生成、PowerPoint 打开导出、manifest、visual QA 都有明确要求。
- 自带 `validate_pptx.py` 和单测，实际运行 `scripts/test_validate_pptx.py`：30 tests passed。
- 对“主要文字必须可编辑”“不能整页截图冒充 PPTX”“不能用 python-pptx 作为正式生成引擎”等风险约束很明确。

主要风险：

- `SKILL.md` 开头有 UTF-8 BOM，官方 `quick_validate.py` 报 `No YAML frontmatter found`。安装前应修复。
- `SKILL.md` 很长，执行成本高；真实做一份 PPT 需要多轮确认、逐页制作和渲染 QA。
- 对 ImageGen、PptxGenJS、PowerPoint/LibreOffice 渲染能力都有隐含依赖。
- 强流程适合高价值交付，不适合快速草稿。

建议：修复 BOM 后适合保留为“咨询式 PPTX 严格工作流/QA skill”。如果已有 `ppt-master`，可以把 CyberPPT 的门禁思想作为补充，而不是两个都无脑触发。

### 5. hugohe3/ppt-master

定位：完整 PPT 生成系统，从资料解析、风格确认、SVG 构建、图片生成/搜索、模板复刻、动画、旁白到原生 PPTX 导出。

优点：

- 官方 `quick_validate.py` 通过。
- 能输出真正可编辑 `.pptx`，不是截图型 deck。
- 工程资产最丰富：大量脚本、模板、图标、参考文档、示例、确认 UI、图片/音频后端。
- `skills/ppt-master/scripts` 下 Python 脚本语法级编译全部通过。
- 有中英文文档，适合长期维护和复杂演示生产。

主要风险：

- 仓库体积很大：全仓库约 1.3G，skill 目录约 96M。安装、同步、上下文读取都需要控制范围。
- 复杂度高，依赖多；很多能力是可选后端，需要正确配置 API key、本地字体、浏览器/Office 相关工具。
- `SKILL.md` 很长，agent 容易在长任务中漂移；需要依赖其“分阶段、确认、重读 spec”的规则。
- 对快速一次性小 PPT 来说可能过重。

建议：作为主力 PPT skill 值得安装，但要配套使用“项目目录 + 明确阶段 + 每阶段验收”的工作方式。若只要 5 页草稿或视觉 PDF，优先用更轻的方案。

## 安装优先级

按用途建议：

| 用途 | 优先选择 | 备选 |
|---|---|---|
| 通用可编辑 PPTX | `ppt-master` | `CyberPPT` 修复后 |
| 咨询风格高质量 PPTX | `CyberPPT` 修复后 | `ppt-master` |
| 快速视觉 PDF/PNG deck | `spacex-ppt-skill` | `ppt-master` |
| AI 新闻雷达 | `ai-news-radar` | 无直接同类 |
| 长内容蒸馏成 skill | `cangjie-skill` | 无直接同类 |

## 修复建议

1. `CyberPPT`：去掉 `SKILL.md` 文件开头 BOM，再跑 quick_validate。
2. `spacex-ppt-skill`：把 Pexels key 放环境变量，不建议写入 skill 目录里的 `pexels_key.txt`。
3. `ppt-master`：不要全仓库无差别读入上下文；使用时按 workflow 读取相关 reference。
4. `ai-news-radar`：进阶源默认关闭，所有密钥只放 GitHub Secrets 或本地环境变量。
5. `cangjie-skill`：首次使用时必须保留验证产物，尤其是 `test-prompts.json` 和失败回炉记录。

## 结论

这批 skill 里没有明显“完全不能用”的仓库。真正需要区分的是目标：

- 要做 PPT 主力生产：选 `ppt-master`。
- 要做咨询式质量门禁：修复后选 `CyberPPT`。
- 要做风格化视觉稿：选 `spacex-ppt-skill`。
- 要做 AI 新闻雷达：选 `ai-news-radar`。
- 要做知识/方法论蒸馏：选 `cangjie-skill`。
