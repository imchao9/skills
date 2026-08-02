---
name: ai-test-metrics
description: Use when collecting AI-assisted requirement test effectiveness data for ai-intelligent-test, including first-run pass rate, human intervention rounds, time estimates, AI-reported bugs, minimal operator confirmation, DingTalk spreadsheet submission, and local Excel fallback for Codex or Cursor workflows.
---

# AI Test Metrics

Use this skill when a user asks to collect, summarize, confirm, or submit
spreadsheet rows for AI-assisted requirement test effectiveness.

## Required Reading

1. `docs/agent/ai-test-metrics.md`
2. `docs/agent/runbook.md`
3. Relevant `midscene_run/report/<run_id>/manifest.json`
4. Relevant `midscene_run/report/<run_id>/ui-audit.json`, if present
5. Relevant case files under `cases/<platform>/<project>/`

## Boundaries

- Infer metrics fields from reports, case metadata, local context, and the
  user's latest instructions whenever possible.
- Use only the fixed DingTalk document:
  `https://alidocs.dingtalk.com/i/nodes/ydxXB52LJq73MwLQHKX3woemWqjMp697?utm_scene=team_space&iframeQuery=sheet_range%3Dkgqie6hm_0_0_1_1`.
  Do not write metrics to any other DingTalk document.
- Ask the operator only for blocking decisions: unknown `需求ID`, ambiguous
  valid run, overwrite/update target, or human-judgment counts that the team
  does not allow as `待确认`.
- If no blockers remain, write directly to the fixed DingTalk document and read
  back the written ranges without an extra confirmation round.
- If fixed DingTalk write or readback fails because of permissions, access, API,
  or network issues, generate a local Excel workbook under
  `midscene_run/metrics/` with the same `需求总表` and `运行明细表` rows.
- Do not query TAPD in V1.
- Do not count invalid environment-blocked runs in first-run pass rate.
- Do not count AI waiting time as human participation time.
- Do not merge AI-reported, human-confirmed, false-positive, uncertain, and TAPD-verified bug counts.

## Workflow

### Start of Requirement Work

Output a metrics initialization block before case generation or first execution:

```text
【AI测试成效统计初始化】
需求ID:
需求名称:
平台:
项目:
负责人:
执行人:
AI工具:
人工测试预估分钟:
备注:
```

When an internal stable id is needed, use `统计ID` format:

```text
<需求ID>-<平台>-<项目>-<负责人>
```

### After First Run

Inspect the first report and output evidence. If no blocking decisions remain,
write rows directly to the fixed DingTalk document and read them back. If
DingTalk submission fails, generate the local Excel fallback.

```text
【首跑统计摘要】
是否有效首跑:
无效原因:
运行ID:
首跑报告链接:
用例数:
首跑通过数:
首跑失败数:
首跑无效数:
首跑通过率:
失败类型分布:
```

Ask the operator only when a blocker exists:

```text
【AI测试成效统计待确认】
钉钉文档:
需求ID:
有效运行:
需要人工确认:
默认处理:
确认后动作:
```

The first run is valid only when the requirement case set completed without
environment blockers such as missing account, missing app install, unavailable
device, or missing model credentials.

### Human Intervention Counting

Count only effective human interventions:

- `需求澄清`
- `用例生成修正`
- `运行环境处理`
- `测试数据处理`
- `失败定位`
- `业务bug确认`
- `误报排除`

Do not count waiting, opening reports, copying commands, status updates, or
simple acknowledgements.

### Submit Metrics

After blockers are resolved, or immediately when no blockers exist, write rows
directly to the DingTalk spreadsheet, read back the written ranges, and output:

```text
【已提交钉钉统计】
钉钉文档:
需求总表写入范围:
运行明细表写入范围:
写入行数:
读回校验:
保留待确认字段:
```

If DingTalk submission fails, write the same rows to a local Excel workbook and
output:

```text
【已生成本地统计Excel】
失败原因:
Excel路径:
包含工作表:
写入行数:
文件校验:
保留待确认字段:
```

## Spreadsheet Fields

Use the exact field definitions and enum values from
`docs/agent/ai-test-metrics.md`.

## Output Rules

- Prefer compact summaries when showing evidence or pending blockers.
- Do not ask for missing non-blocking human-owned values. Write `待确认` for
  those fields and list them in the submission summary.
- Ask for missing values only when they are blockers under
  `docs/agent/ai-test-metrics.md`.
- Report paths may appear in local summaries, but do not write local report
  links as default DingTalk metrics fields.
- When falling back to local Excel, use compact sheet names and headers from
  `docs/agent/ai-test-metrics.md`; verify the workbook exists before replying.
- Keep summaries short and evidence-oriented.
