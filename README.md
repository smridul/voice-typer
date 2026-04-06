# VoiceTyper

Voice typing apps for macOS and iOS.

This repo contains two separate platform implementations:

- [mac/README.md](mac/README.md) — macOS menu bar voice typer
- [ios/README.md](ios/README.md) — iPhone app plus custom keyboard extension

## Repo Layout

- `mac/` — Python/macOS menu bar app
- `ios/` — XcodeGen-based iPhone app and keyboard extension

## Secrets

Each platform keeps secrets local and out of git:

- mac:
  copy `mac/config.example.py` to `mac/config.py`
- ios:
  copy `ios/Config/LocalSecrets.example.xcconfig` to `ios/Config/LocalSecrets.xcconfig`

Both real secret files are gitignored and should not be committed.

## Platform Notes

- mac can record directly and paste text at the cursor.
- iOS custom keyboards cannot access the microphone directly, so recording happens in the main iPhone app and the keyboard inserts the latest saved transcript.

## Setup

See the platform-specific READMEs:

- [mac/README.md](mac/README.md)
- [ios/README.md](ios/README.md)
