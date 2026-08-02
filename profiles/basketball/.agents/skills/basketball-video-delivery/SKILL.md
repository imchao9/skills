---
name: basketball-video-delivery
description: Deliver a Xiaoqiumi basketball replay to verified local edits and Baidu Netdisk outputs. Use for public H5 competition or match links, authenticated MatchVideoList pages, resumable replay downloads, pure-play cuts, labeled event and player clips, team or game highlight reels, and validated Baidu uploads.
---

# Basketball Video Delivery

Run this as a resumable delivery pipeline.
Reuse specialized skills for editing; do not duplicate their algorithms here.

## Required inputs

Collect or infer:

- Xiaoqiumi public H5 or `MatchVideoList` URL and match ID.
- Local workspace with at least twice the expected source size free.
- Full remote Baidu Netdisk target path.
- Optional overrides to the default package.

The default package for every full match is mandatory:

1. Pure-play cut.
2. One personal reel per player with valid located events.
3. One 8-10 minute match-wide game highlight, data-labeled and 1920×1080.
4. Commentary Markdown plus standalone HTML and browser-rendered PNG poster.

Team-only reels and remade event fragments are optional unless requested.
Do not report completion when any default-package item is missing or invalid.
Read [references/default-delivery-prompt.md](references/default-delivery-prompt.md)
when the user asks for the reusable prompt or when orchestrating multiple games.

Never store Xiaoqiumi cookies, signed URLs, Baidu cookies, BDUSS, STOKEN, or passwords in the workspace or reports.

## Fast path

Use the standard runner for the default four-item package:

```bash
python3 "$SKILL_DIR/scripts/run_standard_delivery.py" \
  "<Xiaoqiumi match URL or match ID>" \
  --workspace "$PWD" \
  --target "/篮球/Alpha球会/比赛目录" \
  --photo "/absolute/path/to/team-photo.jpg"
```

The first invocation refreshes data, runs `fast_start_delivery.py`, creates all
reviewable drafts, and exits with status 2 plus
`output/delivery/ai-review.json`. Inspect the listed proxy video, contact
sheets, reports, commentary HTML, and PNG in one AI checkpoint. Edit referenced
CSV or Markdown files when needed, run the generated `refresh_review_command`,
inspect the regenerated draft, then set
`status` to `approved` and all quality flags to `true`.

Run the exact `resume_command` from `output/delivery/standard-run.json`.
The second invocation renders or reuses final 1080p outputs, fully decodes every
required video, validates the standard package, and builds a fingerprint-bound
final visual audit.

When final pixels differ from the main-review artifacts, the runner reports
`waiting_for_final_visual_review` and writes
`output/delivery/final-visual-review.json`. Inspect its HTML or PNG evidence,
play the compact seam-audit video with source audio when present, approve only the required
checks, set `status` to `approved`, and run the
reported resume command. Normal pure cuts require a short final-resolution seam
review. Game highlights and posters require this second check only when they
changed after the main review. If no risky pixels changed, the audit is
`auto_approved` and the runner continues without another AI stop.

The post-audit resume reuses current renders and the completed full-decode
manifest; it does not repeat expensive work.
Add `--execute-upload` only after inspecting the dry-run plan. The approved
review is a hard gate: missing flags, invalid pure-cut ranges, a one-team or
out-of-window game selection, or suspicious made-before-attempts prose stops
the run.

Use the lower-level deterministic starter only for source acquisition or
diagnosis:

```bash
python3 "$SKILL_DIR/scripts/fast_start_delivery.py" \
  "<Xiaoqiumi match URL or match ID>" \
  --workspace "$PWD"
```

The starter always refreshes match data first. It downloads the replay and
labeled events concurrently, reuses validated files, and runs pure-cut
preflight and player-clip build concurrently. AI enters only after
`output/delivery/fast-start.json` reports `ready_for_ai`.
Use `--download-only` when the immediate goal is to obtain the source files without starting video processing.
Open a browser only when the public data path fails or reports that authenticated fallback is required.

For multiple matches, refresh lightweight match data for all inputs first, then
keep processing WIP at one match. Finish, upload, verify, and clean the first
match before rendering the next. Reuse every artifact that passes its phase
gate. Use normal direct networking unless the user explicitly requests a proxy.

