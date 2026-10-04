#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTOR="$SCRIPT_DIR/collect_review_context.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "缺少 python3，请先安装并确保它在 PATH 中。" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "缺少 git，请先安装并确保它在 PATH 中。" >&2
  exit 1
fi

resolve_ref() {
  local ref="$1"
  if git rev-parse --verify --quiet "$ref^{commit}" >/dev/null; then
    printf '%s\n' "$ref"
    return 0
  fi
  if git rev-parse --verify --quiet "origin/$ref^{commit}" >/dev/null; then
    printf 'origin/%s\n' "$ref"
    return 0
  fi
  return 1
}

current_branch="$(git branch --show-current 2>/dev/null || true)"
source_input="${1:-}"
target_input="${2:-}"
output_path="${3:-/tmp/review-context.json}"

if [[ -z "$source_input" ]]; then
  if [[ -n "$current_branch" ]]; then
    read -r -p "请输入源分支名称 [默认: $current_branch]: " source_input
    source_input="${source_input:-$current_branch}"
  else
    read -r -p "请输入源分支名称: " source_input
  fi
fi

if [[ -z "$target_input" ]]; then
  read -r -p "请输入目标分支名称 [默认: master]: " target_input
  target_input="${target_input:-master}"
fi

if [[ -z "$source_input" || -z "$target_input" ]]; then
  echo "源分支和目标分支都不能为空。" >&2
  exit 1
fi

if ! source_ref="$(resolve_ref "$source_input")"; then
  echo "找不到源分支: $source_input" >&2
  exit 1
fi

if ! target_ref="$(resolve_ref "$target_input")"; then
  echo "找不到目标分支: $target_input" >&2
  exit 1
fi

merge_base="$(git merge-base "$target_ref" "$source_ref")"
if [[ -z "$merge_base" ]]; then
  echo "无法计算 merge-base: $source_ref vs $target_ref" >&2
  exit 1
fi

python3 "$COLLECTOR" --base "$merge_base" --head "$source_ref" --output "$output_path"
echo "审查上下文已生成: $output_path"
echo "比较范围: $target_ref...$source_ref (merge-base: $merge_base)"
