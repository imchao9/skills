---
name: wechat-channels-download
description: 用于解析、下载并校验已获授权的微信视频号内容，支持 macOS、Windows 和 Linux。适用于下载视频号、保存分享链接、检查视频地址及排查 wx_video_download。经用户同意后，可能调用非微信官方第三方服务 https://sph.litao.workers.dev/ 获取临时视频地址，再从微信视频 CDN 下载；完整签名地址不落盘。
x-provenance: local-candidate
x-owner: cm
x-source-note: local safety wrapper around ltaoo/wx_channels_download; no upstream binary or certificate material is bundled
---

# WeChat Channels Download

Orchestrate the upstream `wx_video_download` tool without hiding its trust, proxy, credential, or copyright boundaries.
Do not bundle the upstream binary, certificate, private key, cookies, signed URLs, media, or logs in this skill.

## Choose the path

- **Interactive WeChat PC download**: use the local proxy/injected download button for a visible Channels video or author page.
- **Direct media URL**: use `wx_video_download download` only when the user already has an authorized media URL and optional decrypt key.
- **Local API**: use `http://127.0.0.1:2022` only when the downloader is already running and the relevant WeChat page/socket is active.
- **Share-link parsing**: prefer the local tool. Sending a share URL to the upstream public parser is an external disclosure and requires explicit user approval. After approval, run the bundled redacted probe:

  ```bash
  python3 "$SKILL_DIR/scripts/probe_public_parser.py" \
    "https://weixin.qq.com/sph/..." \
    --allow-external-parser \
    --check-url
  ```

  Treat `video_url_found` as evidence that an address was returned. The probe prints only its host, query-parameter names, URL fingerprint, and bounded reachability result; it never prints the full signed URL.
- **One-command share-link download**: after approval, prefer the standard-library script. It resolves the temporary URL in memory, streams the MP4 to a same-directory temporary file, validates it, and atomically publishes the destination without printing the signed URL.

  macOS or Linux:

  ```bash
  python3 "$SKILL_DIR/scripts/download_share_video.py" \
    "https://weixin.qq.com/sph/..." \
    --output "/absolute/path/video.mp4" \
    --allow-external-parser
  ```

  Windows PowerShell, from the skill directory:

  ```powershell
  py -3 .\scripts\download_share_video.py `
    "https://weixin.qq.com/sph/..." `
    --output "$env:USERPROFILE\Downloads\video.mp4" `
    --allow-external-parser
  ```

  Require Python 3.10 or newer. The script has no third-party Python dependencies and does not require the upstream binary, root certificate, system proxy, TUN, or administrator privileges. It refuses existing outputs unless `--overwrite` is explicit, enforces a 2 GiB default limit, rejects non-portable Windows filenames, checks the MP4 signature and SHA-256, and runs deeper validation when `ffprobe` is installed.
- **Batch download**: require an explicit author/account scope and output directory. Do not infer “download everything”.

Read [upstream-tool.md](references/upstream-tool.md) before installing, updating, configuring, troubleshooting, or using API/batch features.

## Safety gate

Before downloading:

1. Confirm the user owns the content or has permission to save it. Do not help bypass account access, paywalls, private visibility, DRM, or other access controls.
2. Inventory the current OS/architecture, existing downloader version, WeChat availability, output directory, free space, VPN/proxy state, and ports `2022`/`2023`.
3. Explain any requested state change:
   - root-certificate installation changes the system trust store;
   - `proxy.system: true` changes the system proxy;
   - TUN mode changes routes and may conflict with Clash, Surge, VPNs, or corporate networking;
   - sudo/admin execution is privileged.
4. Obtain explicit approval before any of those changes. Never type, capture, or persist the user's administrator password.
5. Keep API and proxy listeners on loopback. Do not enable remote download, Cloudflare, RSS/account sync, debug logging, or custom scripts unless the user explicitly requests that separate capability.

## Install or update

Use only the official GitHub releases for `ltaoo/wx_channels_download`.

1. Resolve the current release and the matching OS/architecture asset.
2. Download the asset and its published checksum file.
3. Verify the checksum before extracting or executing.
4. Inspect the extracted `config.yaml`; keep secrets empty and listeners bound to `127.0.0.1`.
5. On macOS/Linux, add executable permission if needed. Run with sudo only after the safety gate and only for the documented first-run certificate/proxy setup.
6. Do not use `curl | sh`, unofficial mirrors, or repository-embedded certificate/private-key files as standalone credentials.

If a compatible binary is already installed, prefer `wx_video_download version` and an in-place official update over reinstalling.

## Download workflow

### Interactive path

1. Record the original system proxy/VPN state.
2. Start the downloader in the foreground with loopback hostname and the intended config.
3. Wait for both the API and proxy success messages. Do not enable `--debug` by default.
4. Open WeChat PC, enter the authorized Channels video, wait for playback to initialize, then pause.
5. Use the injected button and select the requested quality. For author-page batch download, confirm the scope again before creating tasks.
6. Monitor the task list until the selected tasks finish. Do not claim success from task creation alone.
7. Stop the downloader with `Ctrl+C` and verify the original system proxy is restored.

### Direct URL path

Run only with an authorized URL:

```bash
wx_video_download download \
  --url "<signed-media-url>" \
  --filename "<safe-name>.mp4" \
  --key "<decrypt-key-if-required>"
```

Do not echo the real URL/key in chat, shell history, logs, reports, or committed files. Prefer passing sensitive values through a transient local mechanism appropriate to the user's shell.

## Verify the result

Run:

```bash
python3 "$SKILL_DIR/scripts/verify_download.py" "/absolute/path/to/video.mp4"
```

Treat the download as complete only when:

- the intended output exists and is non-empty;
- `ffprobe` reports a video stream and positive duration;
- the filename and selected quality match the request;
- a representative playback check succeeds;
- batch requests have the expected item count, with failures listed separately.

Do not expose the media, signed URL, cookies, decrypt key, or sensitive log contents in the handoff.

## Failure and cleanup

- Missing injected button: confirm the downloader is running, the intended proxy path is active, then refresh/reopen the video page.
- Network failure after launch: stop the downloader and restore the original system proxy before further diagnosis.
- VPN/TUN conflict: stop TUN; prefer an explicitly reviewed split-routing configuration.
- Port conflict: identify the owner of `127.0.0.1:2022` or `:2023`; do not kill unrelated processes without approval.
- Certificate removal: after explicit approval, use the upstream `wx_video_download uninstall` command and verify the trust-store entry is removed.

Report what was installed or changed, the source version/checksum, files downloaded, verification results, restored proxy state, and any residual certificate or routing changes.
