#!/bin/bash
# Install VoiceTyper as a macOS Launch Agent (starts on login)
set -euo pipefail

APP_BUNDLE="/Applications/VoiceTyper.app"
APP_BINARY="$APP_BUNDLE/Contents/MacOS/VoiceTyper"
# Test-only seam: allows overriding only the existence check path in automated tests.
APP_BINARY_CHECK="${VOICETYPER_APP_BINARY_CHECK:-$APP_BINARY}"
PLIST_DST="$HOME/Library/LaunchAgents/com.voicetyper.plist"
LOG_PATH="$HOME/Library/Logs/VoiceTyper.log"

if [ ! -x "$APP_BINARY_CHECK" ]; then
    echo "❌ Missing installed app executable at $APP_BINARY" >&2
    echo "Run: bash $(cd "$(dirname "$0")" && pwd)/install-app.sh" >&2
    exit 1
fi

mkdir -p "$(dirname "$PLIST_DST")"
mkdir -p "$(dirname "$LOG_PATH")"

cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicetyper</string>
    <key>ProgramArguments</key>
    <array>
        <string>$APP_BINARY</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$LOG_PATH</string>
    <key>StandardErrorPath</key>
    <string>$LOG_PATH</string>
</dict>
</plist>
EOF

# Unload if already loaded
launchctl bootout gui/$(id -u) "$PLIST_DST" 2>/dev/null || true

# Load and start immediately
launchctl bootstrap gui/$(id -u) "$PLIST_DST"
launchctl kickstart -k gui/$(id -u)/com.voicetyper

echo "✅ VoiceTyper installed as launch agent."
echo "   It will start automatically on login."
echo "   It's also running right now."
echo ""
echo "   Logs: tail -f $LOG_PATH"
echo "   Uninstall: bash $(cd "$(dirname "$0")" && pwd)/uninstall-launch.sh"
