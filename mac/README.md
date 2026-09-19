# VoiceTyper Mac

Menu bar app for voice typing on macOS.

Speak, stop recording, and the transcript is pasted at the current cursor position.

## App Bundle Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv ../venv
source ../venv/bin/activate
```

2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt pyinstaller
```

3. Run setup (installs dependencies and stores API key in Keychain):

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

4. Build the app bundle:

```bash
bash build-app.sh
```

5. Install the app bundle to `/Applications`:

```bash
bash install-app.sh
```

If `/Applications` requires elevated permissions, re-run with `sudo`.

6. Optional: install launch-at-login agent:

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
2. Press the configured hotkey to start recording, or click
   **Start Recording** in the menu bar menu (mouse-only, no keyboard needed).
3. Press the hotkey again, or click **Stop Recording**, to stop.
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

If Control–Space stops responding while the menu bar app remains open, check
this log before restarting. `pynput` 1.8.1 had a macOS media-key bug: pressing
volume or play/pause could terminate the keyboard listener with
`GlobalHotKeys._on_press() missing ... 'injected'`. VoiceTyper now requires
`pynput>=1.8.2`, which fixes that callback.

The app also checks listener health every two seconds and creates a new listener
if its thread exits. The timer remains active after startup and after permission
changes. The status menu shows `Hotkey reconnecting…` while the listener is
unavailable, or `Hotkey permission required` when Accessibility is not granted.

If the app disappears from the menu bar right after you grant Accessibility (a
`VoiceTyper-*.ips` crash report with `dispatch_assert_queue_fail` under
`TSMGetInputSourceProperty`), that is macOS 26 requiring keyboard-layout lookups
on the main queue while `pynput` performs them on its listener thread. `main.py`
loads the layout on the main thread and hands `pynput` a cached copy, so the
listener thread never calls into Text Input Services.

Because the bundle is ad-hoc signed, every rebuild invalidates the previous
Accessibility and Input Monitoring grants. Remove and re-add VoiceTyper.app in
both lists after each install.

After updating dependencies or source code, rebuild and reinstall the app bundle;
updating the virtual environment alone does not update the installed app.

Run the Mac regression suite from the repository root:

```bash
PYTHONPATH=mac venv/bin/python -m unittest discover -s mac/tests -v
```

On macOS this includes a real `pynput` backend test for media-key events followed
by Control–Space, without posting keyboard events or recording audio.
