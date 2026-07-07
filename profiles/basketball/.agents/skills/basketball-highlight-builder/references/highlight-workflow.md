# Basketball Highlight Workflow Notes

## Clip Filename Contract

Default pattern:

```text
风暴队 30号 李天驰 2分命中 第三节 20_49.mp4
```

Fields:

- team: `风暴队`
- number: `30`
- player: `李天驰`
- event: `2分命中`, `3分命中`, `助攻`, `抢断`, or `盖帽`
- period: `第一节`, `第二节`, `第三节`, `第四节`, `加时1`
- timestamp: `20_49`

Treat timestamps as approximate labels, not guaranteed scoreboard order.

## Scoring and Dedupe Defaults

Selection score:

- `3分命中`: 7
- `2分命中`: 6
- `盖帽`: 5
- `抢断`: 5
- `助攻`: 4

Duplicate-pick priority:

- `3分命中`: 50
- `2分命中`: 40
- `盖帽`: 35
- `抢断`: 30
- `助攻`: 20

When the user asks for more of a player, add a meaningful tie-break bonus for that player during duplicate selection. Do not group one player's clips together; final order still follows period/time/scoreboard logic.

## Known Failure Modes

- Filename time order can conflict with visible scoreboard progression.
- Source clips can begin with a stale scoreboard or quarter-end screen.
- Same possession may produce both assist and made-shot clips; keep one unless the user asks for both.
- Broadcast pause screens should be excluded.
- Tail seconds often contain walking/reset; trim 6-8 seconds for snappier reels.

## Output Conventions

Use descriptive names and preserve accepted versions:

```text
output/highlight_all_deduped_trim8_score_checked.mp4
output/highlight_all_deduped_trim8_score_checked_labeled.mp4
```

Keep plan and concat files beside the output for reproducibility:

```text
data/highlight_plan_*.json
data/highlight_concat_*.txt
```
