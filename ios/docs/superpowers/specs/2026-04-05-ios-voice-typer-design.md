# VoiceTyper iOS — Design Spec

## Overview

An iOS app with a custom keyboard extension that records voice, transcribes it via Groq's Whisper API, and inserts the text at the cursor in any app. This is the iOS counterpart to the existing Mac menubar app.

## Architecture

**Approach:** SwiftUI app + Custom Keyboard Extension. The keyboard extension uses `UIInputViewController` with SwiftUI views embedded via `UIHostingController`.

**Targets:**
- **VoiceTyper** (main app) — minimal setup screen with instructions to enable the keyboard
- **VoiceTyperKeyboard** (keyboard extension) — the actual voice typing keyboard

## Project Structure

```
VoiceTyper/
├── VoiceTyper.xcodeproj
├── VoiceTyper/                        # Main app target
│   ├── VoiceTyperApp.swift            # App entry point
│   ├── SetupView.swift                # Instructions to enable keyboard
│   ├── Assets.xcassets
│   └── Info.plist
├── VoiceTyperKeyboard/                # Keyboard extension target
│   ├── KeyboardViewController.swift   # UIInputViewController
│   ├── KeyboardView.swift             # SwiftUI keyboard UI
│   ├── AudioRecorder.swift            # AVAudioEngine recording
│   ├── WhisperService.swift           # Groq API transcription
│   └── Info.plist
└── Shared/
    └── Config.swift                   # Hardcoded Groq API key (added to both targets)
```

## Main App

A single-screen SwiftUI app that displays setup instructions:

1. Open Settings > General > Keyboard > Keyboards > Add New Keyboard > select "VoiceTyper"
2. Tap VoiceTyper > enable "Allow Full Access" (required for microphone + network access)

No other functionality. The app exists because iOS requires a host app for keyboard extensions.

## Keyboard Extension

### UI States

**Idle:**
- Text preview area at top with placeholder ("Tap mic to start...")
- Large centered microphone button
- Globe button (bottom-left) for switching keyboards — required by iOS
- Return button (bottom-right)

**Recording:**
- Preview area shows "Listening..." with pulsing animation
- Mic button turns red with stop icon
- Visual recording indicator (pulsing dot or similar)

**Transcribing:**
- Preview area shows "Transcribing..."
- Mic button disabled

**Result:**
- Preview area shows transcribed text
- "Insert" button to commit text to the active text field
- Mic button available to re-record
- Clear button to reset

### Visual Style
- Native iOS system style
- Dark/light mode support using system colors
- Keyboard height matches standard iOS keyboard

## Audio Recording

- **Engine:** `AVAudioEngine` capturing at 16kHz mono (matches Mac version)
- **Format:** PCM Int16, single channel
- **Buffer:** In-memory, capped at ~2 minutes (~3.8MB) to stay within the ~50MB keyboard extension memory limit
- **Trigger:** Tap mic to start, tap again to stop (toggle)

## Transcription

- **API:** Groq Whisper — `POST https://api.groq.com/openai/v1/audio/transcriptions`
- **Model:** `whisper-large-v3`
- **Language:** `en`
- **Transport:** `URLSession` multipart form POST with WAV data
- **API Key:** Hardcoded in `Config.swift` (personal use only)
- Audio is converted from PCM buffer to WAV format in memory before sending

## Text Insertion

After the user reviews the transcribed text in the preview area and taps "Insert":
- `textDocumentProxy.insertText(text)` inserts at the current cursor position
- Preview resets to idle state

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Full Access not enabled | Show "Enable Full Access in Settings" in preview |
| Microphone denied | Show "Enable Full Access in Settings" in preview |
| Network failure | Show "No connection" in preview, user can retry |
| Empty transcription (silence) | Show "No speech detected" in preview |
| Extension terminated mid-recording | Audio lost, acceptable for ephemeral voice typing |

## Permissions

- `NSMicrophoneUsageDescription` in both Info.plist files
- Keyboard extension requires "Allow Full Access" for microphone and network access

## Out of Scope

- App Store distribution (hardcoded API key)
- Standalone voice-to-text in the main app
- Language selection (hardcoded to English)
- Recording history or persistence
- Hold-to-record gesture
