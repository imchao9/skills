---
name: java-backend-code-review
description: 审查 Java/Kotlin 后端 GitLab MR、分支差异或本地 diff。适用于检查 Spring、MyBatis、Redis、MQ、Feign、事务、SQL、兼容性、敏感数据、Java/Kotlin 空值风险，以及记录或查询审查问题历史。
---

# Java 后端代码审查

## 概览

这个 skill 用仓库感知的固定流程审查 Java/Kotlin 后端改动。先把 MR 或分支差异限定为审查范围，再结合本地代码、临时 worktree、Mapper XML、相关方法、空值高危模式和历史问题记录进行分析。

支持两种主要入口：

1. MR 审查模式：用户提供 MR URL 或 MR IID。
2. 分支对比模式：用户提供源分支和目标分支，例如 `feature/foo` 对比 `master`。

如果用户要求 review 但输入不完整，只问一个简短问题：

- MR 模式：`请把 MR 地址或 IID 发我。`
- 分支对比模式：`请告诉我源分支和目标分支，例如 feature/xxx 对比 master。`
- 模式不明确：`你要我按 MR 审查，还是按源分支对比目标分支审查？`

## 输入

前置条件：

- `git` 必须在 `PATH` 中可用。
- MR 模式和自动发现当前分支 MR 需要 `glab`。
- 如果没有 `glab`，改用显式 `--base` / `--head` 或本地工作区 diff 模式。
- 如果用户想按 MR 模式审查但缺少 `glab`，读取 [references/glab-install.md](references/glab-install.md)。
- 命令示例中的 `SKILL_DIR` 表示当前 `SKILL.md` 所在目录。必须从实际 skill 路径解析，不要硬编码 Codex/Cursor 安装目录。

输入优先级：

1. 显式 GitLab MR URL 或 MR IID
2. 当前分支已打开的 MR
3. 显式 `base..head`
4. 本地工作区 diff

推荐用户表达：

- `帮我 review 这个 MR：https://gitlab.../merge_requests/123`
- `帮我 review MR 123`
- `帮我 review 这个分支，对比 master`
- `帮我 review feature/xxx 对比 release/2026-03`
- `帮我检查这个 diff 的空指针和事务风险`

审查前先运行：

```bash
python3 "$SKILL_DIR/scripts/collect_review_context.py" --help
```

交互式入口：

```bash
# 询问 MR URL 或 IID
bash "$SKILL_DIR/scripts/review_mr.sh"

# 询问源分支和目标分支
bash "$SKILL_DIR/scripts/review_branch.sh"

# 使用临时 Homebrew 国内镜像安装 glab
bash "$SKILL_DIR/scripts/install_glab.sh"
```

历史问题和 findings 命令：

```bash
python3 "$SKILL_DIR/scripts/review_memory.py" --help
```

审查产物命令：

```bash
python3 "$SKILL_DIR/scripts/review_outputs.py" --help
```

GitLab 评论发布依赖 `review_outputs.py publish-gitlab` 和本机 `glab api`。

常用命令：

```bash
# 审查指定 MR
python3 "$SKILL_DIR/scripts/collect_review_context.py" --mr 123

# 交互输入 MR，默认输出到 /tmp/review-context.json
bash "$SKILL_DIR/scripts/review_mr.sh"

# 通过 MR URL 审查
python3 "$SKILL_DIR/scripts/collect_review_context.py" \
  --mr https://gitlab.example.com/group/project/-/merge_requests/123

# 审查已知 commit range
python3 "$SKILL_DIR/scripts/collect_review_context.py" \
  --base origin/master --head HEAD

# 使用 merge-base 对比源分支和目标分支
bash "$SKILL_DIR/scripts/review_branch.sh" feature/my-branch master

# 降级为本地 diff
python3 "$SKILL_DIR/scripts/collect_review_context.py"
```

## 审查流程

0. 先从用户消息识别审查模式。
   - 如果包含 MR URL 或 IID，使用 MR 模式。
   - 如果包含源分支和目标分支，使用分支对比模式。
   - 如果输入不完整，先问缺失信息，不要直接运行 collector。
   - 如果用户想用 MR 模式但缺少 `glab`，读取 [references/glab-install.md](references/glab-install.md)，先给安装或分支对比方案；只有用户明确同意后才安装。
