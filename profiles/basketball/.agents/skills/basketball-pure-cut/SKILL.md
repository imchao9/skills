---
name: basketball-pure-cut
description: Use this skill when cutting a basketball full-game replay into a pure-play version by removing warmups, pauses, black screens, waiting segments, dead air, score-table/overlay breaks, or non-game footage. It provides a 480p proxy workflow, automatic candidate detection, CSV-based deletion, ffmpeg validation, and an escalation path from conservative to aggressive cuts.
x-provenance: local
x-owner: cm
x-source-note: created from local basketball video editing workflow
---

# Basketball Pure Cut

Use this skill for basketball "纯享版"剪辑: keep real play, remove practice/warmup, waiting, black screens, pauses,主播暂离, dead air, and obvious non-game interludes. Prefer a 480p proxy first, then apply the final cut to the chosen output resolution after the user accepts timing quality.

Bundled scripts:

- `scripts/pure_cut_editor.py`: make a 480p proxy, invert a delete CSV into keep ranges, render the cut video, and write a JSON report.
- `scripts/pure_cut_candidate_detector.py`: scan a proxy video and produce candidate deletion ranges from luminance, frame motion, audio RMS, freeze/low-activity segments, and optional opening warmup removal.
- `scripts/pure_cut_review_sheet.py`: read a deletion CSV, extract candidate start or midpoint frames, create a contact sheet, and write a tile-index CSV for fast review.

## Workflow

1. Identify the source video and probe it. If a directory contains both a short highlight file and a long replay, prefer the longest plausible full replay as `$VIDEO`; do not use an existing highlight reel as the source unless the user explicitly asks to trim that file.

```bash
ffprobe -v error -show_entries format=duration,size -show_streams -of json "$VIDEO"
```

2. Create a 480p proxy before visual analysis.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_editor.py" "$VIDEO" \
  --make-proxy \
  --proxy-output output/pure-cut/proxy/input_480p_proxy.mp4 \
  --force
```

3. Generate automatic deletion candidates against the proxy. Start conservative, then increase aggressiveness only after reviewing thumbnails.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_candidate_detector.py" \
  output/pure-cut/proxy/input_480p_proxy.mp4 \
  --output-csv output/pure-cut/reports/auto_delete_list.csv \
  --report output/pure-cut/reports/auto_delete_report.json
```

Create a candidate midpoint review sheet immediately after detection. Midpoints are better than start frames because a candidate may begin near live play and only become obviously dead air several seconds later.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_review_sheet.py" \
  output/pure-cut/proxy/input_480p_proxy.mp4 \
  --delete-csv output/pure-cut/reports/auto_delete_list.csv \
  --output output/pure-cut/debug/auto_delete_mid_sheet.jpg \
  --index-csv output/pure-cut/debug/auto_delete_mid_sheet.index.csv \
  --position mid \
  --force
```

If the source begins with obvious warmup/practice, pass a concrete opening boundary:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_candidate_detector.py" \
  output/pure-cut/proxy/input_480p_proxy.mp4 \
  --drop-opening-until 00:04:00 \
  --output-csv output/pure-cut/reports/auto_delete_list.csv \
  --report output/pure-cut/reports/auto_delete_report.json
```

4. Review the candidate CSV before rendering. Copy only visually supported removals into `output/pure-cut/reports/reviewed_delete_list.csv`, merging nearby obvious dead-air ranges by hand when it makes the final cut cleaner. Keep the original auto CSV as evidence.

Use this rule of thumb:

- Keep borderline live-play candidates such as free throws, inbound setup, active half-court spacing, players walking into immediate continuation, or a referee holding play for only a few seconds.
- Delete obvious empty-court waits, long timeout/dead-air segments, black screens, warmup/practice, huddles, replay holding pages, and long score-table/overlay breaks.
- If a candidate group contains mixed content, prefer a smaller reviewed range over blindly using every auto-detected micro-cut.

5. Render the proxy cut from the reviewed deletion CSV.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_editor.py" \
  output/pure-cut/proxy/input_480p_proxy.mp4 \
  --delete-csv output/pure-cut/reports/reviewed_delete_list.csv \
  --output output/pure-cut/input_pure_480p.mp4 \
  --report output/pure-cut/reports/input_pure_480p_report.json \
  --force
