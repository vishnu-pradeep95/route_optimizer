#!/usr/bin/env bash
# Build static Tailwind CSS for the driver PWA.
# Usage: bash scripts/build-pwa-css.sh
#
# Prerequisites:
#   tools/tailwindcss-extra binary (download with:
#   curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/download/tailwindcss-extra-linux-x64
#   mv tailwindcss-extra-linux-x64 tools/tailwindcss-extra && chmod +x tools/tailwindcss-extra)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CLI="$PROJECT_ROOT/tools/tailwindcss-extra"
PWA_DIR="$PROJECT_ROOT/apps/kerala_delivery/driver_app"

if [ ! -f "$CLI" ]; then
  echo "ERROR: tailwindcss-extra binary not found at $CLI"
  echo "Download it with:"
  echo "  curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/download/tailwindcss-extra-linux-x64"
  echo "  mv tailwindcss-extra-linux-x64 $CLI && chmod +x $CLI"
  exit 1
fi

echo "Compiling PWA CSS..."
"$CLI" \
  --input "$PWA_DIR/pwa-input.css" \
  --output "$PWA_DIR/tailwind.css" \
  --cwd "$PWA_DIR" \
  --minify

echo "Done: $PWA_DIR/tailwind.css ($(wc -c < "$PWA_DIR/tailwind.css") bytes)"
