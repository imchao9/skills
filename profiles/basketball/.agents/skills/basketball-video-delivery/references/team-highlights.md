# Team highlight reels

Build one independent reel per requested team from the remade event clips.
Do not build a team reel by concatenating player reels because that repeats shared possessions.

## Plan and render

Run the `basketball-highlight-builder` script once per team.
Create the plan first and inspect it before rendering.

```bash
python3 "$HIGHLIGHT_SKILL_DIR/scripts/build_basketball_highlight.py" \
  --root . \
  --clip-dir output/player-clips-front15/个人精彩片段 \
  --team "超流战队" \
  --target-seconds 0 \
  --dedupe-window-seconds 5 \
  --clock-order desc \
  --plan-json output/team-highlights/超流战队.plan.json \
  --concat-file output/team-highlights/超流战队.concat.txt \
  --output output/team-highlights/超流战队-球队精彩集锦.mp4 \
  --plan-only
```

After reviewing the plan, rerun without `--plan-only`.
Use `--overlay-labels` only when the user wants player/action labels.

Repeat for the opposing team with a separate plan and output.

## Selection rules

- Filter by exact team name parsed from filenames before de-duplication.
- Group source-overlapping events from the same possession.
- Prefer a made basket when the team reel should emphasize scoring.
- Prefer the assist when it preserves the setup and made basket in one continuous clip.
- Keep blocks and steals when they start a transition or are a distinct defensive highlight.
- Sort by period order and descending game clock within each period.
- Keep fourth-quarter closing minutes and overtime representative in close games.
- Append a 10-20 second handshake or celebration only to the final team reel, not every player reel.

## Validation

- Confirm every plan row belongs to the requested team.
- Compare player distribution against the labeled event inventory.
- Reject adjacent source-window overlaps unless they represent distinct actions.
- Full-decode the output with `ffmpeg -v error -i <output> -f null -`.
- Inspect early, middle, closing, and overtime frames.
- Write a new version if an accepted reel already exists; do not overwrite it implicitly.
