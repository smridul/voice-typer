# VoiceTyper Mac

Speak and your words appear wherever your cursor is — in any app, any text field.

## How it works

1. App sits in your Mac menubar as 🎙️
2. Press **Ctrl+Space** to start recording → icon turns 🔴
3. Press **Ctrl+Space** again to stop → icon turns ⏳
4. Whisper transcribes your speech and it's automatically pasted at your cursor

## Setup

**1. Get a Groq API key**
Go to https://console.groq.com/keys and create a key.

**2. Run setup**
```bash
cd ~/code/voice-typer-mac
bash setup.sh
```

**3. Add your API key**
```bash
open config.py
# Replace the placeholder with your real Groq key
```

**4. Install as login item (starts automatically on login)**
```bash
bash install-launch.sh
```

**5. Grant macOS permissions when prompted**
- **Accessibility** — System Settings → Privacy & Security → Accessibility → enable `VoiceTyper`
- **Input Monitoring** — System Settings → Privacy & Security → Input Monitoring → enable `VoiceTyper`
- **Microphone** — macOS will prompt automatically

The `VoiceTyper` binary is at `venv/bin/VoiceTyper` — use Cmd+Shift+G in the file picker to navigate there.

## Scripts

| Script | What it does |
|--------|-------------|
| `setup.sh` | One-time install of Python dependencies |
| `install-launch.sh` | Install as macOS login item and start immediately |
| `uninstall-launch.sh` | Remove the login item |
| `restart.sh` | Quick restart |

## Changing the hotkey

Open `main.py` and edit this line near the top:
```python
HOTKEY = "<ctrl>+<space>"
```

Other examples:
- `"<cmd>+<shift>+v"` — Cmd+Shift+V
- `"<f5>"` — F5 key
- `"<ctrl>+r"` — Ctrl+R

## Files

| File | What it does |
|------|-------------|
| `main.py` | The whole app |
| `config.py` | Your API key (never commit this) |
| `config.example.py` | Template for config.py |
| `requirements.txt` | Python dependencies |
| `com.voicetyper.plist` | macOS launchd config |

## Logs

```bash
tail -f voicetyper.log
```
