#!/usr/bin/env bash
set -euo pipefail

if command -v glab >/dev/null 2>&1; then
  echo "glab 已安装: $(command -v glab)"
  glab --version | head -n 1
  exit 0
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "缺少 brew，无法通过 Homebrew 安装 glab。" >&2
  echo "请先安装 Homebrew，或参考 GitLab CLI 官方文档手动安装 glab。" >&2
  exit 1
fi

api_domain="${HOMEBREW_API_DOMAIN:-https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles/api}"
bottle_domain="${HOMEBREW_BOTTLE_DOMAIN:-https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles}"

echo "准备安装 glab。"
echo "本次将临时使用以下 Homebrew 镜像配置："
echo "  HOMEBREW_API_DOMAIN=$api_domain"
echo "  HOMEBREW_BOTTLE_DOMAIN=$bottle_domain"

env \
  HOMEBREW_API_DOMAIN="$api_domain" \
  HOMEBREW_BOTTLE_DOMAIN="$bottle_domain" \
  brew install glab

echo
echo "glab 安装完成。"
echo "下一步请执行："
echo "  glab auth login"
echo "如果是自建 GitLab，也可以执行："
echo "  glab auth login --hostname gitlab.codemao.cn"
