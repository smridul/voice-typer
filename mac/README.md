# VoiceTyper Mac

Menu bar app for voice typing on macOS.

Speak, stop recording, and the transcript is pasted at the current cursor position.

## App Bundle Setup

1. Run setup (installs dependencies and stores API key in Keychain):

```bash
bash setup.sh
```

You can run setup non-interactively by exporting `GROQ_API_KEY` first:

```bash
GROQ_API_KEY=gsk_... bash setup.sh
```

2. Build the app bundle:

```bash
bash build-app.sh
```

3. Install the app bundle to `/Applications`:

```bash
bash install-app.sh
```

If `/Applications` requires elevated permissions, re-run with `sudo`.

4. Optional: install launch-at-login agent:

```bash
bash install-launch.sh
```

## Storage

- API key is stored in macOS Keychain (`com.voicetyper.app` / `groq_api_key`).
- App settings are stored at:
  `~/Library/Application Support/VoiceTyper/settings.json`

## How It Works

1. The app sits in the menu bar.
2. Press the configured hotkey to start recording.
3. Press it again to stop.
4. Audio is sent to Groq for transcription.
5. The result is pasted at the current cursor.

## Permissions

Grant these permissions to `VoiceTyper.app` in macOS Privacy & Security:

- Accessibility
- Input Monitoring
- Microphone

## Files

- `main.py` — app entry point
- `setup.sh` — dependency install + Keychain API key setup
- `build-app.sh` — builds `dist/VoiceTyper.app`
- `install-app.sh` — installs app bundle into `/Applications`
- `install-launch.sh` — installs launch agent for login auto-start
- `requirements.txt` — Python dependencies
- `restart.sh` — restart helper
- `uninstall-launch.sh` — remove login item

## Logs

```bash
tail -f voicetyper.log
```
