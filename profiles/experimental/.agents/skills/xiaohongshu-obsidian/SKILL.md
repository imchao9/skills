---
name: xiaohongshu-obsidian
description: Import, resume, and incrementally organize user-owned Xiaohongshu notes, favorites, likes, authored posts, source collections, tags, comments, replies, images, videos, and supplied transcripts into an existing Obsidian vault. Use when the user asks to export, migrate, sync, resume, classify, deduplicate, or update Xiaohongshu or 小红书 content in Obsidian from OpenCLI, a local JSON export, downloaded media, or user-authorized note links. Preserve manual Obsidian edits and never persist cookies, tokens, signed query parameters, or raw browser-session data.
metadata:
  x-provenance: local
  x-owner: cm
  x-source-note: created from local Xiaohongshu capture and Obsidian workflow
---

# Xiaohongshu to Obsidian

Turn user-owned Xiaohongshu exports into searchable Obsidian notes with deterministic incremental updates. Treat extraction and vault organization as separate stages so a changing login-dependent source cannot corrupt the durable vault.

## Workflow

1. Resolve the real vault and source.
   - Treat a user-provided vault path and export file as authoritative.
   - Inspect the vault root, local instructions, templates, indexes, and a comparable note before choosing the destination folder.
   - For `Codex-Memory`, read `/Users/cm/.codex/CODEX_MEMORY.md` first and follow its curated-memory boundary.
   - Ask for authorization before reading private account data. Never ask for a password, cookie, token, or signed private URL in chat.

2. Choose an input path.
   - Prefer a local export or downloaded bundle supplied by the user.
   - For a live logged-in account, prefer `scripts/sync_xhs_opencli.py`. It checks the connected OpenCLI/Chrome session, keeps signed URLs in process memory only, and passes sanitized items directly to the importer.
   - Run `opencli doctor`, `opencli xiaohongshu whoami -f json`, and `opencli xiaohongshu saved --limit 1 -f json` when diagnosing access. Do not ask the user to paste cookies or tokens.
   - The adapter was validated against OpenCLI `1.8.6`. Check the installed and registry versions before upgrading; do not reinstall when they already match.
   - The adapter removes inherited HTTP/SOCKS proxy variables only for OpenCLI child processes so loopback daemon traffic cannot be misrouted through a disconnected proxy.
   - Read [references/import-contract.md](references/import-contract.md) when adapting a new exporter or source shape.

3. Preview a live OpenCLI sync.

   Start with one saved note and no persistent raw export:

   ```bash
   python3 scripts/sync_xhs_opencli.py \
     --source saved \
     --limit 1 \
     --vault "/absolute/path/to/Vault" \
     --folder "Sources/Xiaohongshu" \
     --dry-run \
     --interval 2.5
   ```

   If `doctor` and `whoami` already succeeded in the same run but a repeated `whoami`
   becomes slow, add `--skip-auth-check`; the selected list command still remains the
   authoritative access check.

   Add authorized sources and enrichment only after the preview is sound:

   ```bash
   python3 scripts/sync_xhs_opencli.py \
     --source saved \
     --source liked \
     --source authored \
     --limit 20 \
     --comments \
     --with-replies \
     --download-media \
     --vault "/absolute/path/to/Vault" \
     --folder "Sources/Xiaohongshu"
   ```

   The live adapter:
   - maps `saved`, `liked`, and `creator-notes` into stable source types;
   - merges duplicates found in multiple lists;
   - enriches saved/liked rows with full note text and interaction counts;
   - optionally fetches comments/replies and downloads local media;
   - retries transient note steps twice by default;
   - checkpoints successful detail, comment, and media steps after each note;
   - resumes `partial` notes and lets `--new-only` skip only `complete` note IDs;
   - retains previously imported comments and vault media when a later refresh
     does not request those optional enrichment steps;
   - continues past per-note failures and returns a structured error report;
   - never stores the signed URL used for the live request.

   `creator-notes` returns creator-dashboard URLs rather than public signed note URLs, so authored posts retain list metadata and metrics but may not support body/comments/media enrichment. OpenCLI list commands expose `--limit` without a cursor; report these runs as bounded, not complete account exports.

   The default state is `<vault>/.xhs-sync/state.json`. Use `--state-file` to
   override it, `--new-only` for unseen/unfinished notes, and `--retries` plus
   `--retry-delay` to tune transient retries. A dry-run reads existing state but
   never creates or updates it. Read
   [references/sync-state-contract.md](references/sync-state-contract.md) before
   changing state semantics.

