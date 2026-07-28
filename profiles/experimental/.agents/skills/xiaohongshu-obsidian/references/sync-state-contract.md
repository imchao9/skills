# Sync state contract

Use the state file to skip completed note IDs and resume incomplete per-note
steps. It is a sanitized checkpoint, not a complete Xiaohongshu backup.

## Location

- With `--vault`, default to `<vault>/.xhs-sync/state.json`.
- Use `--state-file` for an explicit path.
- With only `--output-json`, default beside the export as
  `.xhs-sync-state.json`.
- `--dry-run` may read state but must not write it.

## Shape

```json
{
  "version": 1,
  "source": "opencli/xiaohongshu",
  "updated_at": "2026-07-28T00:00:00+00:00",
  "notes": {
    "note-id": {
      "status": "partial",
      "source_types": ["favorite"],
      "completed_steps": ["details"],
      "item": {
        "note_id": "note-id",
        "url": "https://www.xiaohongshu.com/explore/note-id",
        "title": "标题",
        "content": "正文",
        "media": [
          {
            "type": "image",
            "vault_path": "Sources/Xiaohongshu/_media/note-id/01-cover.jpg"
          }
        ]
      },
      "content_hash": "sha256",
      "updated_at": "2026-07-28T00:00:00+00:00",
      "last_error": {
        "step": "comments",
        "error": "sanitized error",
        "at": "2026-07-28T00:00:00+00:00"
      }
    }
  }
}
```

## Semantics

- `complete`: the selected run finished and imported/exported the note without a
  note-level error. `--new-only` skips it.
- `partial`: at least one selected note step or the final import did not finish.
  `--new-only` must process it.
- `completed_steps`: successful `details`, `comments`, `media`, and final
  `import` or `export` checkpoints.
- `item`: the latest sanitized canonical note snapshot required to resume
  without repeating completed steps and to retain comments/media when a later
  refresh does not request those optional enrichments.
- `last_error`: only the latest sanitized note-step failure.

Write each checkpoint atomically through a same-directory temporary file and
rename. Preserve an earlier valid state if the new write is interrupted.

Before import, media checkpoints may contain `path` values relative to the
current download root. Reuse a completed partial media step only if every
recorded local file still exists there; redownload when temporary files were
cleaned. After a successful vault import, replace those temporary paths with
vault-relative `vault_path` entries. On later runs, resolve only paths contained
inside the selected vault and reuse the existing embeds without recopying.

A normal refresh merges the latest list/detail fields over the stored canonical
snapshot. Empty optional fields from an unrequested step do not erase stored
comments or media. Only `partial` entries reuse `completed_steps`; a `complete`
entry is refreshed unless `--new-only` skips it.

## Safety

Never persist:

- `_raw_url` or any URL containing `xsec_token`, access tokens, signatures, or
  user-info credentials;
- cookies, authorization headers, browser storage, or session payloads;
- the OpenCLI invocation arguments;
- a raw exception that contains a signed URL.

The content is bounded by the current OpenCLI `--limit`. State proves local
processing history, not full-account completeness.
