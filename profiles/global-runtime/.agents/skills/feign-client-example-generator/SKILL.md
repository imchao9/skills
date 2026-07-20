---
name: feign-client-example-generator
description: Generate Java/Kotlin call examples for FeignClient interfaces by mapping client endpoints to current server-side implementations. Use when users ask to generate examples for all FeignClients or selected FeignClients, need an interactive client picker, or need third-party involvement checks before producing examples.
---

# Feign Client Example Generator

Use this skill to generate realistic invocation examples from FeignClient interfaces and their matched implementation endpoints.

## Required Interaction Flow

Follow this flow strictly.

1. Ask the user to choose generation scope first:
   - `全部 FeignClient`
   - `指定 FeignClient`
2. If user chooses `指定 FeignClient`, list all discovered FeignClients and ask user to pick one or more.
3. After scope/client selection, ask update scope:
   - `全量更新（当前选择范围内所有方法）`
   - `方法级增量更新（仅指定方法）`
4. If user chooses `方法级增量更新`, list methods from selected FeignClient(s) and ask user to pick one or more methods.
5. After selection, inspect matched implementation endpoints.
6. If third-party involvement is detected, ask:
   - 是否需要补充第三方文档链接用于辅助生成示例？
   - Wait for answer before generating examples.
7. Ask output mode before writing examples:
   - `生成独立文件`
   - `补充到 FeignClient（块注释）`
8. Generate final call examples in both Java and Kotlin.

Do not skip the interaction questions above.

## Commands

List all FeignClients:

```bash
python3 .agent/skills/feign-client-example-generator/scripts/inspect_feign_clients.py \
  --mode list --format text
```

List all FeignClients with explicit module globs (cross-repo fallback):

```bash
python3 .agent/skills/feign-client-example-generator/scripts/inspect_feign_clients.py \
  --mode list --format text \
  --feign-glob "<client-module-a>/src/main/kotlin/**/*.kt,<client-module-a>/src/main/java/**/*.java,<client-module-b>/src/main/kotlin/**/*.kt,<client-module-b>/src/main/java/**/*.java" \
  --service-glob "<impl-module-a>/src/main/kotlin/**/*.kt,<impl-module-a>/src/main/java/**/*.java,<impl-module-b>/src/main/kotlin/**/*.kt,<impl-module-b>/src/main/java/**/*.java"
```

Inspect one client and map to implementation:

```bash
python3 .agent/skills/feign-client-example-generator/scripts/inspect_feign_clients.py \
  --mode inspect --client "<ClientNameOrFQCN>" --format json
```

## Example Output Policy

When generating Java/Kotlin snippets:

- Use method signatures from the selected FeignClient.
- Use matched controller route and HTTP method as behavior hints.
- Include request object construction and result handling with concrete fields.
- Add a short note when no exact implementation match is found.
- If user provided third-party doc links, align examples to those constraints and mention which link influenced the example.
- Use an integration-facing structure: include a `Feign 方法 + 功能说明` table for quick API onboarding.
- Provide both layers of examples:
  - integrated usage examples (Java + Kotlin)
  - per-method usage examples (Java + Kotlin)
- If `方法级增量更新` is selected, generate/update only the selected methods and keep unrelated method examples unchanged.

## Language Style Policy (Required)

For teammate-facing outputs:

- Use Chinese for explanatory prose, section titles, mapping summaries, and notes.
- Keep professional/API terms in their original form when clearer (for example: FeignClient, endpoint, media_id).
- Keep code identifiers in English (`class`, `method`, variable names, API paths).
- Prefer Chinese for inline code comments unless the user explicitly requests English comments.
- Do not translate package names, FQCN, HTTP paths, or annotation names.

## Real-Field Population Rule (Required)

Generated examples must be based on actual request/response model fields in the codebase, not placeholder-only pseudo snippets.

Required:

- Populate core request fields with realistic sample values when setters/fields exist.
- Prefer concrete chains like `start -> get detail -> approve/terminate` when those methods are available.
- Reflect controller/service behavior for key fields (for example: boolean pass mapping, required IDs, process instance fields).
- Keep `TODO` only for truly business-specific values that cannot be inferred from code/docs.

Forbidden:

- Placeholder-only snippets such as `new Request(); // TODO fill fields`.
- Omitting required fields that are present in model classes and used in service logic.

## Field Discovery Workflow (Before Writing Examples)

