# QA Oracle Conversion

Use this when QA supplies test assets and Codex must convert them into executable `ai-intelligent-test` cases.

## Trust Model

- The QA-provided case row is the oracle.
- Original steps, expected results, endpoints, fixtures, priority, notes, and row order must be preserved.
- Current product behavior is the object under test, not the standard.
- Codex is a converter and executor, not a free-form test designer, unless the user explicitly asks to add coverage.

## Goal Template

```text
/goal 将测试人员提供的测试用例资产转换为 ai-intelligent-test 可执行用例，并完全以原始测试用例的行级步骤、预期结果和端点作为验收标准执行。

通过以下证据验证：
1. 已读取原始测试用例文件，并说明总行数、字段、平台、项目和测试范围；
2. 已建立原始用例行到 maintained ScriptTestCase、已有 maintained case、blocker 或 explicit skip 的映射关系；
3. 已保留原始步骤、预期结果、备注、账号/测试数据来源；
4. 已执行转换后的最小相关用例集；
5. 最终报告按原始用例行说明 pass、fail、error 或 blocker。

同时保持：
- 完全信任测试用例作为 oracle；
- 不根据当前代码行为改写测试意图；
- 不新增测试人员未提供的场景；
- 不把缺数据、缺入口、缺权限伪装成通过；
- 保留来源中用于测试环境执行和复现的账号、密码、token、cookie；仅当来源或用户明确将数据标记为生产、个人/私有、非测试、法律受限或要求脱敏/遮蔽时排除相应数据，并排除无关的模型/API 密钥。

使用边界：
- 输入以 Excel/XMind/测试用例表/测试点中的步骤和预期为准；
- 正式沉淀用例使用 TypeScript ScriptTestCase；
- 可复用流程进入 cases/support/<platform>/<domain>.ts；
- Coding agent 不以 GUI runtime fallback 作为完成态；只有用户明确要求一次性临时运行时，才可做 transient report run，并必须说明未沉淀为正式用例。

每次迭代之间，优先检查转换是否忠于原始行：步骤有没有漏、预期有没有变、断言是否对应端点；然后再看执行失败是产品不符合测试用例，还是测试数据/环境/权限不足。

如果无法完成，则停止并报告：受阻的原始行号、原始步骤、原始预期、当前证据、阻塞类型，以及需要测试或开发补充的入口、账号、数据、版本或环境。
```

## Workflow

1. Read the source asset and record sheet names, row count, columns, and embedded fixtures or credentials.
2. Normalize platform names to `web`, `computer`, `android`, `ios`, or `harmony`.
3. Identify `project`, source ticket / trace id, target domain, and any missing environment or account data.
4. If maintained formal cases will be written under `cases/`, require a source ticket / trace id. Do not invent `feature_id`.
5. Run `test-knowledge-recall` for the target platform/project/domain.
6. Classify each source row:
   - maintained `ScriptTestCase`
   - support-helper extraction needed
   - existing maintained case
   - explicit skip with source-row reason
   - blocker because entry, data, auth, device, or environment is missing
7. Preserve the source row identity in case naming, tags, comments, fixtures, or support metadata so the report can be traced back.
8. Convert expected results into focused visual assertions or explicit `ctx.assert(false, blocker)` when a row is intentionally blocked.
9. Run the narrowest useful checks and the target case set.
10. Read the HTML report and map outcomes back to source rows.
11. Verify that source-backed test-environment accounts, passwords, tokens, cookies, fixtures, and other values remain exact unless the user or source explicitly classifies them as production, personal/private, non-test, legally constrained, or requiring masking or desensitization. Exclude unrelated model/API credentials.
12. Run the knowledge sedimentation check from `docs/agent/knowledge-memory.md`.

## Done Means

- Every source row is accounted for as a maintained `ScriptTestCase`, an existing maintained case, a blocker, or an explicit skip with a source-row reason.
- A transient runtime report is allowed only when the user explicitly requests one-off execution, and the final report must state that no formal case was created.
- The converted cases preserve source steps and expected results without adding unrequested scenarios.
- The final report includes the source asset, row count, mapping summary, run command, report path, and blocker list.
- Source-backed test-environment data is preserved where needed for execution and traceability unless the user or source explicitly classifies it as production, personal/private, non-test, legally constrained, or requiring masking or desensitization. Unrelated model/API credentials are not added to cases, support helpers, knowledge notes, or response summaries.
