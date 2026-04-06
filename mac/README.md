# VoiceTyper Mac

Menu bar app for voice typing on macOS.

Speak, stop recording, and the transcript is pasted at the current cursor position.

## Local Setup

1. Copy `config.example.py` to `config.py`.
2. Put your local API key in `config.py`.
3. Install dependencies:

```bash
bash setup.sh
```

4. Start the app:

```bash
venv/bin/VoiceTyper
```

5. Optional: install it as a login item:

```bash
bash install-launch.sh
```

## Secrets

- Real local config:
  `config.py`
- Template:
  `config.example.py`
- `config.py` is gitignored and should not be committed.

## How It Works

1. The app sits in the menu bar.
2. Press the configured hotkey to start recording.
3. Press it again to stop.
4. Audio is sent to Groq for transcription.
5. The result is pasted at the current cursor.

## Permissions

Grant these when prompted by macOS:

- Accessibility
- Input Monitoring
- Microphone

## Files

- `main.py` — app entry point
- `config.py` — local secret config
- `config.example.py` — config template
- `requirements.txt` — Python dependencies
- `install-launch.sh` — install as login item
- `restart.sh` — restart helper
- `uninstall-launch.sh` — remove login item

## Logs

```bash
tail -f voicetyper.log
```
