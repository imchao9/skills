---
name: obsidian-vault
description: Search, create, link, and reorganize notes in an existing Obsidian vault. Use when the user explicitly asks to find, create, update, index, or organize Obsidian notes or a named vault. Preserve the target vault's actual root, folder structure, naming conventions, templates, and local instructions. For Codex-Memory, use its macOS vault path and read /Users/cm/.codex/CODEX_MEMORY.md first. Do not trigger for ordinary Markdown edits outside an Obsidian vault.
---

# Obsidian Vault

Operate on the user's real vault instead of assuming a universal path or layout.

## Resolve the target vault

1. Treat a user-provided path, current workspace root, or attached note as authoritative.
2. If the target is `Codex-Memory`, use:
   `/Users/cm/Library/Mobile Documents/iCloud~md~obsidian/Documents/Codex-Memory`.
3. For `Codex-Memory`, read `/Users/cm/.codex/CODEX_MEMORY.md` before inspecting or editing notes.
4. For another vault, inspect its root note, `AGENTS.md`, templates, indexes, and existing folders before deciding naming or placement.
5. Never reuse `/mnt/d/Obsidian Vault/AI Research/` unless that exact vault exists and the user places it in scope.

## Preserve local conventions

- Do not flatten a folder-based vault or invent folders in a flat vault.
- Preserve existing filename casing, language, frontmatter, tags, and link style.
- Prefer the smallest edit that keeps existing manual content intact.
- Treat index notes as navigation, not as copies of full notes.
- Keep raw logs, transcripts, credentials, tokens, cookies, and private URLs out of curated notes.

## Search

Use `rg` and `rg --files` from the resolved vault root:

```bash
rg --files . | rg '\.md$'
rg -n 'keyword' . --glob '*.md'
```

Find backlinks with the exact wikilink target:

```bash
rg -n '\[\[Note Title(?:\||#|\]\])' . --glob '*.md'
```

## Create or update notes

1. Inspect the nearest template or comparable note.
2. Choose the destination from the vault's existing information architecture.
3. Write curated conclusions and actionable context, not a conversation transcript.
4. Add `[[wikilinks]]` to real targets and preserve manual checkboxes unless the user asks to change their state.
5. Verify newly added links resolve before finishing.

## Validate

- Confirm every modified file remains valid Markdown.
- Scan changed notes for unresolved wikilinks.
- Confirm no raw session payload or credential-like value was introduced.
- Report the files changed and any unresolved classification decision.
