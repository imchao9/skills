---
name: basketball-highlight-builder
description: Build basketball highlight reels from labeled event clips or full-game cut clips. Use when Codex needs to create, reorder, trim, de-duplicate, validate, or label basketball highlight videos; handle clips named with team, jersey number, player, event, period, and timestamp; preserve source videos while producing new MP4 outputs; or prepare structured event plans for later tactical analysis.
metadata:
  provenance: local
  owner: cm
  source-note: created from local basketball highlight workflow
---

# Basketball Highlight Builder

## Core Workflow

1. Inventory clips before editing. Parse team, jersey number, player, event type, period, clock/timestamp, source path, and duration into a JSON plan.
   Stop with an actionable error when no clip matches the filename contract or the requested team has no parsed clips.
   When the source is a player-event pipeline, also require passed location/stat audits and action evidence fingerprint-bound to the exact reviewed matches CSV. Do not build from an older, manually edited, or unaudited CSV.
2. Filter to the requested team first. Keep opponent clips out unless the user explicitly asks for both teams.
3. Exclude unusable clips early: missing scoreboard, pause screens, duplicate replays, wrong team, or stale quarter-transition frames.
4. De-duplicate same-possession clips with a small clock window. Prefer made shots, then blocks/steals, then assists; apply a player bonus when the user asks for more of one player.
5. Sort by period order: first, second, third, fourth, overtime. Do not assume filename time is always true game order. If the scoreboard regresses, manually reorder the plan by visible scoreboard progression.
6. Trim tails when clips feel slow. The common setting from this project is `--trim-tail-seconds 8`.
7. Build a new output file. Never overwrite a previous accepted cut unless the user explicitly asks.
8. Validate with `ffprobe`, extracted frames around suspicious timestamps, and a count of clips/player distribution when relevant.

## Viewer-facing data-label contract

- Personal event clips, personal reels, team reels, and game highlights are data-labeled by default.
- Every visible event label must include team, jersey number/player, action, period, and game clock. Add official full-game totals only when they come from the normalized match JSON.
- Name deliverables with `_数据标注版.mp4` and record `data_label_status: data_labeled` in the plan/report.
- `--raw-no-overlay` is for diagnostics or temporary concatenation only. Never upload, hand off, or count a `raw_intermediate` file as complete.

The build gate passes when upstream event identity is approved, the plan contains at least one intended clip, the concat list count matches the plan, the output fully decodes, and reviewed frames preserve the scoreboard and readable labels. De-duplication and ordering may remove events; they must never be used to repair uncertain event ownership.

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
  --output output/highlight_数据标注版.mp4
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
风暴队｜30号 李天驰｜2分命中｜第四节 01:24
风暴队｜35号 陈君春｜抢断｜第二节 06:18
风暴队｜62号 戴庆标｜3分命中｜第三节 02:40
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
