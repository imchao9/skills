# Existing Knowledge Base Update Workflow

Use this reference whenever the target project may already contain a knowledge base, architecture docs, module docs, generated AI docs, handbook docs, PRDs, or historical flowcharts.

## Rule Of Thumb

Existing knowledge is not noise. Treat it as first-priority domain input. Code scanning and GitNexus are calibration tools, not replacements.

Do not directly overwrite an existing knowledge base. Do not blindly concatenate new generated docs with old docs. Use an "existing-docs-first update" workflow:

```text
1. Detect existing knowledge sources.
2. Inventory their structure, modules, diagrams, rules, and unresolved notes.
3. Scan code and GitNexus to validate current implementation.
4. Merge confirmed facts into the target KB.
5. Mark stale, conflicting, or unsupported facts as human-review items.
6. Produce a migration/update report when the update is non-trivial.
```

## First Step: Detect Existing Knowledge

Before generating any new `ai-knowledge-base`, check for existing knowledge sources in the repository and common adjacent doc locations.

Search targets:

- `ai-knowledge-base/`
- `docs/`
- `doc/`
- `knowledge-base/`
- `knowledge/`
- `wiki/`
- `architecture/`
- `design/`
- `.agents/`
- `.claude/`
- `README.md`, `AGENTS.md`, `CLAUDE.md`
- exported Markdown docs, Mermaid docs, images, PDFs, Word docs, Yuque/Notion exports, and historical flowcharts when provided by the user.

Suggested shell probes:

```bash
find . -maxdepth 3 -type d \( -name 'ai-knowledge-base' -o -name 'docs' -o -name 'doc' -o -name 'knowledge-base' -o -name 'knowledge' -o -name 'wiki' -o -name 'architecture' -o -name 'design' \)
find . -maxdepth 4 -type f \( -name '*.md' -o -name '*.mdx' -o -name '*.mermaid' -o -name '*.mmd' \)
```

When an existing KB is found, explicitly choose update mode:

| Existing docs found? | Mode | Behavior |
|---|---|---|
| No | Fresh generation | Generate a new integrated KB from code and provided reference docs. |
| Yes | Existing-docs-first update | Preserve useful content, validate against code, merge and annotate. |
| Unclear | Conservative update | Avoid deletion and write a short inventory before making structural changes. |

## Inventory Existing Docs

Before writing, summarize:

- Existing top-level structure and module names.
- Business flows already documented.
- Diagrams and whether they are Mermaid, SVG/PNG images, or embedded links.
- Business rules/formulas/status tables already present.
- Code references already present and whether they still resolve.
- Human-authored notes, warnings, `TODO`, `待确认`, `deprecated`, `过期`, `兼容`, `历史` sections.
- Redundant or conflicting module names.

For non-trivial updates, create or update:

```text
ai-knowledge-base/migration-report.md
modules/{module}/source-docs-map.md
```

Only create these files when they add value. For tiny updates, a final summary is enough.

## Merge Rules

| Situation | Action |
|---|---|
| Existing docs have a fact and source code supports it | Keep the fact, add or refresh source evidence. |
| Existing docs have a fact but source code no longer supports it | Do not delete silently. Move or mark as `待人工确认` / `疑似过期`, with the missing code symbol noted. |
| Source code has a flow/rule not covered by existing docs | Add it to the corresponding module. |
| Existing docs and source code conflict | Write the current implementation from source as the active fact; record the older wording in `human-review.md` or `migration-report.md`. |
| Existing docs contain image-only diagrams | Convert to Mermaid when practical; preserve the original image path or link as source evidence. |
| Existing docs contain business FAQ or product wording | Preserve it as business wording, but attach code evidence or mark `待人工确认`. |
| Existing docs contain historical designs | Do not mix them into current facts; move to `historical-notes.md`, `migration-report.md`, or a clearly labeled history section. |
| Existing docs duplicate generated content | Merge into one canonical section and keep the richer evidence. |

## Conflict Marking

Use explicit labels:

- `代码已确认`: current implementation confirmed by source.
- `待人工确认`: useful business meaning not confirmable from code.
- `疑似过期`: existing doc refers to missing/renamed/deleted code or behavior.
- `历史设计`: intentionally preserved as context, not current behavior.

Example:

```markdown
| Existing doc claim | Current code evidence | Resolution |
|---|---|---|
| "Refund callback directly completes after-sale" | `RefundedMessageHandlingStrategy.handle`, `AfterSaleStateFactory[...]` | Current code routes through state machine; old wording marked `疑似过期`. |
```

## `source-docs-map.md`

Create this file inside a module when several existing docs or reference docs contributed content.

Template:

```markdown
# Source Docs Map

| Source doc | Absorbed into | Status | Notes |
|---|---|---|---|
| `docs/order-flow.md` | `flow-map.md`, `diagrams.md` | `代码已确认` | Flow converted to Mermaid and class names added. |
| `docs/old-refund.md` | `human-review.md` | `疑似过期` | Mentions missing method `{method}`. |
```

## `migration-report.md`

Create this file for repository-level updates when existing docs were reorganized, merged, or partially superseded.

Template:

```markdown
# Knowledge Base Migration Report

## Summary

- Mode: existing-docs-first update
- Existing sources scanned:
- Code/GitNexus sources used:

## Merged

| Source | Target | Resolution |
|---|---|---|

## Conflicts / Stale Items

| Source | Issue | Current evidence | Next action |
|---|---|---|---|

## Deferred

| Item | Reason |
|---|---|
```

## Safety Rules

- Never delete existing human-authored knowledge unless the user explicitly asks for cleanup and the content is backed up in git or migration notes.
- Prefer editing in place when the existing structure is already useful.
- Prefer adding cross-links over duplicating whole documents.
- Preserve business vocabulary and examples even when code evidence is incomplete; mark confidence instead of erasing context.
- If the user asks for a full regeneration and existing KB exists, report that an existing KB was found and use existing-docs-first update unless they explicitly approve destructive replacement.
