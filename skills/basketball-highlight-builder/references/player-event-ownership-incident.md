# Player-event ownership incident

Read this reference when a user reports that a personal reel contains another
player's basket, when locator rows were manually shifted, or when reviewing a
workflow change that can affect event ownership.

## What failed in match 400391280

The delivered `李天驰-个人精彩集锦_数据标注版.mp4` opened with several baskets
that were not made by 李天驰. This was a batch-level attribution failure, not an
isolated bad cut.

The old locator had 149 event rows. Its dense monotonic alignment kept events
in chronological order but could force a thumbnail onto a visually poor source
frame. For the 李天驰 first-quarter `11:32` row, the raw best match was at
`1050.5s`; monotonic alignment moved it to `131.5s`, while Hamming distance
worsened from `196` to `1017`. The pipeline recorded the adjustment and still
reported `complete`. Under the current thresholds, 78 of the 149 old rows would
have been blocked.

The failure then propagated:

| Layer | False confidence | Missing proof |
| --- | --- | --- |
| Locator | Events remained monotonic | The selected frame still matched the event visually |
| Windowing | `source_seconds` existed | It was only a reference frame, not necessarily the action moment |
| Contact sheet | Early/middle/late samples looked playable | The scorer for every made basket was correct |
| Labels | Filename and overlay named a player | The player shown completing the action matched that label |
| Statistics | Aggregate event counts could reconcile | Each individual row belonged to the named player |
| Media QA | Files decoded and had expected resolution | Basketball semantics were correct |
| Cloud QA | Remote path and bytes matched | The uploaded content was factually correct |

The original short post-window also made review weaker: a thumbnail/reference
frame could be cut before the finish, and sparse contact sheets often sampled
the beginning of a segment rather than the action.

## Incident response

When one wrong-player event is reported, treat the whole player-event batch as
untrusted.

1. Freeze upload, overwrite, cleanup, and completion reporting. Preserve the
   accepted source, old outputs, reports, and remote inventory.
2. Establish the event universe from current normalized match JSON. Record the
   expected player/action counts before editing any timestamps.
3. Trace one reported event end to end: metadata, raw best source match,
   monotonic selection, source window, rendered clip, reel position, and remote
   file. Confirm the mechanism before changing the batch.
4. Re-locate every event. Use Xiaoqiumi official single-event clips as
   multi-frame references when thumbnail alignment is ambiguous. A period
   anchor constrains the search; it never overrides poor visual similarity.
5. Stop on every `event-location-audit.json` blocker. A manual timestamp edit
   must regenerate downstream fingerprints and evidence; editing only the CSV
   is not a repair.
6. Reconcile all five action counts for every official player. Exact aggregate
   equality catches missing, extra, and cross-player count errors, but does not
   replace per-event identity review.
7. Review every made basket at the action moment. Confirm scorer, team, period,
   and game clock. If one evidence still is ambiguous or misses the finish,
   inspect multiple frames or the short clip and leave `identity_approved`
   false until the action is visible.
8. Render into a new lineage-bound output directory. Fully decode every reel,
   verify reel count and labels, and run the standard package validator.
9. Only after local semantic approval, prepare an explicit Baidu overwrite
   plan. Execute overwrite only with user authorization, then read back every
   remote path and exact byte count.

For this incident, recovery completed only after all 149 events were
recalibrated, 25 players' five action categories matched official totals with
zero differences, all 17 李天驰 events were rebuilt, 25 personal reels and one
match reel fully decoded, and 26 overwritten cloud files were individually
read back.

## Required evidence

The player-event gate is complete only when all of these refer to the same
content lineage:

- `event-location-audit.json`: `status=complete`, zero blockers, thresholds and
  raw/aligned comparison retained.
- `event-stat-audit.json`: every official player/action comparison matches and
  there are no unknown players.
- `rendered-matches.csv`: contains source, event reference, final window, and
  data-label status for every rendered event.
- `action-evidence.json`: fingerprint matches the reviewed CSV; every scoring
  row has reviewable evidence.
- `ai-review.json`: both `identity_approved` and `clock_approved` are true only
  after the evidence above was inspected.
- `standard-delivery-manifest.json`: media and semantic gates are complete.
- Baidu sync report: remote paths and bytes are verified after, never before,
  semantic approval.

Chronology, aggregate statistics, decoding, labeling, and byte readback are
independent supporting checks. No single one proves event ownership.
