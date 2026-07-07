# 审查输出 MVP

本 MVP 默认只解决一件事：生成独立 review 文档，并写入独立汇总仓库 `cr-notes/` 目录后推送。正式 review 必须执行 push；不要把结果只留在本地目录或对话里。

保留两个可选能力，但默认不启用：

1. 发布 GitLab MR 总评论和 P0/P1 discussion。
2. 同步 GitLab discussion 的 resolved/反馈命令状态，但不判断代码是否真的修复。

## 状态口径

| 状态 | 含义 | 计入已填写反馈 | 计入已接受 |
| --- | --- | --- | --- |
| `open` | 未处理 | 否 | 否 |
| `developer_resolved` | 开发者已 Resolve | 是 | 是 |
| `waived` | 接受但豁免 | 是 | 是 |
| `rejected` | 不接受 / 认为误报 | 是 | 否 |

历史状态兼容：`candidate` 会按 `open` 统计，`adopted` 会按 `developer_resolved` 统计。

## 最短流程

先生成 review 上下文和 findings。findings 文件格式复用现有 `review_memory.py log-review` 输入格式：

```json
{
  "repo_key": "git@gitlab.example.com:group/project.git",
  "repo_label": "project",
  "mr_iid": 123,
  "mr_url": "https://gitlab.example.com/group/project/-/merge_requests/123",
  "base_ref": "base_sha",
  "head_ref": "head_sha",
  "findings": []
}
```

生成产物：

```bash
python3 scripts/review_outputs.py build \
  --context-json /tmp/review-context.json \
  --findings-json /tmp/review-findings.json \
  --team crm \
  --output-dir /tmp/ai-cr-output
```

写入独立汇总仓库并推送。默认使用 `git@gitlab.codemao.cn:backend/platform-informatization/tool/skills.git` 作为汇总仓库，通过临时 worktree/clone 写入 `cr-notes/`、提交并推送：

```bash
python3 scripts/review_outputs.py archive-and-push \
  --result-json /tmp/ai-cr-output/review-result.json
```

默认值固定为：仓库 `tool/skills.git`、分支 `main`、目录 `cr-notes`。如果脚本本身就在该仓库的工作区内，会优先创建临时 worktree；否则会自动临时 clone，提交推送后删除临时目录。团队成员无需配置环境变量。`archive-and-push` 不提供跳过 push 的参数；如果 push 失败，应修复失败原因后重跑。

MR 评论默认不开启。如果明确需要发布到 GitLab MR，先 dry-run 看评论内容：

```bash
python3 scripts/review_outputs.py publish-gitlab \
  --result-json /tmp/ai-cr-output/review-result.json \
  --dry-run
```

确认后再发布：

```bash
python3 scripts/review_outputs.py publish-gitlab \
  --result-json /tmp/ai-cr-output/review-result.json
```

仅当已经发布 MR discussion 时，同步 discussion 处理状态：

```bash
python3 scripts/review_outputs.py sync-discussions \
  --result-json /tmp/ai-cr-output/review-result.json \
  --summary-root /path/to/skills/cr-notes
```

生成统计：

```bash
python3 scripts/review_outputs.py stats \
  --summary-root /path/to/skills/cr-notes \
  --start 2026-04-21 \
  --end 2026-04-28 \
  --csv-output /tmp/ai-cr-stats.csv
```

## 汇总仓库结构

```text
skills/
  cr-notes/
    reports/
      <team>/
        <repo_slug>/
          mr-<iid>/
            <snapshot_uuid>/
              review-result.json
              review-report.md
    index/
      findings.jsonl
      snapshots.jsonl
      discussions.jsonl
      repos.json
```

单次报告仍可用旧的 `archive` 命令写入任意本地目录，不提交、不推送；但它只适合调试或临时产物，正式 review 不能用它替代 `archive-and-push`：

```text
custom-summary-root/
  reports/
    <team>/
      <repo_slug>/
        mr-<iid>/
          <snapshot_uuid>/
            review-result.json
            review-report.md
  index/
    findings.jsonl
    snapshots.jsonl
    discussions.jsonl
    repos.json
```

## GitLab 评论策略（可选）

- MR 评论默认不发布；只有显式执行 `publish-gitlab` 时才会发布。
- MR 总评论包含快照 ID、版本范围、P0/P1/P2/P3 数量和重点问题。
- P0/P1 默认创建行内 discussion；如果缺少位置或 GitLab 无法定位，退化为普通 MR discussion。
- P2/P3 默认只进入总评论和完整报告，避免刷屏。
- 开发者可以 Resolve discussion；同步脚本会把对应 finding 标成 `developer_resolved`。
- 开发者可以回复 `/ai-review waive <finding_key> 原因` 或 `/ai-review reject <finding_key> 原因`。

## 统计口径

- 团队数：时间范围内出现过 review 的 team 数量。
- 审查次数：`snapshots.jsonl` 中的 snapshot 数量。
- 问题总数：`findings.jsonl` 中的 finding 数量。
- 已填写反馈占比：`status != open` 的问题数 / 问题总数。
- 已接受占比：`developer_resolved + waived` 的问题数 / 问题总数。
- 各级别问题：按 `severity=P0/P1/P2/P3` 计数。
- 各级别分类 Top5：每个 severity 下按 `category` 聚合 Top5。
