# 灵犀·代码实现的灵犀·需求方案交接规则

当用户提供来自“灵犀·需求方案”（`lingxi-plan`）的 `RequirementContext`（需求上下文），或要求基于上游技术方案实现后端代码时，读取本参考。

## RequirementContext 处理
用户提供 `RequirementContext` 时：
- 将它视为本次运行的上游需求来源。
- 在 `Pre-check` 和 `方案映射表` 生成中复用它。
- 不要求在“灵犀·代码实现”中重新读取原始需求 URL。
- 若 `fetch_status=failed`，停止并要求先完成需求收集。
- 若 `requirements_stage_gate` 缺失或不等于 `captured`，停止并要求先回到“灵犀·需求方案”完成需求收集。
- 若 `technical_plan_status` 缺失或不等于 `generated`，停止并要求先回到“灵犀·需求方案”生成技术方案。
- 若 `implementation_surface=frontend`，停止并说明当前技能不负责前端实现。
- 若 `implementation_surface=unknown`，停止并要求先确认实施端。
- 若 `implementation_surface=backend|fullstack`，要求 `backend_plan_status=generated`。
- 若 `需求清单路径`、`需求收集单路径`、`后端技术方案路径` 任一缺失或不可读，停止并要求补齐可追溯文件。
- 若 `implementation_surface=fullstack`，只实现后端技术方案，不得宣称前端部分已完成。
- 只要 `blocking_source_gaps` 非空，只有 `source_gap_approval=approved` 时才能继续；否则停止并要求确认来源缺口。
- 旧字段 `stage_gate` 不再作为门禁依据；只识别 `requirements_stage_gate` 和 `technical_plan_status`。

响应中使用直白术语：
- `需求收集单` = `RequirementContext`
- `开发补充单` = developer details (`本期要做/本期不做/第三方对接信息/内部改造点/验收口径`)
- `方案设计单` = “灵犀·需求方案”生成的后端技术方案
- `需求清单` = generic list with `背景/需求要点/需求注意事项/第三方对接/需实现部分(R*)`

## 硬门禁

以下情况必须停止，不进入实现：
- `fetch_status=failed`
- `requirements_stage_gate` 缺失或不等于 `captured`
- `technical_plan_status` 缺失或不等于 `generated`
- `implementation_surface=frontend|unknown`
- `implementation_surface=backend|fullstack`，但 `backend_plan_status` 不等于 `generated`
- `需求清单路径`、`需求收集单路径`、`后端技术方案路径` 任一缺失或不可读
- 存在未授权的 `blocking_source_gaps`，无论 `source_completeness` 当前值是什么

如果只是推荐字段缺失，但不影响上述硬门禁，可以继续并在 `风险说明` 中高亮：
- `原始需求文件路径`（仅当“灵犀·需求方案”未要求原始留存时可缺失）
- `本期要做/本期不做`
- 开发补充信息
- 非阻塞 `source_gaps`

如果用户明确要求只实现部分范围：
- 实现范围限制在 `本期要做`。
- 将 `本期不做` 明确标为本期外范围。
- 范围清单缺失且影响实现判断时，停止并要求补齐；不再仅按最佳猜测推进。

## SolutionContext Output Add-On
When `Plan-Full` implementation planning is required, append a compact structured block:

```yaml
SolutionContext:
  form_label: "方案设计单"
  solution_title: string
  需求清单路径: string
  需求收集单路径: string
  原始需求文件路径: string
  需求条目映射: string[]   # format: "R1 -> 方案章节X"
  本期要做映射: string[]
  本期不做确认: string[]
  第三方依赖检查清单: string[]
  第三方对接落地清单: string[]
  复用模板清单: string[]
  接口与存储变更摘要: string[]
  风险与回滚摘要: string[]
  验收测试计划: string[]
  可开发状态: "可开发" | "带风险可开发"
  待补充项: string[]
```

Readiness rule:
- `可开发`: no blocking unknowns for implementation.
- `带风险可开发`: design can proceed but has unresolved dependency/details.

Plan-Full persistence behavior:
- `Display-Only`: `SolutionContext` may be returned inline only, without repository file write.
- `Display-And-Persist`: `SolutionContext` should be persisted to a repository document path and referenced in output.

## Technical Plan Consumption
Use `后端技术方案路径` as the primary implementation source. Use `RequirementContext`, `需求清单路径`, and `需求收集单路径` as traceability metadata and scope evidence.

- Do not regenerate the requirement technical plan when a completed plan from `lingxi-plan` is present.
- Map selected `R*` items and technical-plan sections to concrete code changes before implementation when `Plan-Lite` or `Plan-Full` is active.
- For direct implementation tasks without `RequirementContext`, use the user request and repository evidence; do not invent upstream completion states.
- Items in `需实现部分` not selected in the current phase must be explicitly labeled as `本期不实现`.
- If source completeness is partial but `source_gap_approval=approved`, continue only within the approved scope and preserve the source-gap risk in the implementation summary.
