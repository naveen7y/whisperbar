#!/usr/bin/env bash
# Build WhisperBar.app and install it to /Applications.
# Produces a menu-bar app with its own Microphone + Accessibility identity.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: virtualenv missing. Run ./setup.sh first." >&2
  exit 1
fi

PY=".venv/bin/python"

echo "==> Ensuring py2app is installed"
"$PY" -m pip install --upgrade py2app -q

echo "==> Cleaning previous build"
rm -rf build dist

echo "==> Building WhisperBar.app (alias mode)"
"$PY" setup_app.py py2app -A

APP="dist/WhisperBar.app"
if [ ! -d "$APP" ]; then
  echo "ERROR: build failed — $APP not found." >&2
  exit 1
fi

echo "==> Installing to /Applications"
rm -rf "/Applications/WhisperBar.app"
cp -R "$APP" "/Applications/WhisperBar.app"

# Clear any stale quarantine/signature cache so macOS treats it fresh.
xattr -cr "/Applications/WhisperBar.app" 2>/dev/null || true

cat <<'EOF'

==> Done. WhisperBar.app is in /Applications.

IMPORTANT — because this is an alias-mode build, the app links back to
this source folder and its .venv. Don't move or delete either.

Next:
  1. Launch it:  open -a WhisperBar   (or find "WhisperBar" in Spotlight)
     The 🎙️ icon appears in the menu bar (no Dock icon — that's intended).
  2. Grant permissions when asked, both under System Settings ▸ Privacy & Security:
       • Microphone     → enable "WhisperBar"
       • Accessibility  → add/enable "WhisperBar"  (needed to paste text)
  3. Auto-start at login: System Settings ▸ General ▸ Login Items ▸
     add WhisperBar. (If you previously ran ./install-service.sh, run
     ./uninstall-service.sh first so you don't launch two copies.)

After granting Accessibility, quit (menu bar ▸ Quit) and relaunch once.
EOF
