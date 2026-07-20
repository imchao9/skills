---
name: weekly-business-report
description: Use when asked to generate, refresh, or verify a recurring local weekly business report from prior Markdown reports, week-specific product-progress notes, legacy .xls/.xlsx source tables, CSV work-sync exports, and TAPD-style links. Especially relevant for folders like weekly-report with MxWy subfolders, previous week reports as templates, and follow-up requests to resync after 产品一周进度.md changes.
---

# Weekly Business Report

Use this skill for local, recurring weekly reports where the source of truth is a folder of prior reports and current-week spreadsheets.
The goal is to preserve the existing report voice and structure while making counts, links, and progress wording traceable to the local source files.

## Workflow

1. Inventory the local folder before writing.
   - Find prior reports, usually files like `基础平台26M7W1周报.md`.
   - Find current-week source files, usually an `MxWy/` folder with `.xls`, `.xlsx`, `.csv`, and `产品一周进度.md`.
   - Treat the latest previous report as the format template unless the user provides another target.

2. Read the product-progress note as the business wording source.
   - Use `产品一周进度.md` for top-line focus, cross-month priorities, risk language, and next-step phrasing.
   - If the user says the product-progress file changed, reopen it and resync the existing report rather than creating a second report.

3. Extract source tables with structured tools.
   - Prefer spreadsheet parsers for `.xlsx` and CSV.
   - If legacy `.xls` cannot be read because `xlrd` or equivalent support is missing, convert with LibreOffice headless into `/tmp/<task-name>/*.xlsx`.
   - Keep temporary conversion outputs outside the report folder unless the user asks otherwise.

4. Draft or update the report in place.
   - Preserve the prior report structure, headings, and link style.
   - Do not invent TAPD IDs or reuse neighboring links when the source row has no ID.
   - Keep unmatched items as plain text and note the source limitation if needed.

5. Verify before final response.
   - Recount key source categories against the generated report.
   - Check TAPD link IDs and titles for obvious conflicts.
   - Grep for important phrases from the product-progress note.
   - Report any missing fields, source rows without IDs, or assumptions.

## Boundaries

- Do not query external systems unless the user explicitly asks.
- Do not print private spreadsheet contents beyond the concise report summary needed for verification.
- Do not overwrite manual edits without rereading the live report first.
- Do not treat stale generated text as final when a source note has changed.
