# VoiceTyper Mac

Menu bar app for voice typing on macOS.

Speak, stop recording, and the transcript is pasted at the current cursor position.

## App Bundle Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv ../venv
source ../venv/bin/activate
```

2. Run setup (installs dependencies and stores API key in Keychain):

```bash
bash setup.sh
```

You can also run setup non-interactively by setting `GROQ_API_KEY` in the environment first:

```bash
read -r -s -p "Enter GROQ API key: " GROQ_API_KEY; echo
export GROQ_API_KEY
bash setup.sh
unset GROQ_API_KEY
```

3. Build the app bundle:

```bash
bash build-app.sh
```

4. Install the app bundle to `/Applications`:

```bash
bash install-app.sh
```

If `/Applications` requires elevated permissions, re-run with `sudo`.

5. Optional: install launch-at-login agent:

```bash
bash install-launch.sh
```

The launch agent starts the installed executable directly:

```text
/Applications/VoiceTyper.app/Contents/MacOS/VoiceTyper
```

That avoids the flaky LaunchServices `open` path and is the recommended setup for a new Mac.

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
- Automation for `System Events`

## New Mac Checklist

On a new Mac, expect to do all of these once:

1. Run `bash setup.sh`
2. Build and install the app bundle
3. Open VoiceTyper and set a valid Groq API key
4. Allow Microphone access
5. Allow Accessibility and Input Monitoring
6. Allow Automation for `System Events` when macOS prompts for paste control

If transcription fails silently after recording, the most common causes are:

- invalid Groq API key
- missing `System Events` automation permission
- missing Accessibility or Input Monitoring permission

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
tail -f ~/Library/Logs/VoiceTyper.log
```
