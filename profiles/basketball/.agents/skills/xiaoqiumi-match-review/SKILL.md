---
name: xiaoqiumi-match-review
description: Fetch Xiaoqiumi basketball match data, normalize box-score facts, draft Chinese post-game commentary, and produce review poster layouts in five visual styles. Use when the user gives a Xiaoqiumi match URL or matchid and wants a 球评, 赛后复盘, 数据摘要, or basketball review poster.
x-provenance: local
x-owner: cm
x-source-note: created from local Xiaoqiumi basketball commentary workflow
---

# Xiaoqiumi Match Review

Use this skill when the user provides a 小球迷比赛链接, 小球迷 `matchid`, scoreboard screenshot, or asks to generate 篮球球评 / 赛后复盘 / 球评海报 from Xiaoqiumi data.

## Workflow

1. If the user gives a competition page, fetch the recent match list first.
The default mode follows the competition page's current period and current round.
Use `--all-rounds` when the user wants a broader scan.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/fetch_xiaoqiumi_competition.py" \
  "https://h5static.xiaoqiumi.com/littleFans/index.html?...competitionID=400012066&sportType=1" \
  --out output/xiaoqiumi-competition-400012066.json \
  --list-md output/xiaoqiumi-competition-400012066-recent.md
```

For a broader nearby-match scan:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/fetch_xiaoqiumi_competition.py" \
  "https://h5static.xiaoqiumi.com/littleFans/index.html?...competitionID=400012066&sportType=1" \
  --all-rounds \
  --recent-count 20 \
  --out output/xiaoqiumi-competition-400012066-all.json \
  --list-md output/xiaoqiumi-competition-400012066-nearby.md
```

2. Fetch the real single-match data before writing.
Do not rely on visible DOM text when the page shows zeroed stats, delayed loading, or a security check.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/fetch_xiaoqiumi_match.py" \
  "https://h5static.xiaoqiumi.com/littleFans/index.html?...matchid=400365844&sportType=1" \
  --out output/xiaoqiumi-400365844.json \
  --facts-md output/xiaoqiumi-400365844-facts.md
```

3. Read the facts Markdown and normalized JSON.
Confirm teams, final score, match date, quarter scores, team stats, and player leaders.

4. Draft the article from data plus narrative.
Use the local template script only as a first draft when speed matters.
For a final deliverable, improve the draft with the user's requested tone and any provided reference article.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/generate_xiaoqiumi_commentary.py" \
  output/xiaoqiumi-400365844.json \
  --out output/xiaoqiumi-400365844-commentary.md
```

5. Render posters after the text direction is settled.
Choose one style, or generate all five for comparison.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/render_xiaoqiumi_poster.py" \
  output/xiaoqiumi-400365844.json \
  --style all \
  --out-dir output/posters \
  --photo /absolute/path/to/court.jpg \
  --scoreboard-photo /absolute/path/to/scoreboard.jpg
```

6. Screenshot the HTML poster in a browser when the user needs a PNG.
Prefer deterministic HTML for Chinese text accuracy, then use image generation only for background art or visual variants that do not need exact small text.

## Data Rules

- `CompetitionInfo` is the source for competition name, season, current periods, and event metadata.
- `CompPeriodList` and `CompSchedule` are the competition-page schedule sources.
- Use `CompSchedule` rather than the global `MatchList` when the user gives a competition page and needs matches from that specific competition.
- `MatchInfo` is the source for teams, score, date, competition, stadium, and tabs.
- `MatchDetail` with the `赛况` tab is the source for period scores, team stats, best players, and player box scores.
- Treat `sectionList`, `homePlayers`, `awayPlayers`, and team stat objects as more reliable than page DOM.
- Overtime labels can be confusing in Xiaoqiumi output.
Label extra period columns as `OT1`, `OT2`, but avoid claiming the regulation game was tied unless the data proves it.
- If the score in a photo conflicts with API data, say so and ask whether to use the photo as override.

## Writing Rules

- Start with a strong title containing the winner, score, and main story.
- The body should combine data and narrative.
- In Chinese prose, always put attempts before makes and include an explicit
  action word: write `78投19中`, `22投3中`, or `30次罚球命中12球`. Never
  convert a box-score `命中/出手` value such as `19/78` into `19中78`.
  Slash-form tables must label their order explicitly as `命中/出手`.
- Mention both teams with respect, especially when the losing side has clear leaders or late-game resistance.
- Avoid only listing numbers.
Turn the numbers into a game story: scoring distribution, rebounding edge, turnovers, shooting efficiency, rotation depth, key players, and next-match outlook.
- Do not invent injuries, conflicts, tactical details, or off-court stories unless the user provides them.

## Poster Styles

Use these stable style names:

- `cinematic-dark`: dark court-photo background, large score, dramatic sports-review tone.
- `scoreboard-card`: scoreboard-centric layout, heavier stats blocks, good for WeChat group recap.
- `newspaper`: white editorial layout, headline plus longer article excerpt, good for text-heavy review.
- `neon-energy`: high-contrast neon sports graphic, good for promotional sharing.
- `minimal-clean`: clean white layout, compact facts, good for formal summary.

Read `references/api-contract.md`, `references/commentary-style.md`, and `references/poster-styles.md` before adapting the workflow to a new data shape.
