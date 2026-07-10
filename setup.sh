#!/usr/bin/env bash
# WhisperBar setup — creates a virtualenv and installs dependencies.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Creating virtual environment (.venv)"
"$PYTHON" -m venv .venv

echo "==> Upgrading pip"
./.venv/bin/python -m pip install --upgrade pip

echo "==> Installing requirements (this downloads faster-whisper + PyTorch-free CTranslate2 backend)"
./.venv/bin/python -m pip install -r requirements.txt

cat <<'EOF'

==> Done.

Run the app with:
    ./run.sh

First launch, macOS will ask for permissions. Grant ALL THREE
(System Settings ▸ Privacy & Security):
  • Microphone         — to record your voice (macOS usually prompts automatically)
  • Input Monitoring   — to DETECT the global hotkey (the #1 reason a hotkey seems dead)
  • Accessibility      — to PASTE the transcribed text into the focused app

Grant Input Monitoring and Accessibility to whatever app actually runs
WhisperBar — the terminal app (or Python) you launch it from with ./run.sh,
or "WhisperBar" itself if you build the standalone .app (see ./build-app.sh).
After granting, quit and relaunch WhisperBar so macOS picks up the change.
EOF
