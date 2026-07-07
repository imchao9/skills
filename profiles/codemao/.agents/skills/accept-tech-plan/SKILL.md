---
name: accept-tech-plan
description: Gate-review complete technical plan documents for business feature work before or after implementation. Use when the user asks to validate, accept, review, approve, 方案验收, 方案准入, 技术评审, 实现核验, 判断是否可开工, 判断是否可提测, or judge a business feature technical方案/技术方案/implementation plan against the repository, either before coding starts or after code exists, and wants a Chinese 通过 / 有条件通过 / 不通过 decision with blockers and required questions.
---

# Accept a Business Feature Technical Plan

Use this skill to decide whether a business feature technical plan is ready for implementation, or whether an existing implementation matches the accepted plan.

The posture is a gate review, not a requirements review or writing assistant. The default input is a completed or mostly completed technical方案/technical plan/design proposal. Requirement evidence is supporting material used to check business alignment; do not assume the user is asking you to validate raw requirements unless they explicitly say so.

Read the plan, determine the acceptance stage, use requirement evidence when available, verify implementation-relevant claims against the repository, and return whether development can start responsibly or the existing implementation matches the plan.

## Core Rules

- Treat repository inspection as mandatory. Do not accept claims about existing modules, interfaces, tables, flows, dependencies, or configuration without checking the code when those claims affect implementation readiness.
- Do not return `通过` when the target repository cannot be located, cannot be confirmed as the right repository, or material code claims cannot be checked. Use the repository inspection rules below to downgrade or fail.
- Treat plan completeness as the primary acceptance target. The plan must describe the intended business goal and acceptance intent well enough to judge implementation readiness. External requirement material strengthens the review but is not mandatory when the plan itself embeds enough business context.
- Treat requirement clarification as an alignment check, not the default input. If requirement material is missing, only fail the plan when the plan itself lacks enough business goal, actor, scope, business rules, acceptance intent, or exclusions to judge whether the design solves the right problem.
- Optimize for the detected stage. Before coding, judge implementation readiness. After coding, judge plan-implementation consistency, regression risk, and whether the implementation is ready for test, merge, or release.
- Distinguish target-state design from mistaken current-state assumptions. If the plan clearly says something will be created or changed, evaluate it as proposed work. If it treats nonexistent or conflicting behavior as already present, mark it as a blocker when material.
- Do not rewrite the plan. Point out gaps and ask the questions the plan author must answer.
- Lead with findings and a Chinese gate decision. Keep summaries short.

## Workflow

1. **Read the plan.** Identify the feature goal, business flow, proposed technical changes, affected systems, data behavior, interface behavior, risks, and tests.
2. **Determine acceptance stage.** Use the stage rules below to decide whether this is `编码前方案准入`, `编码后实现核验`, or `阶段未知`.
3. **Find requirement evidence.** Use the requirement source rules below before judging business alignment. Do not stop only because no external requirement document exists if the plan embeds enough requirement context.
4. **Load the rubric.** Read `references/gate-rubric.md` before judging the plan.
5. **Extract checkable claims.** List claims about requirements, existing code, APIs, routes, tables, models, jobs, permissions, config, dependencies, changed files, tests, and similar prior implementations.
6. **Inspect the repository.** Use `rg`, `rg --files`, and targeted file reads. Prefer direct evidence with `file:line` pointers. Apply the repository inspection rules below when the target repository or evidence is incomplete.
7. **If code exists, compare implementation to the plan.** Check whether implemented code, tests, config, migrations, and interface behavior match the plan's promised changes and non-goals.
8. **Classify gaps.** Decide whether each issue is blocking, conditional, or non-blocking using the rubric.
9. **Return the gate review.** Use the Chinese output format below.

## Input Interpretation Rules

Default assumption:

- The user is asking you to accept/reject a technical plan, not to accept/reject the requirement itself.
- If the supplied document mixes requirement, solution design, and implementation plan, review the solution/design portions as the target artifact and use the requirement portions as evidence.
- If the supplied material is only raw business requirements with no technical design, state that the artifact is not yet a technical plan and return `不通过` with the missing design decisions.
- If the user explicitly asks for requirement review, use a requirement-review posture instead of this skill when a more suitable skill is available.

## Acceptance Stage Rules

