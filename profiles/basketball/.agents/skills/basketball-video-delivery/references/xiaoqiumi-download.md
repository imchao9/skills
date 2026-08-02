# Xiaoqiumi replay acquisition

## Preferred public path

The H5 competition and match pages expose basketball data through `https://api.xiaoqiumi.co/api`.
Resolve a match ID with `Basketball/Match/MatchInfo`, then read every `Basketball/Match/MatchDetail` tab.
The `集锦` tab contains the replay and labeled event media needed by the editing workflow.

Use the companion `$xiaoqiumi-match-review` fetcher when available so the raw responses and normalized event table share one source of truth.
Enumerate every replay candidate after checking title, duration, author, creation time, resolution, and thumbnail.
Treat near-identical long recordings from the same author created within five minutes as duplicate variants and retain the longer one.
Retain distinct long recordings and same-author short continuation segments in chronological order.
Treat short official highlights and entries whose `subName` is `个人集锦` as event media, not as the full replay.

## Authenticated fallback

When the public response lacks a playable URL or returns an access error, open the supplied `MatchVideoList` page with an existing authenticated browser profile.
Capture the successful `Basketball/Match/MatchVideoList?matchID=<id>` response and apply the same all-candidate selection contract to `video_type=1` items.
If the management page redirects to `#/SignIn`, ask the user to log in manually.
Keep cookies and authorization headers in memory only.

## Download procedure

1. Resolve and save sanitized match metadata without URL query parameters.
2. Write `replay-selection.json` with every candidate, selected segment, and exclusion decision.
3. Pass each selected segment's current URL through stdin or an environment variable to the bundled downloader.
4. Stream each segment to a `.part` file and rename atomically after HTTP completion.
5. Assemble multiple segments chronologically. Stream-copy matching formats; normalize only incompatible formats.
6. Download labeled events with their original titles, replacing only characters invalid on the local filesystem.
7. Record expected and completed event counts.
8. Verify every segment and the assembled replay duration, streams, resolution, content length, and a decoded sample.

For normal deliveries, let `fast_start_delivery.py` execute steps 1-7 and consume its sanitized report instead of waiting for AI between commands.

```bash
export XQM_DOWNLOAD_URL='<current in-memory file_url>'
python3 "$SKILL_DIR/scripts/xiaoqiumi_download.py" \
  --output 'source/<title>.mp4' \
  --report 'output/delivery/xiaoqiumi-download.json'
unset XQM_DOWNLOAD_URL
```

Prefer `--url-stdin` when another process can pipe the URL directly.
Reports retain only scheme, host, and path; query parameters are removed.

The phase is complete only when the match report exists, replay validation succeeds, downloaded event count matches the report, and no active `.part` remains.

### Download health and bounded recovery

The standard fast path uses eight deterministic byte ranges and writes an
atomic health heartbeat beside each segment report every 10 seconds. The
heartbeat records bytes, percentage, rolling throughput, ETA, last progress,
attempt number, and whether resumable chunks are retained. Signed query
parameters are never written.

After a 120-second startup grace period, the downloader treats any of these as
unhealthy:

- no byte progress for 90 seconds;
- rolling five-minute throughput below 1 MiB/s;
- predicted remaining time above one hour after ten minutes of observation.

An unhealthy or interrupted transfer is stopped and resumed with the same URL,
remote-object contract, range layout, and chunk files. The default budget is
three attempts total (the initial attempt plus two automatic resumes). A resume
is allowed only while the sanitized path, byte size, ETag, and connection count
match `source/<segment>.mp4.chunks/manifest.json`.

After the retry budget is exhausted, both the segment report and the parent
workflow report use `status: needs_attention`, preserve all valid chunks, and
record the reason, progress, speed, ETA, failed attempts, report paths, and
exact resume command. This is a recoverable waiting state, not successful
completion. Inspect the network/CDN or refresh an expired URL before resuming.
Never auto-shutdown the machine while this state is active.

## Failure handling

- Public response has no media: inspect all `MatchDetail` tabs before using the authenticated fallback.
- Redirect to SignIn on the fallback: user login required.
- Expired file URL or 403: refresh the list and reacquire `file_url`; do not retry the stale URL forever.
- Multiple replays: never silently choose only the longest item. Distinguish duplicate long variants, chronological recording segments, pre-game tests, and official highlights; retain an explicit selection manifest.
- Browser blob download fails on a large file: use the authenticated request URL with a streaming downloader while retaining required browser authorization in memory only.
- Interrupted transfer: retain `.part`; resume only if the server supports byte ranges, otherwise restart that file.
- Repeated stall, sustained low speed, or excessive ETA: let the bounded retry budget finish, then inspect the `*-health.json` and parent `needs_attention` report. Do not leave a trickling transfer running indefinitely.
- Remote size, ETag, URL path, or range layout changed: do not combine retained chunks with the new object. Inspect the source, then explicitly quarantine or remove stale chunks before starting a fresh download.
