#!/usr/bin/env bash
# packages/ai-worker dizininden çalıştır: ./scripts/run-crawler.sh smoke
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$WORKER_DIR/../.." && pwd)"

cd "$WORKER_DIR"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
fi

python -m ingest.catalog_crawler "$@"
