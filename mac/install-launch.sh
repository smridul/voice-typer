#!/bin/bash
# Install VoiceTyper as a macOS Launch Agent (starts on login)
set -e

PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.voicetyper.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.voicetyper.plist"

# Unload if already loaded
launchctl bootout gui/$(id -u) "$PLIST_DST" 2>/dev/null || true

# Copy plist to LaunchAgents
cp "$PLIST_SRC" "$PLIST_DST"

# Load and start immediately
launchctl bootstrap gui/$(id -u) "$PLIST_DST"

echo "✅ VoiceTyper installed as launch agent."
echo "   It will start automatically on login."
echo "   It's also running right now."
echo ""
echo "   Logs: tail -f $(dirname "$0")/voicetyper.log"
echo "   Uninstall: bash $(dirname "$0")/uninstall-launch.sh"
