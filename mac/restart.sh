#!/bin/bash
# Restart VoiceTyper
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.voicetyper.plist 2>/dev/null
sleep 1
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.voicetyper.plist
echo "✅ VoiceTyper restarted."
