#!/usr/bin/env bash
# Launch WhisperBar.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Virtualenv not found. Run ./setup.sh first." >&2
  exit 1
fi

exec ./.venv/bin/python whisperbar.py
