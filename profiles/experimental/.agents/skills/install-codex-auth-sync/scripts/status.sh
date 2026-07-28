#!/usr/bin/env bash
set -euo pipefail

app_root="$HOME/Library/Application Support/Codex Auth Sync"
binary="$app_root/bin/codex-auth-sync"

[[ "$(uname -s)" == "Darwin" ]] || { printf '%s\n' '仅支持 macOS。' >&2; exit 1; }
[[ -x "$binary" ]] || { printf '%s\n' '尚未安装 Codex Auth Sync Agent。' >&2; exit 1; }

"$binary" status --mode cliproxy --root "$app_root"

domain="gui/$(id -u)"
if launchctl print "$domain/com.cm.codex-auth-sync.agent" >/dev/null 2>&1; then
  printf '%s\n' 'launch_agent=loaded'
else
  printf '%s\n' 'launch_agent=not_loaded'
fi
