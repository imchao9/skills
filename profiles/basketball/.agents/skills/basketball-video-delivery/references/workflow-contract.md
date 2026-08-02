# Delivery workflow contract

## Stable directories

```text
source/                         downloaded replay and original event clips
output/pure-cut/                proxy, reviewed deletion CSV, final pure cut
output/player-clips-front15/    remade events, player reels, match reports
output/team-highlights/         one plan and accepted reel per team
output/game-highlight/          match-wide plan, contact sheet, and accepted reel
output/delivery/                sanitized delivery and sync reports
```

## Phase gates

| Phase | Complete when |
| --- | --- |
| fast-start | Latest match data is saved, acquisition passes, deterministic preflight finishes or is explicitly skipped, and `fast-start.json` says `ready_for_ai` |
| download-health | Heartbeat is current while running; a completed segment has 100% bytes and no retained chunks; `needs_attention` remains incomplete and blocks downstream work and shutdown |
| review-draft | Pure proxy cut, player reports, labeled 1080p game-highlight draft/contact sheet, commentary HTML/PNG, and `ai-review.json` exist |
| AI review | `ai-review.json` says `approved`; all four quality flags are true; referenced artifacts pass structural checks |
| acquire | Every replay candidate is classified, every selected segment and the assembled final `.mp4` pass validation, assembled duration matches the selected-duration sum, and no active `.part` remains |
| pure-cut | Reviewed CSV exists, full output decodes, final contact sheet is visually accepted |
| player-clips | `matches.csv` and `players.csv` exist, reel count matches players, all reels decode |
| team-highlights | One plan/output exists per requested team, plans contain no opponent clips, all reels decode |
| game-highlight | One 8-10 minute match-wide output represents both teams, decodes fully, and its plan/contact sheet is accepted |
| commentary | Data claims match normalized JSON, article has at least 600 Chinese characters and four review sections, standalone HTML opens without external assets, and browser-rendered PNG passes visual QA |
| standard-package | Pure cut, player reels, 1080p game highlight, commentary Markdown, HTML, and PNG all pass `validate_standard_delivery.py` |
| final-visual | Fingerprints match current outputs; pure-cut seams are reviewed when cuts exist; game/poster are reviewed only when changed after the main review |
| upload | Remote-safe names are collision-free, CLI output contains no failure marker, and every remote path and exact byte count matches the local delivery set |

## Safety rules

- Preserve sources and previously accepted outputs.
- Require explicit user approval for cloud deletion or overwrite.
- Keep credentials outside the workspace and all reports.
- Upload explicit deliverables, never a broad working directory.
- Check free space before proxying or rendering.
- Treat successful command exit as necessary but not sufficient; inspect command output and verify artifacts.
- Permit automatic shutdown only after the requested terminal delivery state is complete. `running`, `retrying`, `needs_attention`, and either visual-review waiting state must keep the machine available.

## Resume decision

Inspect the phase gate artifacts in order.
Resume at the first incomplete gate.
If a gate artifact exists but validation fails, quarantine or write a new output rather than silently accepting or overwriting it.
For replay downloads, reuse retained range chunks only when their manifest still
matches the current remote size, ETag, sanitized path, and range layout. Retry a
health failure at most within the configured attempt budget; after that, expose
`needs_attention` for human diagnosis instead of looping forever.

## AI entry boundary

Keep these operations deterministic and run them before AI review:

- Refresh `MatchInfo` and every required `MatchDetail` tab.
- Enumerate all replay candidates, de-duplicate overlapping long variants, and retain chronological recording segments.
- Download or resume every selected segment and assemble one full editing source; use event metadata, thumbnails, and OCR
  before downloading event videos as alignment references.
- Validate media, expected event count, and partial-file state.
- Build the 480p proxy, signal candidates, review sheet, remade events, and player reels.

Use AI only for ambiguous visual decisions:

- Accept or adjust pure-cut deletion boundaries.
- Review suspicious visual matches and overlapping possessions.
- Choose team and match-wide highlight order, emphasis, and final visual acceptance.
- Audit commentary facts and accept the rendered long-form poster.

Do not place AI reasoning between deterministic commands that can be represented by exit status, reports, counts, media probes, or resumable state.

## Standard runner state machine

Run `scripts/run_standard_delivery.py` as a resumable state machine:

1. First run: deterministic preparation, then `waiting_for_ai`.
2. One AI checkpoint: inspect and, when needed, edit the referenced artifacts.
3. Second run: final render, full decode, package validation, and final visual evidence.
4. If final pixels introduce risk, inspect only required checks in
   `final-visual-review.json`; otherwise the audit auto-approves.
5. Resume: reuse current renders/decode manifest and perform Baidu dry-run or execution.

Never set approval flags merely to unblock the runner. The reviewed proxy,
labeled game-highlight draft, and rendered poster must be the actual artifacts
inspected. If an approved CSV or Markdown file changes, regenerate and inspect
its dependent draft with `refresh_review_command` before resuming.

The final visual contract binds approval to file size, mtime, and hashes of
review inputs. Any later render or edit invalidates approval and regenerates the
evidence. Do not require a second AI review for unchanged player reels, game
highlight, or poster. Show before/after frames for every pure-cut seam and
provide a compact motion video containing roughly two seconds on either side of
each seam, preserving source audio when available.