4. Preview a local export.

   ```bash
   python3 scripts/import_xhs_export.py export.json \
     --vault "/absolute/path/to/Vault" \
     --folder "Sources/Xiaohongshu" \
     --dry-run
   ```

   For a live OpenCLI session, stream a small read-only page without persisting signed source URLs:

   ```bash
   opencli xiaohongshu saved --limit 5 -f json |
     python3 scripts/import_xhs_export.py - \
       --vault "/absolute/path/to/Vault" \
       --folder "Sources/Xiaohongshu" \
       --dry-run
   ```

   Review the planned create/update counts, target folder, stable IDs, and missing local media. Stop if the export contains no usable notes or the vault cannot be resolved.

5. Import the smallest useful local-export slice.

   ```bash
   python3 scripts/import_xhs_export.py export.json \
     --vault "/absolute/path/to/Vault" \
     --folder "Sources/Xiaohongshu" \
     --media-root "/absolute/path/to/exported-media"
   ```

   The importer:
   - creates one Markdown note per stable Xiaohongshu note ID;
   - replaces only the `xhs-sync` managed block on later runs;
   - preserves manual frontmatter and content outside that block;
   - copies local images and videos under `<folder>/_media/<note-id>/`;
   - writes comments and nested replies when the export supplies them;
   - removes credential-like query parameters from stored URLs;
   - reports created, updated, unchanged, duplicated, and missing-media counts.

6. Curate after deterministic import.
   - Add user-specific summaries, topic links, and durable tags outside the managed block.
   - Preserve the export's collection names and topic tags as source metadata; do not silently turn every source label into the vault's taxonomy.
   - Distinguish author claims, comment feedback, and independently verified facts.
   - For transcription, use an available local/user-approved transcription tool only when a local audio or video file exists. Write the transcript outside the managed block or feed it back through the documented `transcript` field. Do not claim transcription succeeded without a real output.

7. Validate.
   - Run the same import again and expect `unchanged` unless the source changed.
   - Run with `--new-only` and expect completed IDs under `skipped_seen`.
   - Confirm a failed note remains `partial`, then resumes only incomplete steps.
   - Confirm a manual paragraph outside the managed block survives an update.
   - Open representative image, video, comment, and reply links from the real vault.
   - Scan generated Markdown for `cookie`, `authorization`, `xsec_token`, access tokens, and signed URLs.
   - Report source limitations, skipped media, and any content that could not be fetched.
   - Run both offline regression suites:

     ```bash
     python3 scripts/test_import_xhs_export.py
     python3 scripts/test_sync_xhs_opencli.py
     ```

## Boundaries

- Operate only on content the user owns or is authorized to access.
- Do not bypass login, CAPTCHA, rate limits, anti-bot controls, or private APIs.
- Do not equate likes with favorites when the source export does not distinguish them.
- Do not claim full-account completeness without source counts or an exporter manifest.
- Do not claim OpenCLI collection-folder support: the current `saved` and `liked` row contracts do not expose collection names.
- Do not put signed source URLs, cookies, tokens, raw browser payloads, or local media roots in the state file.
- Do not overwrite manual note sections, flatten the vault, or invent folders without inspecting local conventions.
- Do not save cookies, tokens, raw browser storage, signed URLs, or unfiltered session payloads in Obsidian.
- Keep remote media as sanitized source links unless it has been downloaded through an authorized, verifiable path.

## Example requests

- “把这份小红书收藏 JSON 增量整理到我的 Obsidian。”
- “把我自己发布的笔记、评论和下载好的图片放进知识库，并保留人工笔记。”
- “重新同步新增收藏，不要覆盖我上次在 Obsidian 里写的总结。”
- “把本地小红书视频和已有转写稿关联到对应笔记。”
- “用我当前 Chrome 登录态，把最近 20 条收藏和点赞增量同步到 Obsidian。”