After client selection and endpoint inspection, do this before generating output:

1. Read selected FeignClient interface methods and request/response types.
2. Read request model classes used by main example methods (at least start/query/approve paths when present).
3. Inspect matched controller + service implementation for parameter semantics and required mappings.
4. If third-party docs are provided, reconcile field usage with those docs and annotate influenced fields.

Recommended shell probes:

```bash
rg -n "class <RequestType>|set[A-Z]|@NotNull|@NotEmpty" .
rg -n "<methodName>|<requestType>" .
sed -n 'start,endp' <matched-service-or-controller-file>
```

## Example Quality Checklist

Before finalizing Java/Kotlin snippets, verify:

- Each showcased method includes concrete request field assignments.
- IDs and control fields are explicit where needed (for example `processCode`, `processInstanceId`, `pass`, `remark`).
- Snippets compile in style (valid imports/classes/method calls for the project APIs).
- Third-party influenced fields are called out in a short note.
- For block-comment mode, generated content remains concise and bounded by marker block.
- The output includes a clear `Feign 方法 + 功能说明` table.
- The output includes both integrated and per-method examples for Java and Kotlin.
- In `方法级增量更新` mode, verify unrelated method example sections were not modified.

## Incremental Update Rules (Required)

When `方法级增量更新` is selected, apply the following rules strictly:

1. Resolve target file first:
   - Mode A: `docs/feign-examples/<ClientName>.md` (relative to current project root)
   - Mode B: selected FeignClient source file
2. If target exists, read existing content before generating new content.
3. Update only selected method sections; keep unrelated method sections unchanged.
4. If a selected method section does not exist, append it in the correct section group.
5. If target does not exist, generate a new full document/block using the standard structure.

For Mode A markdown incremental updates, use stable method markers to enable safe replacement:

- `/* BEGIN GENERATED METHOD: <methodSignature> */`
- `/* END GENERATED METHOD: <methodSignature> */`

Do not overwrite hand-written notes outside generated method marker blocks.

## Output Mode Rules

Always ask user to choose one of the following output modes.

### Mode A: `生成独立文件`

- Write markdown files under `docs/feign-examples/` relative to the current project root.
- Do not hardcode repository-specific absolute paths in output location rules.
- File name convention:
  - single client: `<ClientName>.md`
  - all clients: `all-feign-clients-examples.md`
- Include:
  - client basic info
  - Feign method capability table (`Feign 方法 + 功能说明`)
  - implementation mapping summary
  - Java integrated snippet
  - Kotlin integrated snippet
  - Java per-method snippets
  - Kotlin per-method snippets
- In `方法级增量更新` mode:
  - if target file exists, read it first and update only selected method sections.
  - preserve unrelated method sections and non-generated custom content.
  - use markdown method markers for replace-in-place safety.

### Mode B: `补充到 FeignClient（块注释）`

- Update the selected FeignClient source file directly.
- Insert a generated block comment near interface/class declaration.
- Use stable markers so future runs can replace content safely:
  - start: `BEGIN GENERATED CALL EXAMPLES`
  - end: `END GENERATED CALL EXAMPLES`
- If marker block already exists, replace block content instead of appending duplicates.
- In `方法级增量更新` mode, update only selected method sub-blocks.
- Recommended sub-markers:
  - `/* BEGIN GENERATED METHOD: <methodSignature> */`
  - `/* END GENERATED METHOD: <methodSignature> */`
- Keep comment language concise and preserve compilable source code.

## Third-Party Decision Rule

Treat implementation as third-party related when inspection result contains:

- `thirdPartyInvolved = true`, or
- evidence lines with keywords such as `dingtalk`, `beisen`, `didi`, `external`, `openapi`, `sdk`, `http://`, `https://`.

When third-party related, ask for extra documentation links before writing code examples.

## Script Resource

- `scripts/inspect_feign_clients.py`
  - Auto-discovers Feign modules (name contains `client`) and implementation modules (for example name contains `service`/`api`/`web`/`server`/`backend`/`core`) in current project.
  - Supports explicit override via `--feign-glob` and `--service-glob` (repeatable or comma-separated).
  - Scans FeignClient declarations from Feign module source files.
  - Matches endpoint routes to controller mappings from implementation source files.
  - Follows common implementation chain (`controller -> facade -> service`, including `*Impl`) when collecting third-party evidence.
  - Flags potential third-party involvement with evidence lines.
