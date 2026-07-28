#!/usr/bin/env bash
set -euo pipefail

force=false
confirmed=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) force=true ;;
    --yes) confirmed=true ;;
    -h|--help)
      printf '%s\n' 'usage: activate.sh [--force --yes]'
      exit 0
      ;;
    *) printf '%s\n' 'usage: activate.sh [--force --yes]' >&2; exit 2 ;;
  esac
  shift
done

if [[ "$force" != "$confirmed" ]]; then
  printf '%s\n' '强制同步必须同时提供 --force --yes。' >&2
  exit 2
fi

app_root="$HOME/Library/Application Support/Codex Auth Sync"
binary="$app_root/bin/codex-auth-sync"
[[ -x "$binary" ]] || { printf '%s\n' '尚未安装 Codex Auth Sync Agent。' >&2; exit 1; }

arguments=(sync --mode cliproxy --root "$app_root")
if [[ "$force" == "true" ]]; then
  arguments+=(--force)
fi
"$binary" "${arguments[@]}"
"$binary" status --mode cliproxy --root "$app_root"
