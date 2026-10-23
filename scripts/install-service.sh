#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
fluke_root="${1:?Usage: install-service.sh /absolute/Fluke/checkout}"
[[ -f "$fluke_root/scripts/fluke_preview.sh" ]] || { echo 'Fluke checkout missing' >&2; exit 1; }
MORTAL_FLUKE_ROOT="$fluke_root" docker compose -f "$repo_root/deploy/compose.yml" build
MORTAL_FLUKE_ROOT="$fluke_root" docker compose -f "$repo_root/deploy/compose.yml" up -d --wait
