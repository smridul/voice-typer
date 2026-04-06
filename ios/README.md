# VoiceTyper iOS

iPhone app plus custom keyboard extension for recording speech in the app, transcribing it with Groq, and inserting the latest transcript from the keyboard.

## Local Setup

1. Copy `Config/LocalSecrets.example.xcconfig` to `Config/LocalSecrets.xcconfig`.
2. Put your Groq API key in:

```xcconfig
GROQ_API_KEY = your-key-here
```

3. Generate the Xcode project:

```bash
xcodegen generate
```

4. Open `VoiceTyper.xcodeproj` in Xcode.

## Secrets

- The real secret file is:
  `Config/LocalSecrets.xcconfig`
- That file is gitignored and should not be committed.
- The committed template is:
  `Config/LocalSecrets.example.xcconfig`

Both the app target and the keyboard extension read `GROQ_API_KEY` from that local xcconfig through their `Info.plist` values.

## How It Works

- Recording happens in the main `VoiceTyper` app.
- After transcription, the latest transcript is saved to the shared App Group and also copied to the clipboard.
- The custom keyboard shows a compact transcript bar plus typing keys.
- Tapping `Insert` in the keyboard inserts the latest saved transcript into the current text field.

## Notes

- iOS custom keyboards cannot access the microphone directly.
- If `VoiceTyper.xcodeproj` gets out of sync with `project.yml`, regenerate it with `xcodegen generate`.
