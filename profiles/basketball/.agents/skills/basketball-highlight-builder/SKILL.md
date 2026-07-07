---
name: basketball-highlight-builder
description: Build basketball highlight reels from labeled event clips or full-game cut clips. Use when Codex needs to create, reorder, trim, de-duplicate, validate, or label basketball highlight videos; handle clips named with team, jersey number, player, event, period, and timestamp; preserve source videos while producing new MP4 outputs; or prepare structured event plans for later tactical analysis.
x-provenance: local
x-owner: cm
x-source-note: created from local basketball highlight workflow
---

# Basketball Highlight Builder

## Core Workflow

1. Inventory clips before editing. Parse team, jersey number, player, event type, period, clock/timestamp, source path, and duration into a JSON plan.
2. Filter to the requested team first. Keep opponent clips out unless the user explicitly asks for both teams.
3. Exclude unusable clips early: missing scoreboard, pause screens, duplicate replays, wrong team, or stale quarter-transition frames.
4. De-duplicate same-possession clips with a small clock window. Prefer made shots, then blocks/steals, then assists; apply a player bonus when the user asks for more of one player.
5. Sort by period order: first, second, third, fourth, overtime. Do not assume filename time is always true game order. If the scoreboard regresses, manually reorder the plan by visible scoreboard progression.
6. Trim tails when clips feel slow. The common setting from this project is `--trim-tail-seconds 8`.
7. Build a new output file. Never overwrite a previous accepted cut unless the user explicitly asks.
8. Validate with `ffprobe`, extracted frames around suspicious timestamps, and a count of clips/player distribution when relevant.

## Preferred Script

Use `scripts/build_basketball_highlight.py` when the current repo does not already have a better local pipeline.

Example for Chinese-labeled clips:

```bash
python /Users/cm/Documents/me/Skills/basketball-highlight-builder/scripts/build_basketball_highlight.py \
  --root . \
  --clip-dir 个人集锦 \
  --team 风暴队 \
  --trim-tail-seconds 8 \
  --dedupe-window-seconds 5 \
  --priority-player 李天驰 \
  --plan-json data/highlight_plan.json \
  --concat-file data/highlight_concat.txt \
  --output output/highlight_labeled.mp4 \
  --overlay-labels
```

If Pillow is not installed and labels are requested, run with a temporary dependency:

```bash
uv run --with Pillow python /Users/cm/Documents/me/Skills/basketball-highlight-builder/scripts/build_basketball_highlight.py ...
```

## Ordering Rules

Use filename time only as a first pass. For this dataset, some third-quarter filenames did not match visible scoreboard progression, so the final accepted cut required manual plan reordering.

When a user reports score regression:

- Map output timestamp to the plan clip using cumulative effective durations.
- Extract frames before and after the timestamp.
- Identify whether the issue is stale source frames, wrong period ordering, duplicate same-possession clips, or filename time mismatch.
- Patch the plan JSON order, then rebuild to a new output path.

## Label Overlay

For each clip, use a concise top-left label:

```text
30号 李天驰 2分命中
35号 陈君春 抢断
62号 戴庆标 3分命中
```

Prefer a semi-transparent dark rectangle with white text. Keep labels away from the bottom scoreboard. If ffmpeg lacks `drawtext`, render text to transparent PNGs with Pillow and use `overlay=...:shortest=1`.

## Validation Checklist

- Confirm the original accepted video still exists.
- Confirm new output duration and codec:

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,pix_fmt,width,height,r_frame_rate -of json output/new.mp4
```

- Extract at least one early frame and one previously problematic timestamp:

```bash
ffmpeg -y -ss 00:00:02 -i output/new.mp4 -frames:v 1 output/audit_0002.jpg
ffmpeg -y -ss 00:02:57 -i output/new.mp4 -frames:v 1 output/audit_0257.jpg
```

- Inspect the frames visually. Verify labels are readable, scoreboard remains visible, and score does not regress at known problem points.

## Reference

Read `references/highlight-workflow.md` when adapting this workflow to a new repo or explaining the plan/build/debug loop.
