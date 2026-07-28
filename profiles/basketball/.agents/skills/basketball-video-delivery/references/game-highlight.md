# Match-wide game highlight

Create this deliverable independently from both team reels.
It tells the story of the whole game, so it must include both teams and preserve chronological match order.

## Default build

Use the accepted `reports/matches.csv` from `$basketball-player-clips` as the event timeline.
When the local pipeline produced separate `matches.csv` and
`rendered-matches.csv` files, normalize the rendered table first:

```bash
python3 "$SKILL_DIR/scripts/prepare_game_highlight_matches.py" \
  --input output/player-clips-front15/reports/rendered-matches.csv \
  --output output/game-highlight/matches-for-game-highlight.csv
```

Use `--team-map OLD=NEW` when an old event title contains a stale team name.
The normalized file adds the deterministic duration and quality columns required
by the condensed-reel builder without re-running video recognition.

Run:

```bash
python3 "$PLAYER_CLIPS_SKILL/scripts/make_condensed_reel.py" \
  --matches-csv output/game-highlight/matches-for-game-highlight.csv \
  --output output/game-highlight/比赛精彩集锦_精选8-10分钟.mp4 \
  --min-seconds 480 \
  --target-seconds 520 \
  --max-seconds 570 \
  --cluster-window 12 \
  --overlap-gap 2 \
  --selected-min-gap 2 \
  --contact-sheet
```

The default duration window is 8:00-9:30, targeting about 8:40.
Nearby or overlapping events from the same possession must become one cluster rather than repeated footage.

## Selection rules

- Include events from both teams; reject a reel that accidentally becomes a one-team reel.
- Preserve source chronology across quarters and overtime.
- Prefer an assist when it already shows the made basket from the same normal possession.
- Prefer the made basket for a clutch possession when that better preserves the decisive play.
- Favor three-pointers, blocks, steals, strong finishes, lead changes, and late fourth-quarter or overtime events.
- Keep enough context before each play to make the action understandable.
- Append 10-20 seconds of post-game handshake or celebration when available and when it fits the maximum duration.

## Acceptance

Record the selected event count, represented teams, duration, and output path in the delivery report.
Require all of the following:

- Duration is within the configured minimum and maximum.
- Both teams appear in the selected events.
- No two selected entries repeat the same overlapping possession cluster.
- Decisive fourth-quarter or overtime events are present when they exist in `matches.csv`.
- The generated contact sheet is visually accepted.
- `ffmpeg -v error -i "$OUTPUT" -f null -` exits zero.

## Viewer-facing labels

Render a two-line top-left card for every selected segment after selection is accepted.
The first line contains jersey number, player, and full-game statistics derived from all labeled events.
The second line describes the current event and should join an assist with its scorer when both exist in the same cluster.
Statistics are limited to labeled points, assists, steals, and blocks; never invent rebounds or other unavailable fields.

```bash
uv run --with Pillow python3 "$SKILL_DIR/scripts/render_game_highlight_labels.py" \
  --matches-csv output/game-highlight/matches-for-game-highlight.csv \
  --selection-csv output/game-highlight/比赛精彩集锦_精选8-10分钟_selection.csv \
  --match-json output/match.json \
  --output output/game-highlight/比赛精彩集锦_精选8-10分钟_数据标注版.mp4
```

Inspect frames from at least one scoring event and one assist event.
Confirm the card does not cover the bottom scoreboard and remains readable on both light and dark footage.
When normalized match JSON is available, pass it with `--match-json` so the card
uses official full-game points, rebounds, assists, steals, and blocks. Without
it, the card explicitly says `已标记` rather than presenting labeled-event
counts as official full-game totals.

## Resolution gate

Deliver the final viewer-facing reel at exactly 1920×1080. If the labeled reel
is still 1280×720 because the accepted source was 720p, upscale the final reel
once with Lanczos and validate the temporary output before replacing the local
deliverable:

```bash
ffmpeg -y -i "$LABELED_REEL" \
  -vf "scale=1920:1080:flags=lanczos" \
  -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$TEMP_1080P"
```

Do not upscale native 1080p inputs or claim that upscaling adds source detail.
