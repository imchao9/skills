---
name: basketball-player-clips
description: Generate basketball player event clips and reels from a full replay plus labeled event references. Use when event identity, source alignment, action windows, official-stat reconciliation, and per-player review evidence must be verified before delivery.
---

# Basketball Player Clips

Use this skill to remake event clips from a source replay when metadata or existing short clips identify candidate events. Metadata and filenames are claims, not identity proof. A personal reel is deliverable only after location, official-stat, and action-frame gates all pass.

When a user reports a wrong scorer, a shifted timestamp was manually accepted,
or the locator produced widespread adjustments, read
[the player-event ownership incident](../basketball-video-delivery/references/player-event-ownership-incident.md)
and apply its full-batch incident response. One confirmed bad event invalidates
the current player-event batch; repairing only that reel is insufficient.

## Non-negotiable gates

1. `event-location-audit.json` must be `complete`. Any alignment shifted by more than 30 seconds or whose aligned hash is over 128 bits worse than the raw best match is `blocked`; do not render it automatically.
2. `event-stat-audit.json` must exactly reconcile each player's `2分命中`, `3分命中`, `助攻`, `抢断`, and `盖帽` counts with normalized official player totals. Unknown players and missing/extra events block all reels.
3. `action-evidence.json` must be fingerprint-bound to `rendered-matches.csv`. Inspect every scoring evidence frame and confirm the player completing the basket matches the label. Set identity approval only after this full review, not from a sparse contact sheet.
4. Review period and game clock independently. A plausible player name does not validate the source timestamp, and a monotonic sequence must never override a poor visual match silently.

## Core Workflow

1. Confirm the source full-game replay and old event clip directory.

```bash
ffprobe -v error -show_entries format=duration,size -of json "$SOURCE"
find "$CLIPS_DIR" -maxdepth 1 -type f -name '*.mp4' | wc -l
```

2. Run the remake script. Default behavior:

- Event-direct thumbnails are treated as reference frames, not guaranteed action frames.
- Event-direct clips retain 15 seconds before and 8 seconds after the reference frame so the finish is visible.
- For platform reference clips, cover the matched reference clip instead of assuming `old_start + 7s`; use a fixed offset only as an explicitly reviewed legacy override.
- Existing reels, full-game highlight videos, and replay copies in the clip directory are skipped.
- Outputs include remade event clips, per-player reels, a full-game highlight reel, CSV reports, and optional contact sheets.
- Viewer-facing event clips, personal reels, and full-game highlights are data-labeled by default. Every label includes team, jersey/player, action, period, and game clock; final filenames include `数据标注版`.
- Final reels are sorted by game order: 第一节, 第二节, 第三节, 第四节, then 加时. Within each period, clips are sorted by the period clock from high to low because basketball game clocks count down.
- Accept period clocks written as `MM:SS`, `MM_SS`, or `MM-SS`; normalize them before sorting and window calculations.

```bash
python3 "$SKILL_DIR/scripts/remake_player_clips.py" \
  --source "$SOURCE" \
  --clips-dir "$CLIPS_DIR" \
  --output-dir output/player-clips-front15 \
  --contact-sheets
```

3. Verify the three audit reports, then decode output before reporting completion.

```bash
ffmpeg -v error -i output/player-clips-front15/比赛精彩集锦_比赛时间顺序_数据标注版.mp4 -f null -
```

4. For a viewer-facing game highlight reel, build a condensed version from `reports/matches.csv`. This clusters nearby or source-overlapping events in the same period, keeps one clip per cluster, and prefers the assist clip when an assist and made basket describe the same normal play. In clutch time, made baskets can override assist preference.

```bash
python3 "$SKILL_DIR/scripts/make_condensed_reel.py" \
  --matches-csv output/player-clips-front15/reports/matches.csv \
  --output output/player-clips-front15/比赛精彩集锦_精选8-10分钟_数据标注版.mp4 \
  --min-seconds 480 \
  --target-seconds 520 \
  --max-seconds 570 \
  --cluster-window 12 \
  --overlap-gap 2 \
  --selected-min-gap 2 \
  --contact-sheet
```

## Review Rules

- Treat unlabeled output as `raw_intermediate` only. Use `--raw-no-overlay` solely for diagnostics; never deliver or upload it.
- Verify every made-basket action evidence frame; early/middle/late sampling is insufficient for player identity.
- Treat a still frame as reviewable evidence only when it shows the action clearly. If the finish or scorer is ambiguous, inspect multiple frames or the short clip and keep identity approval false.
- Treat filename labels as event metadata, not visual proof. If a specific clip looks wrong, inspect the generated `reports/matches.csv` row and the event frame.
- High visual-hash scores can happen on repeated empty-court or similar half-court scenes. Any blocked locator row stops the full batch; never approve it merely because monotonic order looks plausible.
- Keep all old clips intact. Write remade clips to a new output directory.
- Prefer game-time-ordered reels for viewing. Preserve filenames for individual remade clips.
- Keep viewer-facing full-game highlight reels around 8-10 minutes when the game is close or goes to overtime. The all-event reel is useful for audit, but too long for normal viewing.
- When scoring and assist clips refer to the same possession, prefer the assist clip because it usually preserves the pass setup and made basket in one shot. If no assist is available, prefer higher-impact actions such as 3-pointers, blocks, steals, then 2-pointers.
- For close games, boost fourth-quarter closing minutes and overtime. Make sure late made baskets are represented, even if the same possession also has an assist clip.
- Avoid adjacent repeated footage by checking `new_start`/`new_end` source windows, not only period-clock labels.
- Apply the same source-window overlap rule to player reels. If two clips for the same player cover the same source window, keep one representative clip; prefer 3-pointers, blocks, steals, 2-pointers, then assists unless the user asks for a different player-specific emphasis.
- If the source has post-game handshake footage, append a short 10-20 second closing shot after the final scoring clip.

## Useful Options

```bash
python3 "$SKILL_DIR/scripts/remake_player_clips.py" \
  --source "$SOURCE" \
  --clips-dir "$CLIPS_DIR" \
  --output-dir "$OUT" \
  --old-event-offset 7 \
  --default-pre 15 \
  --default-post 8 \
  --assist-pre 15 \
  --assist-post 8 \
  --resume \
  --crf 20 \
  --preset veryfast
```

`--old-event-offset 7` is legacy-only and requires visual confirmation that the reference action really occurs at that offset. Use `--player-name NAME` only for diagnosis; a one-player pass never substitutes for the full event/stat audit.

When disk space is tight and the goal is only a condensed full-game highlight reel, skip large intermediate reels:

```bash
python3 "$SKILL_DIR/scripts/remake_player_clips.py" \
  --source "$SOURCE" \
  --clips-dir "$CLIPS_DIR" \
  --output-dir "$OUT" \
  --default-pre 15 \
  --default-post 8 \
  --assist-pre 15 \
  --assist-post 8 \
  --resume \
  --skip-full-reel \
  --skip-player-reels
```

For Xiaoqiumi event-direct delivery, the standard runner uses a low-peak mode:
it renders one player's temporary event set, concatenates that player's reel,
then removes the temporary set before moving to the next player. The condensed
game builder materializes only selected missing event clips from the `source`,
`new_start`, and `new_end` columns. Do not remove those columns from the reviewed
matches CSV; they are the recovery contract.
