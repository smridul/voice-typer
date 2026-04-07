#!/bin/bash
# VoiceTyper Mac — one-time setup script
set -euo pipefail

echo "🎙️  VoiceTyper Mac Setup"
echo "========================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install from https://python.org"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
python3 -m pip install -r requirements.txt

echo ""
if [ -n "${GROQ_API_KEY:-}" ]; then
    api_key="$GROQ_API_KEY"
    echo "🔐 Using GROQ_API_KEY from environment."
else
    read -r -s -p "🔐 Enter GROQ API key: " api_key
    echo ""
fi

if [ -z "$api_key" ]; then
    echo "❌ GROQ API key is required." >&2
    exit 1
fi

printf '%s' "$api_key" | python3 -c '
import sys
from keychain import save_api_key

secret = sys.stdin.read()
if not secret:
    raise SystemExit("Missing GROQ API key")
save_api_key(secret)
'

unset api_key
echo "✅ API key saved to macOS Keychain."

echo ""
echo "📋 First-time macOS permissions needed:"
echo "   • Microphone access — macOS will prompt automatically"
echo "   • Accessibility access — go to:"
echo "     System Settings → Privacy & Security → Accessibility"
echo "     and enable VoiceTyper.app"
