# Development Diff Acceptance

Use this when Codex must turn code changes into executable acceptance evidence.

## Trust Model

- `git diff` / PR diff is a signal, not the truth.
- Requirement text, source ticket, and user-visible behavior define the intended outcome.
- A Coverage Review is the first review artifact; do not generate maintained cases until the user approves the intended coverage, unless they explicitly ask to skip review.
- Passing tests are necessary but not sufficient; the final diff must also pass a code review gate.
- A test that merely mirrors implementation details is not valid acceptance evidence.

## Goal Template

```text
/goal 基于当前代码 diff，先产出 Coverage Review 供使用者审核覆盖方向；在覆盖意图确认后，为受影响的用户路径生成或更新 ai-intelligent-test 自动化验收用例，并完成三段代码验收：Coverage Review gate 通过、Test gate 通过、Review gate 无阻塞问题。

通过以下证据验证：
1. 已分析当前 git diff / PR diff，识别受影响的用户路径、入口和关键状态变化；
2. 已读取相关需求、业务代码、已有 cases/support/knowledge，并说明不确定点；
3. 已输出 Coverage Review，包含覆盖概览、即将生成的用例和待确认问题；
4. 已获得使用者对 Coverage Review 的确认，或明确记录用户跳过确认的指令；
5. 已按确认后的覆盖项生成或更新 TypeScript ScriptTestCase，并复用或补充必要的 support helper；
6. 已运行最小相关验证命令，包括 typecheck、lint、相关单测，以及目标 AI 自动化用例；
7. HTML 报告显示目标验收用例通过，或失败原因已明确归类；
8. 已输出 Coverage Audit，将确认过的 TC 编号映射到最终 ScriptTestCase、执行状态和报告证据；
9. 已对最终 diff 做代码 review，确认没有阻塞级问题。

同时保持：
- 不默认信任代码 diff 是正确实现；
- 不在 Coverage Review 审核前生成或修改正式用例，除非用户明确要求跳过审核；
- 不为了让测试通过而弱化断言；
- 不把实现细节当成用户验收标准；
- 不把未确认的覆盖方向伪装成已审核；
- 不扩大修改范围；
- 不把未验证行为描述为已通过；
- Review 中发现的阻塞问题必须修复并重新验证。

使用边界：
- 输入以当前 diff、需求说明、相关业务代码、已有 cases/support/knowledge 为准；
- 用例资产优先落在 cases/ 和 cases/support/；
- 知识沉淀只进入 knowledge/_inbox/ 候选；
- 框架级 src/、package.json、lockfile 默认不改，除非用户明确要求。

每次迭代之间，先判断当前阶段：覆盖方向未确认、测试失败、报告证据不足，还是 review 发现阻塞问题。测试失败时再分类为：产品实现问题、用例表达问题、测试数据问题、环境问题、模型不稳定，或 review 发现的代码质量问题。然后选择下一步：收窄/修正 Coverage Review、修实现、修用例、抽 helper、补验证，或报告阻塞。

如果无法同时通过 Coverage Review gate、Test gate 和 Review gate，则停止并报告：已通过的验证、未通过的门禁、具体证据、阻塞原因，以及解除阻塞需要的需求说明、测试账号、环境、数据或人工决策。
```

## Workflow

1. Inspect `git status --short`, `git diff --stat`, and focused diffs for changed files.
2. Map changed code to user-visible routes, states, and product experience changes.
3. Read the source ticket or requirement truth page when available. If unavailable, state what is inferred from diff and what remains uncertain.
4. Run `test-knowledge-recall` for the affected platform/project/domain.
5. Produce a Coverage Review and stop for user approval before editing maintained cases, unless the user explicitly asked to skip review.
6. After approval, generate or update focused `ScriptTestCase` assets and support helpers. Each case must trace back to an approved TC item.
7. Run the narrowest useful checks:

   ```bash
   pnpm typecheck
   pnpm lint
   TEST_PLATFORM=<platform> TEST_PROJECT=<project> pnpm test -- --tag <tag>
   ```

8. Read the generated HTML report and classify each failure before changing anything.
9. Produce a Coverage Audit mapping confirmed TC items to generated cases, execution status, and report evidence.
10. Review the final diff in code-review stance. Blocking findings include logic regressions, missing assertions, false-positive tests, overbroad edits, leaked credentials, report-semantics errors, and maintainability risks.
11. Fix blocking review findings and rerun the affected checks.
12. Run the knowledge sedimentation check from `docs/agent/knowledge-memory.md`.

## Coverage Review Template

Produce this before editing maintained cases:

```md
## 覆盖概览
本次 diff 主要影响：...

计划覆盖：
1. ...
2. ...
3. ...

本轮不覆盖：...

## 即将生成的用例
TC-01 ...
说明：...

TC-02 ...
说明：...

TC-03 ...
说明：...

## 请确认
1. 以上用例方向是否符合本次需求？
2. 是否需要增加或删除某个场景？
3. 是否有指定测试数据、课程包、账号或环境必须使用？
```

Generation requirements:

- `覆盖概览` uses user paths and product experience language, not a stack of file names.
- `计划覆盖` uses one user scenario category per item, without concrete DOM, helper, analytics, or implementation details.
- `即将生成的用例` uses temporary review numbers such as `TC-01`; formal case ids are generated only after approval.
- Each case only explains what it will do and why a reviewer can understand it; do not expand full assertions before approval.
- `本轮不覆盖` must be explicit so reviewers do not assume every boundary is covered automatically.

Stop after the Coverage Review with a direct review request:

```text
请确认以上 Coverage Review 是否覆盖你想覆盖的方向；确认后我再生成 ScriptTestCase 并执行。
```

## Coverage Audit Template

Produce this after generating and running cases:

| Confirmed TC item | Generated ScriptTestCase | Scenario summary | Execution status | Report evidence |
| --- | --- | --- | --- | --- |

## Done Means

- The Coverage Review was reviewed by the user, or the user explicitly skipped the review gate.
- The affected AI acceptance cases pass in a real run, or the remaining failure is explicitly classified as a product/environment/data blocker.
- `pnpm typecheck` and `pnpm lint` pass, unless an unrelated pre-existing failure is proven.
- The code review pass has no blocking findings.
- The Coverage Audit shows each generated case traces back to an approved TC item.
- The final report states the verification commands, report path, coverage review result, code review result, and unverified runtime assumptions.