- Use `编码前方案准入` when the user says the work is not implemented yet, when no relevant implementation changes are present, or when the request is clearly asking whether the plan can start coding.
- Use `编码后实现核验` when the user says code has been written, provides a branch/diff/MR/PR, asks whether implementation matches the plan, or relevant changed files can be tied to the planned feature.
- Use `阶段未知` when the user does not say whether code exists and repository evidence is insufficient to infer it. Continue the review, but state the uncertainty in `验收摘要`.
- For `编码后实现核验`, prefer evidence in this order: explicit user statement, PR/MR/diff, git changed files, then targeted repository evidence. Check `git status` and a suitable diff when available.
- If only historical repository code exists and there is no user statement, PR/MR, diff, or changed-file evidence tying it to this work, do not infer that the feature has been implemented. Use `阶段未知` and state that only code-state consistency was checked.
- In `编码前方案准入`, the decision answers: "Can implementation start responsibly?"
- In `编码后实现核验`, the decision answers: "Does the implementation match the plan well enough to proceed to test, merge, or release?"
- If the stage is `编码后实现核验`, do not treat already-written code as mere existing state. Compare it against the plan's target behavior, non-goals, tests, migrations, config, and rollback expectations.

## Repository Inspection Rules

- Confirm the target repository or module before judging code-state consistency. Use the user's provided path, the current workspace, project markers, or plan references.
- If the target repository cannot be located or cannot be confirmed, the overall decision cannot be `通过`. Use `有条件通过` only when the unchecked code claims are non-core and the plan is otherwise implementable; use `不通过` when repository uncertainty affects core design, integration points, data behavior, permissions, migrations, rollback, or tests.
- If repository access is partial, mark `代码仓库检查：部分检查` and list what was checked and what was not.
- If a material code claim cannot be verified after targeted search, label it `未验证假设`. If that claim affects implementation approach or plan-implementation consistency, make it a blocker or condition rather than treating it as fact.
- Do not cite broad search results as proof of absence unless the search scope is clear enough to support the claim.

## Requirement Evidence Rules

Evaluate requirement context before implementation readiness:

1. If the current request or plan contains a DingTalk requirement document link, try to fetch the requirement through available DingTalk MCP/tools before reviewing the plan.
   - Read document metadata first when tooling supports it, then route by document type.
   - If direct link reading fails and a requirement name is available, try DingTalk search/name fallback.
   - If DingTalk tooling is unavailable, state that the current session needs DingTalk MCP access, provide the DingTalk MCP setup page `https://aihub.dingtalk.com/#/detail?instanceId=600280&detailType=instanceMcpDetail&mcpId=9629`, and say the user can either connect DingTalk MCP or paste the requirement body.
   - If DingTalk access fails but the plan embeds enough equivalent requirement context, continue the review and record `钉钉原文未验证` in `需求依据`.
   - If DingTalk access fails and no equivalent requirement context is available, ask for the requirement content or an accessible link.
2. If no DingTalk link is available, inspect the plan for referenced raw requirements, requirement lists, PRD links, issue links, or local requirement files. Read those sources when accessible.
3. If no external requirement reference exists, determine whether the plan itself contains enough requirement context: background, target user/actor, scope, business rules, acceptance criteria or acceptance intent, and exclusions.
4. If the plan embeds enough requirement context, continue the review and record requirement source as `方案内嵌`; if a DingTalk link was present but not fetched, also state `钉钉原文未验证`.
5. If neither external material nor embedded plan context provides enough requirement evidence, mark requirement context as `insufficient` and fail only because the technical plan cannot be judged against a clear business outcome.

Do not treat implementation mechanics alone as sufficient requirement evidence. The plan must expose enough business intent to judge whether the proposed behavior matches the intended outcome.

## Gate Decisions

- `通过`: the plan is ready to implement. Remaining details, if any, are minor and do not affect task breakdown or core implementation.
- `有条件通过`: the plan can proceed only if listed conditions are answered or accepted, and the gaps do not change the core design or implementation breakdown.
- `不通过`: the plan is not ready. One or more missing, incorrect, or unverified items block implementation readiness.

Use Chinese decision labels in the user-facing output. If a downstream tool or user explicitly asks for machine-readable English values, map them as `通过=pass`, `有条件通过=conditional pass`, `不通过=fail`.

