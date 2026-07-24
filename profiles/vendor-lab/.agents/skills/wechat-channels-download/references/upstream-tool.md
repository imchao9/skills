# Upstream tool reference

## Source and licensing

- Canonical source: <https://github.com/ltaoo/wx_channels_download>
- Documentation: <https://ltaoo.github.io/wx_channels_download/>
- Releases: <https://github.com/ltaoo/wx_channels_download/releases>
- Audited on: 2026-07-24
- Audited main commit: `3551436de39ae32dec86e4d064977a6684e429e3`
- Audited release: `v260714`

The upstream `LICENSE` applies MIT terms with the Commons Clause restriction: the software may not be sold, or used as the substantial value of a paid product/service, without a separate license. Re-check the live license before redistribution or commercial use.

This local skill is an orchestration wrapper. It does not include or redistribute upstream source, binaries, certificates, private keys, images, or documentation.

## Upstream behavior

The executable starts:

- an HTTP API, normally `127.0.0.1:2022`;
- an interception proxy, normally `127.0.0.1:2023`;
- optional system-proxy or TUN integration;
- response modification that injects download controls into WeChat PC pages.

The first privileged run may install a root certificate. Installing a root certificate changes the system trust chain and allows interception of matching HTTPS traffic. Treat it as a high-impact local change.

The repository supports macOS, Windows, and Linux release assets. Linux normally requires TUN mode and administrator privileges. Windows offers `safe` release assets without UPX compression.

## Conservative configuration

Start from the upstream-generated configuration, then verify:

```yaml
download:
  remoteServer:
    enabled: false

api:
  hostname: "127.0.0.1"
  port: 2022

proxy:
  hostname: "127.0.0.1"
  port: 2023
  tun: false

mp:
  enabled: false

cloudflare:
  accountId: ""
  apiToken: ""
  adminToken: ""
  sphCookie: ""
```

`proxy.system` may need to be `true` for the default interactive path, but changing it requires explicit approval and a restore check. With an existing proxy manager, use only an explicitly reviewed split-routing setup; routing all `qq.com` traffic through an unreviewed proxy chain is too broad.

Do not enable remote listeners, remote download, Cloudflare deployment, account/RSS sync, TUN, debug logging, or arbitrary injected scripts as part of a normal video download.

## Supported paths

### Interactive WeChat path

Use the upstream application and injected controls. Playback must initialize before the page exposes enough information for the download.

### Direct CLI path

```bash
wx_video_download download \
  --url "<video-url>" \
  --filename "<filename>.mp4" \
  --key "<numeric-key-if-needed>"
```

The tool downloads to a temporary file and decrypts when a key is provided. Treat URLs and decrypt keys as sensitive transient values.

### Cross-platform share-link path

The local `scripts/download_share_video.py` wrapper supports macOS, Windows, and Linux with Python 3.10+ only. It sends the user-approved share URL to the upstream public parser, keeps the returned signed URL in process memory, restricts media requests to HTTPS WeChat video CDN hosts, and atomically writes a verified MP4. It does not require the upstream binary or its interception certificate.

### Local API

The upstream OpenAPI definition is rooted at `http://127.0.0.1:2022`. Channels endpoints require an active WeChat Channels page/socket. Review the live OpenAPI documents before constructing requests; do not invent request bodies.

## Security observations

- The upstream tree contains built-in certificate material used by its interception implementation. Do not copy that material into this skill or expose it as reusable credentials.
- The current source can write `app.log`; logs may contain request/task metadata and must not be committed or included in debug artifacts.
- The current root command contains an integration path that can print a filtered Yuanbao cookie. Keep that integration disabled and never publish raw console/log output.
- Share links, signed media URLs, cookies, decrypt keys, downloaded videos, task metadata, and account lists can be private. Redact them from handoffs.

## Cleanup

- Stop foreground execution with `Ctrl+C`.
- Verify the original system proxy and VPN state after every run.
- Use `wx_video_download uninstall` only after the user approves removing the installed root certificate.
- If the process exits unexpectedly, inspect proxy state before reopening unrelated network applications.
