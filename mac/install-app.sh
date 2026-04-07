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

if [ -d "$TARGET_APP" ]; then
    rm -rf "$TARGET_APP"
fi

cp -R "$SOURCE_APP" "$TARGET_APP"

echo "✅ Installed VoiceTyper app bundle at $TARGET_APP"
