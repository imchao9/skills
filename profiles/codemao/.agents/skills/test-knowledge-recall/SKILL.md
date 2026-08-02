---
name: test-knowledge-recall
description: Use before generating, repairing, or debugging business test cases in ai-intelligent-test when the task needs missing-step recall, similar-case recall, support helper discovery, failure memory, or knowledge sedimentation.
---

# Test Knowledge Recall

Use this skill to recall project memory before writing or changing business test assets.

## Inputs

Identify as many as possible from the user request and repo context:

- `platform`: `web`, `computer`, `android`, `ios`, or `harmony`
- `project`: for example `pc-client`, `oj`, `ai-typing-game`, `tanyue`
- `domain`: feature or business area
- query terms: requirement title, UI labels, event names, errors, or case ids

## Workflow

1. Read `knowledge/README.md` and `docs/agent/knowledge-memory.md`.
2. Build or refresh the generated index:

   ```bash
   pnpm tsx scripts/knowledge/build-index.ts
   ```

3. Search memory notes:

   ```bash
   pnpm tsx scripts/knowledge/search.ts --platform <platform> --project <project> --query "<terms>"
   ```

4. Inspect the top matched notes and their `related_cases` / `related_support`.
5. Inspect nearby cases and support helpers before generating or changing tests.
6. Put execution-critical steps into TS cases or support helpers. Keep knowledge notes for recall, source, page maps, historical failures, and automation guidance.
7. If the task discovers a reusable rule, test data source, page map, or failure cause, capture a candidate memory under `knowledge/_inbox/` instead of writing directly to the official vault:

   ```bash
   pnpm tsx scripts/knowledge/capture.ts \
     --platform <platform> \
     --project <project> \
     --domain <domain> \
     --type <type> \
     --title "<title>" \
     --summary "<what was learned>" \
     --source "<evidence>" \
     --tags "<comma,separated,tags>"
   ```

8. Review candidates with:

   ```bash
   pnpm tsx scripts/knowledge/review-inbox.ts
   ```

9. Promote only reviewed `promote` candidates. Merge `merge` candidates into existing notes by hand.

## Output Shape

Before editing business test assets, summarize:

- matched notes
- related cases
- related support helpers
- warnings for deprecated, reference-only, low-confidence, or missing metadata
- what will land in case/support vs knowledge
- captured memory candidates, if any, and why they should be promoted, merged, moved to support, or discarded

## Boundaries

- Do not enable runtime knowledge prompt injection.
- Do not treat knowledge notes as the source of executable truth when a case or support helper already encodes the behavior.
- Do not write new official notes directly from a task transcript. Capture candidates in `_inbox` first.
- Preserve source-backed test-environment data when it is reusable evidence unless the user or source explicitly classifies it as production, personal/private, non-test, legally constrained, or requiring masking or desensitization. Do not add unrelated model/API credentials to memory notes.
