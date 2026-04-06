#!/bin/bash
# Remove VoiceTyper launch agent
set -e

PLIST_DST="$HOME/Library/LaunchAgents/com.voicetyper.plist"

if [ -f "$PLIST_DST" ]; then
    launchctl bootout gui/$(id -u) "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "✅ VoiceTyper launch agent removed."
    echo "   It will no longer start on login."
else
    echo "ℹ️  VoiceTyper launch agent not found. Nothing to remove."
fi
