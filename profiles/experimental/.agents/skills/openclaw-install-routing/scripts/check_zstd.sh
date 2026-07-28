#!/usr/bin/env bash
# Report decompression readiness without installing anything.
set -euo pipefail

if command -v zstd >/dev/null 2>&1; then
  printf 'zstd=present\n'
  zstd --version | head -1
  exit 0
fi

if [ "$#" -eq 1 ] && [ -f "$1" ] && tar -tf "$1" >/dev/null 2>&1; then
  printf 'zstd=provided-by-tar\n'
  exit 0
fi

printf 'zstd=missing\n' >&2
printf 'Install a checksummed bootstrap zstd tool or explicitly install zstd before extraction.\n' >&2
exit 3