When unsure between two decisions, choose the stricter one if the uncertainty affects core flow, data correctness, permissions, external interfaces, migration, rollback, or critical tests.

## Output Principles

- Lead with the Chinese decision and the smallest useful rationale.
- Separate the reviewer verdict from the evidence trail, so the result can be pasted into an acceptance record.
- Prefer action-oriented findings: each blocker or condition should tell the plan author exactly what must change or be answered.
- In dimension notes and findings, write business impact first, then technical evidence.
- If the user asks for read-only review or says not to modify files, do not offer write-oriented landing options; either omit `验收文档落地` or show only `暂不落地`.
- After the review, offer documentation landing choices and wait for the user's numbered reply before creating or updating files, unless a read-only constraint applies.

## Output Format

```markdown
## 验收结论

结论：通过 | 有条件通过 | 不通过

摘要：<用 1 句话说明技术方案是否可进入实现，或已实现代码是否符合方案>

理由：<1-3 句话说明核心判断依据>

## 验收摘要

- 方案材料：<方案名称/路径/链接或当前对话>
- 验收阶段：编码前方案准入 / 编码后实现核验 / 阶段未知
- 验收对象：技术方案 / 技术方案 + 已实现代码 / 需求与方案混合文档 / 尚不是技术方案
- 代码仓库检查：已检查 / 部分检查 / 未检查，<如未完整检查，简述原因>
- 主要实施风险：<最高信号风险或“无”>
- 下一步前必须完成：<无，或进入编码/提测/合并/发布前必须修正或确认的问题简表>

## 需求依据

- 来源：钉钉需求链接 / 引用的需求文件 / 方案内嵌 / 当前对话 / 不可用
- 状态：已获取 / 部分获取 / 已内嵌 / 缺失
- 说明：<需求依据完整性、冲突或访问限制>

## 维度检查

| 维度 | 状态 | 说明（先写业务影响，再写技术证据） |
|---|---|---|
| 需求上下文 | 通过 / 有条件通过 / 不通过 | ... |
| 需求一致性 | 通过 / 有条件通过 / 不通过 | ... |
| 实施就绪度 | 通过 / 有条件通过 / 不通过 | ... |
| 代码现状一致性 | 通过 / 有条件通过 / 不通过 | ... |
| 方案实现一致性 | 通过 / 有条件通过 / 不通过 / 不适用 | ... |
| 风险控制 | 通过 / 有条件通过 / 不通过 | ... |
| 测试充分性 | 通过 / 有条件通过 / 不通过 | ... |

## 阻塞问题

- B1. <问题>
  - 影响：<为什么阻塞或威胁实施>
  - 依据：<需求依据、方案章节、和/或仓库相对路径 file:line 证据>
  - 必答：<方案作者必须回答的问题>

## 通过条件

- C1. <有条件通过时必须满足的条件；如果结论不是“有条件通过”且无条件项，写“无”>

## 必答问题

1. <问题>

## 非阻塞建议

- <建议>

## 验收文档落地

请选择是否生成验收文档：

1. 生成独立验收报告：写入 `docs/acceptance/<plan-slug>-acceptance.md`
2. 追加到原方案文档：在方案末尾增加“技术方案验收”章节
3. 暂不落地：只保留本次对话中的验收结果
```

Omit `非阻塞建议` when there are none. If there are no blocking findings, write `无` under `阻塞问题`. If the decision is `有条件通过`, include `通过条件` and make every required condition concrete enough to verify. If there are no conditions, write `无`. Always include `验收文档落地` unless the user explicitly said not to create or update files.

When the user chooses a landing option:

- For option 1, create the directory if needed and write the review as a standalone Markdown report. Use a stable slug from the plan filename or feature name.
- For option 2, update only the referenced/local plan document. If the plan is not a local editable Markdown file, explain that append is unavailable and offer option 1 instead.
- For option 3, do not write files.
- If the requested write would overwrite an existing acceptance report, ask before replacing it.

## Evidence Rules

- Use repo-relative paths in findings.
- Cite line numbers when available.
- Cite requirement context separately from plan evidence and code evidence.
- Separate plan evidence from code evidence when both matter.
- State `unverified assumption` when a claim matters but cannot be confirmed with available context.
- Do not cite broad search results as proof of absence unless the search scope is clear enough to support the claim.