1. 先运行 `scripts/collect_review_context.py`。
2. 手动打开文件前，先读取 JSON 输出。它已经包含：
   - 审查模式
   - MR 元数据
   - 用于记忆记录的仓库身份
   - base/head 引用
   - 原始 diff
   - 变更文件和 hunk
   - 变更方法或 SQL 块
   - 解析到的 1-2 跳相关方法
   - 命中的空值高危模式
   - 未解析符号和歧义说明
3. 如果 `nullability_gotchas_hits` 非空，写 findings 前读取 [references/nullability-gotchas.md](references/nullability-gotchas.md)。
4. 如果审查模式是 `merge_request` 或 `commit_range`，后续读取优先使用 collector 生成的临时 worktree，避免被本地脏改动污染。
5. 如果审查模式是 `working_tree`，直接审查当前仓库状态。

## 范围规则

- 主范围：diff 中的变更 hunk。
- 扩展范围：所在方法或 SQL 块，再向仓库内被调用方法扩展 1-2 跳。
- 如果 diff 触达或直接引用 Mapper XML、迁移 SQL、配置，也要审查。
- 不要无限追调用链。
- 如果方法名解析出多个候选且不能从当前文件或类消歧，记录为歧义，不要虚构绑定。
- 如果代码依赖仓库外部服务、SDK 或生成代码，审查本地调用点并记录剩余风险。

## 审查标准

写 findings 前读取 [references/review-rules.md](references/review-rules.md)。
当 collector 命中空值高危模式，或本次 review 明显涉及 Java/Kotlin 空值风险时，读取 [references/nullability-gotchas.md](references/nullability-gotchas.md)。

关键行为：

- 优先检查正确性、回归风险、兼容性、事务安全、SQL 安全、空值风险和敏感数据问题。
- 旧代码只有在新改动调用它、改变它的假设或依赖它时才算入范围。
- 优先输出高置信 findings，不用弱猜测凑数量。
- 如果数据库 MCP 不可用，写明 `数据库MCP状态: 离线`，只做静态分析。
- 空值问题优先引用具体规则编号，例如 `NULL-001`。

## 空值高危模式

diff 或扩展上下文出现以下模式时，必须做空值专项审查并读取 gotchas 参考：

- `Collectors.toMap(...)` 的 value 可能为 `null`
- `Optional.get()` 或 `findFirst().get()`
- `Map.get(...).foo()` 链式访问
- `response.getItems().stream()` 这类可空集合直接 stream
- `.intValue()` 或可空包装类型参与比较、运算导致自动拆箱
- `list.get(0)` 没有判空或判空集合
- Kotlin `!!`
- `a.getB().getC().getD()` 这类深链式调用
- `stream().map(...)` 可能产出 `null`
- `BeanUtils.copyProperties` 的 source 可能为 `null`

## 输出格式

只输出 findings，不要用通过项填充答案。

开头使用短头部：

```text
审查范围: MR / commit range / local diff
上下文来源: MR 123 / base..head / working tree
调用扩展: 1-2 跳
数据库MCP状态: 在线 / 离线
```

然后按 `P0 -> P3` 排序列出 findings。每个 finding 包含：

- 严重级别
- 规则编号
- 文件和行号
- 简短标题
- 来自 diff 或相关代码的证据
- 影响
- 推荐修复

如果没有 findings，明确说明没有发现高置信问题，并列出剩余盲点，例如未解析符号或数据库离线检查。

## 对用户的引导

从对话触发 skill 时，用简短直接的中文提示，不要让用户自己读脚本文档。

推荐话术：

- `把 MR 地址发我，我按 MR 范围做 review。`
- `告诉我源分支和目标分支，我按分支差异做 review。`
- `如果你只想看本地未提交改动，也可以直接说 review 当前 diff。`
- `当前机器没有 glab。你可以改用分支对比模式，或者我帮你安装 glab。要安装的话，我会临时使用清华 Homebrew 镜像执行 brew install glab。要我现在安装吗？`

