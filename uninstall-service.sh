#!/usr/bin/env bash
# Remove the WhisperBar launchd service.
set -euo pipefail

LABEL="com.whisperbar.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_NUM="$(id -u)"

echo "==> Stopping and removing service"
launchctl bootout "gui/$UID_NUM/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "==> Removed. WhisperBar will no longer start at login."
echo "    (A currently-running instance keeps running until you Quit it from the menu bar.)"