```

6. Verify the proxy before presenting or rendering the full-resolution result.

```bash
ffmpeg -v error -i output/pure-cut/input_pure_480p.mp4 -f null -
ffmpeg -hide_banner -i output/pure-cut/input_pure_480p.mp4 \
  -vf "blackdetect=d=0.5:pix_th=0.10" -an -f null -
```

Also generate a contact sheet for fast human review:

```bash
ffmpeg -y -i output/pure-cut/input_pure_480p.mp4 \
  -vf "fps=1/120,scale=320:-1,tile=5x6" \
  output/pure-cut/debug/input_pure_480p_contact_sheet.jpg
```

7. After the proxy passes review, render the final full-resolution cut with the same reviewed CSV. The editor prints each keep segment as it renders, which is useful for long 1080p jobs.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_editor.py" "$VIDEO" \
  --delete-csv output/pure-cut/reports/reviewed_delete_list.csv \
  --output output/pure-cut/input_pure_1080p.mp4 \
  --report output/pure-cut/reports/input_pure_1080p_report.json \
  --force
```

For a quick timing smoke test on the original file, use `--copy-codecs` first. This is much faster, but cut points can be less accurate because they follow codec/keyframe boundaries; do not treat it as the final deliverable unless the timing is acceptable.

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_editor.py" "$VIDEO" \
  --delete-csv output/pure-cut/reports/reviewed_delete_list.csv \
  --output output/pure-cut/input_pure_1080p_fastcopy.mp4 \
  --report output/pure-cut/reports/input_pure_1080p_fastcopy_report.json \
  --copy-codecs \
  --force
```

If full-resolution rendering is too slow and exact archival quality is not required, prefer `--preset ultrafast --crf 25` for a faster draft. Keep the default `--preset veryfast --crf 23` for the normal final pass.

## Aggressiveness

Default detection is intentionally conservative. It catches black/dark screens, freezes, and low-motion/low-audio waiting. It will not reliably remove active warmups or table overlays unless parameters or extra rules identify them.

For a more aggressive pass, use:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/pure_cut_candidate_detector.py" "$PROXY" \
  --drop-opening-until 00:04:00 \
  --black-luminance 0.18 \
  --min-wait 5 \
  --min-freeze 3 \
  --wait-motion 0.020 \
  --wait-audio 0.020 \
  --merge-gap 4 \
  --output-csv "$CSV" \
  --report "$REPORT"
```

Increase these carefully:

- `--drop-opening-until`: best for known warmup/practice at the start; do not infer this from numeric time unless visual evidence supports it.
- `--black-luminance`: higher catches dim pause pages but can remove legitimate dark footage.
- `--wait-motion` and `--wait-audio`: higher catches more dead air but can delete slow half-court setup.
- `--min-wait` and `--min-freeze`: lower catches shorter pauses but increases false positives.
- `--merge-gap`: higher merges nearby micro-cuts into cleaner deletion spans.

## Review Rules

Treat the generated CSV as candidate deletion, not ground truth. Basketball semantics matter:

- Do not label a clip as highlight or pure-play only because of crowd noise, clock changes, or motion.
- A valid pure-play keep segment should show active possession, transition, inbound, free throw, rebound scramble, or immediate game continuation.
- Delete warmup/practice, timeout huddles, dead air, black screens,主播暂离, replay holding pages, long scoreboard/table overlays, and non-game setup.
- If the user says "不要通过数字去剪辑，而是通过进球/比赛内容", use timestamps only as implementation cut points after visual or model-backed event judgment.

## Progress and Long Runs

Full-resolution rendering may be slow because the script re-encodes every kept range for accurate cuts, then concatenates them. This is expected. If there is no visible output file yet, check for active per-segment ffmpeg work instead of assuming it is stuck:

```bash
ps -axo pid,etime,pcpu,pmem,command | rg 'pure_cut_editor.py|ffmpeg' | rg -v 'rg'
```

The final output file appears only after the temporary keep clips are rendered and concatenated.

## Known Limits

The bundled detector is signal-based. It does not truly understand made baskets, fouls, timeouts, player identities, or scoreboard-table graphics. For score-table/overlay pages that still contain motion or audio, add a visual overlay detector or manually review contact sheets instead of only raising low-motion thresholds.
