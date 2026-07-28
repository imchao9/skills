# Import contract

Use this contract when converting an exporter-specific payload into the importer’s canonical shape. The importer accepts a top-level array or an object containing an array under `items`, `notes`, `data`, `favorites`, or `results`.

Pass `-` as the input path to read JSON from standard input. This is preferred for live OpenCLI smoke tests because signed source URLs remain in the process pipeline instead of a persistent export file. Supply `--media-root` explicitly if streamed JSON references local media.

## Canonical example

```json
{
  "items": [
    {
      "note_id": "abc123",
      "url": "https://www.xiaohongshu.com/explore/abc123",
      "title": "深圳周末路线",
      "content": "正文",
      "author": {
        "name": "作者名",
        "id": "author-id"
      },
      "published_at": "2026-07-01T10:00:00+08:00",
      "collected_at": "2026-07-27T09:00:00+08:00",
      "kind": "favorite",
      "collections": ["周末"],
      "tags": ["深圳", "徒步"],
      "likes": "320",
      "collects": "41",
      "comments_count": "18",
      "views": "5600",
      "media": [
        {
          "type": "image",
          "path": "media/abc123/cover.jpg"
        },
        {
          "type": "video",
          "path": "media/abc123/video.mp4"
        }
      ],
      "transcript": "已由用户提供或经授权工具生成的转写文本。",
      "comments": [
        {
          "author": "评论者",
          "content": "评论内容",
          "created_at": "2026-07-02T10:00:00+08:00",
          "replies": [
            {
              "author": "作者名",
              "content": "回复内容"
            }
          ]
        }
      ]
    }
  ]
}
```

## Recognized aliases

| Canonical field | Accepted aliases |
| --- | --- |
| `note_id` | `id`, `noteId`, `note_id` |
| `url` | `url`, `link`, `share_url`, `note_url` |
| `title` | `title`, `name`, `note_title` |
| `content` | `content`, `desc`, `description`, `text`, `note_text` |
| `author` | `author`, `user`, `creator`, `nickname` |
| `published_at` | `published_at`, `publish_time`, `created_at`, `time` |
| `collected_at` | `collected_at`, `favorite_time`, `saved_at` |
| `kind` | `kind`, `type`, `source_type`, or true like/favorite/authored flags |
| `collections` | `collections`, `albums`, `folders`, `categories`, `category` |
| `tags` | `tags`, `topics`, `hashtags` |
| `likes` | `likes`, `like_count` |
| `collects` | `collects`, `favorites_count`, `favorite_count`, `collect_count` |
| `comments_count` | `comments_count`, `comment_count` |
| `views` | `views`, `view_count`, `read_count` |
| `media` | `media`, `images`, `image_list`, `pictures`, `videos`, `video` |
| `comments` | `comments`, `comment_list` |
| `transcript` | `transcript`, `transcription`, `video_text` |

Unknown fields are ignored. This is deliberate: browser exports frequently include cookies, signatures, tracking fields, and private account state that must not reach the vault.

## OpenCLI 1.8.6 mapping

The live adapter uses only observed, read-only OpenCLI commands:

| Purpose | Command | Observed row shape |
| --- | --- | --- |
| Login preflight | `opencli xiaohongshu whoami -f json` | login state fields |
| Favorites | `opencli xiaohongshu saved --limit N -f json` | `id`, `title`, `author`, `likes`, `type`, `url` |
| Likes | `opencli xiaohongshu liked --limit N -f json` | `id`, `title`, `author`, `likes`, `type`, `url` |
| Authored posts | `opencli xiaohongshu creator-notes --limit N -f json` | `id`, `title`, `date`, `views`, `likes`, `collects`, `comments`, `url` |
| Note details | `opencli xiaohongshu note URL -f json` | `field`/`value` rows for title, author, content, likes, collects, comments, tags |
| Comments | `opencli xiaohongshu comments URL --limit N --with-replies true -f json` | author, text, likes, time, reply flags |
| Media | `opencli xiaohongshu download URL --output DIR -f json` | per-file status; files under `DIR/<note-id>/` |

The live signed URL is retained only long enough to invoke note, comments, and download commands. The reusable export and Obsidian notes receive only `sanitize_url(...)` output. Runtime warnings before a JSON document are tolerated, but a non-zero OpenCLI exit remains a recorded error.

The current saved/liked commands have a limit but no cursor and do not return collection folder names. Therefore the adapter emits a bounded manifest and must not label the result as a complete account backup or a collection-tree mirror.

For resumable live sync behavior, read
[sync-state-contract.md](sync-state-contract.md). The import contract describes
note data; the state contract describes local processing history.

## Media rules

- Resolve relative paths against `--media-root` when provided, otherwise against the input JSON’s parent directory.
- Reject traversal and symlinks that resolve outside those source roots.
- Copy existing local files into the vault.
- A resumable state snapshot may use `vault_path` for media already stored in
  the selected vault. It must be vault-relative, contained inside that vault,
  and reference an existing supported media file; reuse it without copying.
- Keep remote URLs as sanitized links; the importer does not download them.
- Treat a missing local file as a reported warning, not as a reason to discard the note.
- Never store a remote URL query parameter named like `token`, `xsec_token`, `sign`, `signature`, `auth`, `authorization`, `cookie`, `session`, `key`, or `secret`.
- Strip URL user-info credentials and reject destination paths or symlinks that resolve outside the vault.

## Incremental behavior

The stable identity is `note_id`; if absent, the importer derives a hash from the sanitized URL, title, and author. The note filename retains the first imported title and ends with the stable ID. Later imports find the note by that suffix and replace only:

```text
<!-- xhs-sync:start -->
...
<!-- xhs-sync:end -->
```

Frontmatter keys prefixed with `xhs_` are managed by the importer. Other frontmatter fields and all content outside the managed block are preserved.
