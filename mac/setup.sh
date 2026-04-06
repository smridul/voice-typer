#!/bin/bash
# VoiceTyper Mac — one-time setup script
set -e

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
pip3 install -r requirements.txt

# Check for config.py
if [ ! -f config.py ]; then
    echo ""
    echo "⚠️  No config.py found. Creating from template..."
    cp config.example.py config.py
    echo "👉 Open config.py and paste your OpenAI API key, then run:"
    echo "   python3 main.py"
else
    echo ""
    echo "✅ config.py found."
    echo ""
    echo "🚀 Ready! Run the app with:"
    echo "   python3 main.py"
fi

echo ""
echo "📋 First-time macOS permissions needed:"
echo "   • Microphone access — macOS will prompt automatically"
echo "   • Accessibility access — go to:"
echo "     System Settings → Privacy & Security → Accessibility"
echo "     and enable Terminal (or your Python runner)"