除非用户明确想自己运行脚本，否则不要强迫用户选择命令行参数。
不要在没有明确确认时安装 `glab`。

如果用户要自己运行脚本，给出对应命令：

```bash
# MR 模式
bash "$SKILL_DIR/scripts/review_mr.sh"

# 分支对比模式
bash "$SKILL_DIR/scripts/review_branch.sh"

# 安装 glab
bash "$SKILL_DIR/scripts/install_glab.sh"
```

正式 review 后，如果存在 findings，除非用户明确说不要记录，否则用 `candidate` 状态记录到历史：

```bash
python3 "$SKILL_DIR/scripts/review_memory.py" \
  log-review --repo-key <repo-key> --input-json /tmp/review-findings.json
```

每次正式 review 结束后，必须执行 document-first 输出流程。先生成独立文件，再通过临时 worktree 或临时 clone 写入 `git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git` 的 `cr-notes/`，提交并 push。这个步骤是强制出口：不能跳过，不能静默降级为只在本地保存；如果归档或 push 失败，先把 review findings 给用户，再简短报告失败原因并把它作为待修复问题继续处理。

归档后，如果本次 review 是 MR 模式，或对话/collector 上下文中出现完整 GitLab MR URL，即使 collector 因缺少 `glab` 降级为 `commit_range` 或 `working_tree`，也要询问是否评论到 MR：

```text
要把这次 review 结果评论到 MR 吗？
1. 评论到 MR
2. 先不评论
```

只有用户选择 `1` 或明确要求发布 MR 评论时，才执行 MR 评论发布。若没有完整 MR URL，先问：`请把要评论的 MR 地址发我。`

```bash
# 生成 review-result.json 和 review-report.md
python3 "$SKILL_DIR/scripts/review_outputs.py" build \
  --context-json /tmp/review-context.json \
  --findings-json /tmp/review-findings.json \
  --team <team> \
  --output-dir /tmp/ai-cr-output

# 强制归档到 tool/skills.git 的 cr-notes/ 并 push。
python3 "$SKILL_DIR/scripts/review_outputs.py" archive-and-push \
  --result-json /tmp/ai-cr-output/review-result.json

# 仅当用户选择评论到 MR 或明确要求 MR 评论时才使用：先 dry-run。
python3 "$SKILL_DIR/scripts/review_outputs.py" publish-gitlab \
  --result-json /tmp/ai-cr-output/review-result.json \
  --dry-run

# 仅当已经发布 MR 评论时才同步 discussion resolved/waive/reject 状态。
python3 "$SKILL_DIR/scripts/review_outputs.py" sync-discussions \
  --result-json /tmp/ai-cr-output/review-result.json \
  --summary-root /path/to/skills/cr-notes

# 生成 CR 总览和团队统计。
python3 "$SKILL_DIR/scripts/review_outputs.py" stats \
  --summary-root /path/to/skills/cr-notes
```

发布 MR 评论前的 GitLab 访问规则：

1. 正式流程首选 `review_outputs.py publish-gitlab`，它通过 `glab api` 发布评论。先确认：

   ```bash
   command -v glab
   glab auth status --hostname gitlab.codemao.cn
   ```

2. 如果缺少 `glab`，不要擅自安装；按前置规则询问用户是否安装，或请用户先完成 `glab auth login --hostname gitlab.codemao.cn`。

MVP 中，`open` 表示未处理，`developer_resolved` 表示 GitLab discussion 已 resolved，`waived` 表示接受但豁免，`rejected` 表示不接受或误报。不要声称 `verified_fixed`，这个状态在 MVP 中故意延后。

如果用户说：

- `记录这次 review` -> 运行 `log-review`
- `把这条问题记为采纳` -> 运行 `mark-finding --status adopted`
- `把这条问题记为误报` -> 运行 `mark-finding --status rejected`
- `查看历史高频问题` -> 运行 `query-findings`

## 清理

如果 collector 或 archive 流程创建了临时 worktree/clone，优先使用脚本自带清理逻辑。不要删除用户仓库、不要用 `git reset --hard` 清理业务仓库。