## Pipeline

### 1. Acquire the replay and labeled clips

Read [references/xiaoqiumi-download.md](references/xiaoqiumi-download.md).
Prefer the fast-path command above over issuing each acquisition command interactively.
Resolve the match with the public H5/API path first.
Read `MatchInfo` and the `MatchDetail` `集锦` tab, enumerate every replay candidate, de-duplicate overlapping full-length variants, retain every chronological recording segment, and collect its labeled event clips.
Use the authenticated `MatchVideoList` page only when the public response has no playable URL or access is rejected.
Download into `source/` with a `.part` suffix and rename atomically only after completion.
Download labeled event clips when the page provides them; preserve their original titles as filenames.
Use the full replay as the only editing source. Prefer event metadata,
thumbnails, and scoreboard OCR for locating plays. Treat platform event videos
as alignment references only, and fetch them only when metadata-based location
is insufficient.

Verify with:

```bash
ffprobe -v error -show_entries format=duration,size -show_streams -of json "$SOURCE"
find "$CLIPS_DIR" -maxdepth 1 -type f -name '*.mp4' | wc -l
```

When a phone or stream changes during the game, download each retained segment
and assemble them into one ordered editing source. Use fast stream-copy assembly
only when stream signatures match; normalize incompatible phone formats before
concatenation. Keep `replay-selection.json`, the individual segments, and
`replay-assembly.json` as evidence.

The acquisition gate passes only when the sanitized match report exists, every
candidate and selection decision is recorded, every selected segment passes
`ffprobe`, the assembled replay duration matches the selected-duration sum, the
final replay passes `ffprobe`, the expected event count is recorded, and no
active `.part` remains.

The standard downloader emits a 10-second health heartbeat and applies bounded
recovery to the default parallel transfer: 120-second startup grace, 90 seconds
without progress, five-minute rolling throughput below 1 MiB/s, or an ETA above
one hour after ten minutes triggers a resumable retry. It makes at most three
attempts total and preserves deterministic range chunks. If the budget is
exhausted, `fast-start.json` and `standard-run.json` report
`status: needs_attention` with progress, diagnostics, and a resume command.
Treat this as an incomplete recoverable state, request human intervention, and
do not upload or auto-shutdown. See the acquisition reference for override and
remote-object compatibility rules.
Stop for user login only when the public path is unavailable and the fallback page redirects to `SignIn`.
Do not ask the user to paste cookies into chat.

### 2. Build the pure-play version

Use `$basketball-pure-cut`.
Always create and inspect a 480p proxy, candidate sheet, reviewed deletion CSV, and final timeline contact sheet.
Treat signal candidates only as hints.
Check candidate boundaries for intermittent score/stat overlays; inspect 10-20 seconds on both sides before accepting a cut.
Render 1080p only after the reviewed proxy passes visual inspection.

### 3. Remake events and player reels

Use `$basketball-player-clips` when labeled old event clips exist.
Default to assists `front15/back0` and other actions `front15/back3`.
Keep old clips unchanged.
Review the highest visual-hash-distance rows in `reports/matches.csv` and all source-overlapping events.
Require one valid player reel per player in `reports/players.csv`.

### 4. Build team reels

Use `$basketball-highlight-builder` for separate team reels, overlay labels, manual reordering, or plan-driven de-duplication.
Read [references/team-highlights.md](references/team-highlights.md).
Build one plan and one output per requested team from the remade event clips.
Name each output `<球队>-球队精彩集锦.mp4`.
Do not combine opponents into one team reel.

### 5. Build the game highlight reel

Read [references/game-highlight.md](references/game-highlight.md).
Build one match-wide reel from `reports/matches.csv`, with both teams interleaved in chronological match order.
This is a required and separate deliverable; do not substitute either team's reel for it.
Default to an 8-10 minute output named `比赛精彩集锦_精选8-10分钟.mp4`.
Render per-segment top-left player statistics and event descriptions for the viewer-facing output.
The viewer-facing game highlight must be delivered at 1920×1080. Preserve
native 1080p sources; when the accepted source is 720p, upscale only the final
viewer-facing reel with a high-quality scaler instead of enlarging every
intermediate event clip.

