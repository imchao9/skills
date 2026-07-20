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
| acquire | Final `.mp4` exists, `ffprobe` succeeds, no active `.part` remains |
| pure-cut | Reviewed CSV exists, full output decodes, final contact sheet is visually accepted |
| player-clips | `matches.csv` and `players.csv` exist, reel count matches players, all reels decode |
| team-highlights | One plan/output exists per requested team, plans contain no opponent clips, all reels decode |
| game-highlight | One 8-10 minute match-wide output represents both teams, decodes fully, and its plan/contact sheet is accepted |
| upload | CLI exits zero and remote names/counts match the local delivery set |

## Safety rules

- Preserve sources and previously accepted outputs.
- Require explicit user approval for cloud deletion or overwrite.
- Keep credentials outside the workspace and all reports.
- Upload explicit deliverables, never a broad working directory.
- Check free space before proxying or rendering.
- Treat successful command exit as necessary but not sufficient; verify artifacts.

## Resume decision

Inspect the phase gate artifacts in order.
Resume at the first incomplete gate.
If a gate artifact exists but validation fails, quarantine or write a new output rather than silently accepting or overwriting it.
