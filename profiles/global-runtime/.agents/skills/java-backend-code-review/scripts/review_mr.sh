#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTOR="$SCRIPT_DIR/collect_review_context.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少 python3，请先安装并确保它在 PATH 中。" >&2
  exit 1
fi

if ! command -v glab >/dev/null 2>&1; then
  echo "缺少 glab。MR 模式需要先安装 GitLab CLI 并执行 \`glab auth login\`。" >&2
  echo "可先执行: bash \"$SCRIPT_DIR/install_glab.sh\"" >&2
  exit 1
fi

mr_input="${1:-}"
output_path="${2:-/tmp/review-context.json}"

if [[ -z "$mr_input" ]]; then
  read -r -p "请输入 MR 地址或 IID: " mr_input
fi

if [[ -z "$mr_input" ]]; then
  echo "MR 地址或 IID 不能为空。" >&2
  exit 1
fi

python3 "$COLLECTOR" --mr "$mr_input" --output "$output_path"
echo "审查上下文已生成: $output_path"