### 6. Verify local deliverables

Require all of the following:

- Full decode succeeds for the pure cut and every player reel.
- Full decode succeeds for every team and game reel.
- Pure-cut contact sheet contains no warmup, long dead air, or score/stat holding page.
- Final pure-cut seam evidence and compact seam video contain no visible cut jump, duplicate/blank frame, or broken immediate continuation.
- Local player reel count matches `players.csv`.
- Each team plan contains only that team, includes its expected players, and has no source-overlapping duplicate possessions.
- The game reel represents both teams, covers decisive late-game events when present, stays within its configured duration bounds, and has no duplicate possession clusters.
- The final viewer-facing game reel is exactly 1920×1080, regardless of whether
  the accepted source was native 1080p or required final-stage upscaling.
- The game reel contact sheet is visually accepted and its full decode succeeds.
- No accepted source or previous output was overwritten.
- Deliverable directories contain only intended `.mp4` files; exclude `.DS_Store`, reports, concat lists, proxies, and debug frames.

Run the deterministic standard-package gate before the final upload:

```bash
python3 "$SKILL_DIR/scripts/validate_standard_delivery.py" \
  --run-dir "runs/<matchID>" \
  --out "runs/<matchID>/output/delivery/standard-delivery-manifest.json" \
  --full-decode
```

Do not start final sync unless this reports `status: complete`.

### 7. Sync to Baidu Netdisk

Run a dry-run first:

```bash
python3 "$SKILL_DIR/scripts/baidu_sync.py" \
  --target "/篮球/Alpha球会/比赛目录" \
  --pure "output/pure-cut/比赛_纯享版_1080p.mp4" \
  --personal-dir "output/player-clips-front15/个人精彩集锦" \
  --events-dir "output/player-clips-front15/个人精彩片段" \
  --team-highlight "output/team-highlights/主队-球队精彩集锦.mp4" \
  --team-highlight "output/team-highlights/客队-球队精彩集锦.mp4" \
  --game-highlight "output/game-highlight/比赛精彩集锦_精选8-10分钟_数据标注版.mp4" \
  --attachment "output/球评_比赛.md" \
  --attachment "output/球评海报/比赛_球评海报.html" \
  --attachment "output/球评海报/比赛_球评海报.png" \
  --report "output/delivery/baidu-sync-report.json"
```

Inspect the plan, then add `--execute`.
Every deliverable selector is optional, but at least one is required.
The script uploads the pure cut to the game folder, player reels to `个人精彩集锦/`, remade events to `个人精彩片段/`, each `--team-highlight` file to `球队精彩集锦/`, and each `--game-highlight` file to `比赛精彩集锦/`.
The legacy `--highlight` option remains an alias for `--game-highlight`.
Each `--attachment` is uploaded explicitly to the match root.
It uploads `.mp4` files explicitly instead of recursively, so hidden files cannot leak into the cloud.
It maps local names to collision-free Baidu-compatible names without changing local files.
It rejects known CLI failure output even when the CLI exits with status 0, then verifies every remote path and exact byte count.

Do not delete or overwrite remote files unless the user explicitly authorizes that action.
Use `--policy skip` by default; use `rsync` or `overwrite` only when requested.

### 8. Report completion

Before reporting completion, assert that the standard package contains the pure
cut, match-wide game highlight, player reels, and commentary HTML/image. Treat a
missing standard item as an incomplete delivery, even when every requested
upload command itself succeeded.

Also require `final-visual-review.json` to be `auto_approved` or explicitly
`approved` with every required check approved.

Report:

- Source URL and match ID without authentication parameters.
- Local source, pure cut, event clip, player reel, team reel, and game reel counts.
- Game reel duration, selected-event count, represented teams, and contact-sheet path.
- Deleted pure-cut duration and final duration.
- Remote target, any local-to-remote filename mappings, player/team/game reel counts, and exact verified byte total.
- Failed or skipped items and the exact resume command.

## Resume rules

Read [references/workflow-contract.md](references/workflow-contract.md).
Resume from verified artifacts, not from conversational claims.
Never redownload, rerender, or reupload a valid artifact solely because the previous agent stopped.
