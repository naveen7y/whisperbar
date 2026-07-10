#!/usr/bin/env bash
# Install WhisperBar as a login item that auto-starts and auto-restarts,
# using a macOS launchd LaunchAgent. Idempotent — safe to re-run.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.whisperbar.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/.whisperbar"

if [ ! -x "$DIR/.venv/bin/python" ]; then
  echo "ERROR: virtualenv missing. Run ./setup.sh first." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"

echo "==> Writing LaunchAgent to $PLIST"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$DIR/.venv/bin/python</string>
        <string>$DIR/whisperbar.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <!-- Restart only after an abnormal exit (a crash). A clean exit — i.e.
         the user choosing Quit from the menu — is respected, so Quit sticks
         instead of being immediately relaunched by launchd. -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ProcessType</key>
    <string>Interactive</string>
    <!-- WhisperBar writes its own rotating log to $LOGDIR/whisperbar.log, so
         send launchd's stdout/stderr to /dev/null to avoid double-writing and
         fighting the app's log rotation. -->
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>
</dict>
</plist>
EOF

UID_NUM="$(id -u)"

echo "==> Loading service"
# Modern launchctl (macOS 10.11+); fall back to legacy load if needed.
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || true
if launchctl bootstrap "gui/$UID_NUM" "$PLIST" 2>/dev/null; then
    launchctl enable "gui/$UID_NUM/$LABEL" 2>/dev/null || true
    launchctl kickstart -k "gui/$UID_NUM/$LABEL" 2>/dev/null || true
else
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
fi

echo
echo "==> Installed. WhisperBar will now start at login and restart if it crashes."
echo "    Logs:      $LOGDIR/whisperbar.log"
echo "    Status:    launchctl print gui/$UID_NUM/$LABEL | head"
echo "    Uninstall: ./uninstall-service.sh"
echo
echo "The 🎙️ icon should appear in your menu bar within a few seconds"
echo "(⏳ while the model loads on first run). If macOS prompts for"
echo "Microphone or Accessibility permission, grant both."
