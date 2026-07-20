---
name: basketball-video-delivery
description: Deliver a basketball game from an authenticated Xiaoqiumi match page to verified Baidu Netdisk outputs. Use when Codex needs to download a full-game replay from a xiaoqiumi.com MatchVideoList URL, create a reviewed pure-play cut, remake labeled event clips and per-player reels, build separate team highlight reels or a condensed game reel, resume a partially completed basketball video run, or upload only validated deliverables to a specific Baidu Netdisk game folder.
---

# Basketball Video Delivery

Run this as a resumable delivery pipeline.
Reuse specialized skills for editing; do not duplicate their algorithms here.

## Required inputs

Collect or infer:

- Xiaoqiumi `MatchVideoList` URL and match ID.
- Local workspace with at least twice the expected source size free.
- Full remote Baidu Netdisk target path.
- Desired outputs: pure cut, event clips, player reels, one reel per requested team, and one match-wide game highlight reel.

Never store Xiaoqiumi cookies, signed URLs, Baidu cookies, BDUSS, STOKEN, or passwords in the workspace or reports.

## Pipeline

### 1. Acquire the replay and labeled clips

Read [references/xiaoqiumi-download.md](references/xiaoqiumi-download.md).
Use an authenticated browser session to open the supplied match page.
Select `回放`, identify the longest plausible full-game item, and obtain its current `file_url` from the `Basketball/Match/MatchVideoList` response or download control.
Download into `source/` with a `.part` suffix and rename atomically only after completion.
Download labeled event clips when the page provides them; preserve their original titles as filenames.

Verify with:

```bash
ffprobe -v error -show_entries format=duration,size -show_streams -of json "$SOURCE"
find "$CLIPS_DIR" -maxdepth 1 -type f -name '*.mp4' | wc -l
```

Stop for user login if the page redirects to `SignIn`.
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

### 6. Verify local deliverables

Require all of the following:

- Full decode succeeds for the pure cut and every player reel.
- Full decode succeeds for every team and game reel.
- Pure-cut contact sheet contains no warmup, long dead air, or score/stat holding page.
- Local player reel count matches `players.csv`.
- Each team plan contains only that team, includes its expected players, and has no source-overlapping duplicate possessions.
- The game reel represents both teams, covers decisive late-game events when present, stays within its configured duration bounds, and has no duplicate possession clusters.
- The game reel contact sheet is visually accepted and its full decode succeeds.
- No accepted source or previous output was overwritten.
- Deliverable directories contain only intended `.mp4` files; exclude `.DS_Store`, reports, concat lists, proxies, and debug frames.

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
  --report "output/delivery/baidu-sync-report.json"
```

Inspect the plan, then add `--execute`.
Every deliverable selector is optional, but at least one is required.
The script uploads the pure cut to the game folder, player reels to `个人精彩集锦/`, remade events to `个人精彩片段/`, each `--team-highlight` file to `球队精彩集锦/`, and each `--game-highlight` file to `比赛精彩集锦/`.
The legacy `--highlight` option remains an alias for `--game-highlight`.
It uploads `.mp4` files explicitly instead of recursively, so hidden files cannot leak into the cloud.
It verifies login, local media metadata, remote names, counts, and displayed sizes.

Do not delete or overwrite remote files unless the user explicitly authorizes that action.
Use `--policy skip` by default; use `rsync` or `overwrite` only when requested.

### 8. Report completion

Report:

- Source URL and match ID without authentication parameters.
- Local source, pure cut, event clip, player reel, team reel, and game reel counts.
- Game reel duration, selected-event count, represented teams, and contact-sheet path.
- Deleted pure-cut duration and final duration.
- Remote target, remote pure filename, player/team/game reel counts, and total displayed size.
- Failed or skipped items and the exact resume command.

## Resume rules

Read [references/workflow-contract.md](references/workflow-contract.md).
Resume from verified artifacts, not from conversational claims.
Never redownload, rerender, or reupload a valid artifact solely because the previous agent stopped.
