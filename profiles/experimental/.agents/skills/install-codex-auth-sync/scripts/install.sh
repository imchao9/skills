#!/usr/bin/env bash
set -euo pipefail
umask 077

base_url="${CODEX_AUTH_SYNC_BASE_URL:-https://43.138.216.106/codex-auth-sync}"
code_source="interactive"
code_file=""
preflight=false

usage() {
  printf '%s\n' 'usage: install.sh [--code-stdin | --code-file ABSOLUTE_PATH | --preflight]'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --code-stdin)
      [[ "$code_source" == "interactive" ]] || { usage >&2; exit 2; }
      code_source="stdin"; shift
      ;;
    --code-file)
      [[ "$code_source" == "interactive" && $# -ge 2 ]] || { usage >&2; exit 2; }
      code_source="file"; code_file="$2"; shift 2
      ;;
    --preflight)
      preflight=true; shift
      ;;
    -h|--help)
      usage; exit 0
      ;;
    *)
      usage >&2; exit 2
      ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || { printf '%s\n' '仅支持 macOS。' >&2; exit 1; }
case "$(uname -m)" in
  arm64) arch="arm64" ;;
  x86_64) arch="amd64" ;;
  *) printf '不支持的 Mac 架构：%s\n' "$(uname -m)" >&2; exit 1 ;;
esac
[[ "$base_url" == https://* && "$base_url" != *$'\n'* ]] || { printf '%s\n' '同步服务器必须是有效的 HTTPS 地址。' >&2; exit 1; }

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/install-codex-auth-sync-skill.XXXXXX")"
[[ "$work_dir" == "${TMPDIR:-/tmp}"/install-codex-auth-sync-skill.* && -d "$work_dir" ]] || { printf '%s\n' '无法创建安全的临时目录。' >&2; exit 1; }
installer="$work_dir/install-agent-v2.sh"
manifest="$work_dir/manifest.json"
code=""
cleanup() {
  code=''
  unset CODEX_AUTH_SYNC_CODE || true
  rm -rf "$work_dir"
}
trap cleanup EXIT

nonce="$(date +%s)"
curl --fail --silent --show-error --location --max-time 30 \
  "$base_url/install-agent-v2.sh?skill=1&nonce=$nonce" -o "$installer"
grep -Fq 'installer_version="2"' "$installer" || { printf '%s\n' '下载到的不是 v2 安装脚本。' >&2; exit 1; }
grep -Fq 'x86_64) arch="amd64"' "$installer" || { printf '%s\n' '安装脚本缺少 Intel 支持。' >&2; exit 1; }
grep -Fq 'platform=macos-agent&arch=$arch' "$installer" || { printf '%s\n' '安装脚本的架构下载契约无效。' >&2; exit 1; }

curl --fail --silent --show-error --location --max-time 30 \
  "$base_url/v1/app-update?platform=macos-agent&arch=$arch" -o "$manifest"
version="$(plutil -extract version raw -o - "$manifest")"
manifest_arch="$(plutil -extract arch raw -o - "$manifest")"
[[ "$manifest_arch" == "$arch" ]] || { printf '%s\n' '服务器返回了错误架构的 Agent。' >&2; exit 1; }
printf '预检通过：macOS %s，Agent v%s。\n' "$arch" "$version"

if [[ "$preflight" == "true" ]]; then
  exit 0
fi

case "$code_source" in
  stdin)
    IFS= read -r code
    ;;
  file)
    [[ "$code_file" == /* && -f "$code_file" && ! -L "$code_file" ]] || { printf '%s\n' '注册码文件必须是绝对路径下的普通文件。' >&2; exit 1; }
    mode="$(stat -f '%Lp' "$code_file")"
    (( (8#$mode & 077) == 0 )) || { printf '注册码文件权限必须为 0600，当前为 %s。\n' "$mode" >&2; exit 1; }
    IFS= read -r code < "$code_file"
    [[ "$(wc -l < "$code_file" | tr -d ' ')" -le 1 ]] || { printf '%s\n' '注册码文件只能包含一行。' >&2; exit 1; }
    ;;
  interactive)
    CODEX_AUTH_SYNC_BASE_URL="$base_url" bash "$installer"
    code=''
    ;;
esac

if [[ "$code_source" != "interactive" ]]; then
  [[ "$code" =~ ^[a-f0-9]{32}$ ]] || { printf '%s\n' '需要有效的 32 位一次性注册码。' >&2; exit 1; }
  CODEX_AUTH_SYNC_BASE_URL="$base_url" CODEX_AUTH_SYNC_CODE="$code" bash "$installer"
  code=''
  unset CODEX_AUTH_SYNC_CODE || true
fi

app_root="$HOME/Library/Application Support/Codex Auth Sync"
binary="$app_root/bin/codex-auth-sync"
device_file="$app_root/device.json"
[[ -x "$binary" && -f "$device_file" && ! -L "$device_file" ]] || { printf '%s\n' '安装未生成完整的设备注册文件。' >&2; exit 1; }
device_mode="$(stat -f '%Lp' "$device_file")"
[[ "$device_mode" == "600" ]] || { printf '设备凭证权限异常：%s。\n' "$device_mode" >&2; exit 1; }

"$binary" status --mode cliproxy --root "$app_root"
printf '%s\n' '设备已注册。下一步：请管理员在网页后台批准该设备。'
