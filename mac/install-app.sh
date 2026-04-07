#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_APP="$SCRIPT_DIR/dist/VoiceTyper.app"
TARGET_APP="/Applications/VoiceTyper.app"

if [ ! -d "$SOURCE_APP" ]; then
    echo "❌ Build output missing at $SOURCE_APP" >&2
    echo "Run: bash $SCRIPT_DIR/build-app.sh" >&2
    exit 1
fi

if [ -e "$TARGET_APP" ]; then
    if [ ! -w "$TARGET_APP" ] && [ ! -w "/Applications" ]; then
        echo "❌ Cannot replace $TARGET_APP (permission denied)." >&2
        echo "Re-run with sufficient privileges, for example: sudo bash $SCRIPT_DIR/install-app.sh" >&2
        exit 1
    fi
elif [ ! -w "/Applications" ]; then
    echo "❌ Cannot install to /Applications (permission denied)." >&2
    echo "Re-run with sufficient privileges, for example: sudo bash $SCRIPT_DIR/install-app.sh" >&2
    exit 1
fi

if [ -e "$TARGET_APP" ] || [ -L "$TARGET_APP" ]; then
    rm -rf "$TARGET_APP"
fi

ditto "$SOURCE_APP" "$TARGET_APP"

echo "✅ Installed VoiceTyper app bundle at $TARGET_APP"
