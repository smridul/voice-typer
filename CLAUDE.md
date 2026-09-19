# VoiceTyper

Voice-to-text menu bar app. Press a hotkey (Control+Space) to record, press again to stop; audio goes to Groq for transcription and the result is pasted at the cursor. The menu bar menu also has a **Start Recording / Stop Recording** item that toggles the same flow with the mouse.

## Layout
- `mac/` — macOS menu bar app (Python: rumps, pynput, sounddevice, groq). See `mac/README.md` for full setup, permissions, and troubleshooting.
- `ios/` — iOS app (Swift, Xcode Cloud / TestFlight).
- `venv/` — root virtualenv used for building the Mac app (has PyInstaller). `mac/venv/` is a secondary dev venv without PyInstaller.

## Build and install (Mac)
Run from `mac/`:
```bash
PYTHON_BIN=/Users/mridulshrivastava/code/voice-typer/venv/bin/python bash build-app.sh
bash install-app.sh          # copies dist/VoiceTyper.app to /Applications
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.voicetyper.plist
launchctl kickstart -k gui/$(id -u)/com.voicetyper
```
Before installing, stop the running app: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.voicetyper.plist; pkill -x VoiceTyper`.

Tests (from repo root): `PYTHONPATH=mac venv/bin/python -m unittest discover -s mac/tests -v`

Logs: `~/Library/Logs/VoiceTyper.log`

## Decisions and gotchas
- The bundle is ad-hoc signed, so every rebuild is a "new" app to macOS. After reinstalling, remove and re-add VoiceTyper.app under Privacy & Security > Accessibility and Input Monitoring. Microphone and System Events automation may also need re-granting.
- pynput must be >=1.8.2. Version 1.8.1 crashes the hotkey listener thread when a media key (volume, play/pause) is pressed (`_on_press() missing 'injected'`), which left the menu bar app alive but Control+Space dead. Fixed in commit abd17f2 (2026-09-09), which also adds a 2-second health check that restarts the listener if its thread dies.
- Updating the venv alone does not update the installed app; always rebuild and reinstall.
- macOS 26 (Darwin 25) traps with SIGTRAP (`dispatch_assert_queue_fail` in `TSMGetInputSourceProperty`) if pynput's listener thread loads the keyboard layout while the input-source cache is stale, which happens right after a permission grant. `main.py` loads the layout on the main thread (`refresh_keyboard_layout_context`) and patches `pynput.keyboard._darwin.keycode_context` with a cached copy. Fixed 2026-09-09, uncommitted at time of writing.
- The launch agent runs the binary directly (not via `open`) because LaunchServices `open` was flaky.
- Start/Stop Recording menu item (2026-09-19): `_on_hotkey` and `_on_record_menu_item` both call `_toggle_recording()`. Only the hotkey path checks `_hotkey_enabled`, so the menu item works even when Accessibility/Input Monitoring hasn't been granted. The item title (`RECORD_START_LABEL` / `RECORD_STOP_LABEL`) is updated wherever the menu bar icon is updated (`_start_recording`, `_stop_and_transcribe`, `_reset_status`).

## Current state (2026-09-19)
- Mac app built from main (keyboard-layout fix c082419 + Start/Stop Recording menu item), pynput 1.8.2, installed to /Applications. Needs Accessibility / Input Monitoring re-granted after each rebuild.
