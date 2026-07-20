# Xiaoqiumi replay acquisition

## Confirmed web flow

Basketball match video pages use:

```text
POST Basketball/Match/MatchVideoList?matchID=<id>
```

Each response item contains metadata such as `video_type`, `title`, `play_time`, and `file_url`.
The UI separates `集锦` (`video_type=0`) from `回放` (`video_type=1`).
For long files, its download link normalizes the URL scheme and appends:

```text
?download_name=<sanitized-title>.mp4
```

The endpoint and authentication scheme may change.
Re-inspect live network traffic instead of hardcoding an API host, authorization header, or signed URL.

## Authentication boundary

The management page redirects unauthenticated sessions to `#/SignIn`.
Prefer an existing authenticated browser profile.
If authentication is absent, pause and ask the user to log in manually.
Never print, persist, or copy cookies and authorization headers into project files.

## Download procedure

1. Open the supplied `MatchVideoList` page in an authenticated browser.
2. Capture XHR/fetch traffic before refreshing the video list.
3. Identify the successful `Basketball/Match/MatchVideoList` response for the requested match ID.
4. Select the longest `video_type=1` item as the full replay only after checking title and duration.
5. Pass the current URL through stdin or an environment variable to the bundled downloader; never place it in a report or shell history.
6. Confirm HTTP completion and content length.
7. Let the downloader rename `.part` to `.mp4` atomically.
8. Verify duration, streams, resolution, and decode a short sample.

```bash
export XQM_DOWNLOAD_URL='<current in-memory file_url>'
python3 "$SKILL_DIR/scripts/xiaoqiumi_download.py" \
  --output 'source/<title>.mp4' \
  --report 'output/delivery/xiaoqiumi-download.json'
unset XQM_DOWNLOAD_URL
```

Prefer `--url-stdin` when another process can pipe the URL directly.
Reports retain only scheme, host, and path; query parameters are removed.

For labeled clips, preserve the page title exactly except characters invalid on the local filesystem.

## Failure handling

- Redirect to SignIn: user login required.
- Expired file URL or 403: refresh the list and reacquire `file_url`; do not retry the stale URL forever.
- Multiple replays: choose by title, duration, and visible content rather than size alone.
- Browser blob download fails on a large file: use the authenticated request URL with a streaming downloader while retaining required browser authorization in memory only.
- Interrupted transfer: retain `.part`; resume only if the server supports byte ranges, otherwise restart that file.
