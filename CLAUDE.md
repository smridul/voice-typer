# VoiceTyper

Voice-to-text menu bar app. Press a hotkey (Control+Space) to record, press again to stop; audio goes to Groq for transcription and the result is pasted at the cursor. The menu bar menu also has a **Start Recording / Stop Recording** item, and a small floating **🎙️ Record / 🔴 Stop** button (`mac/record_panel.py`) toggles the same flow with the mouse.

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

- Floating record button (2026-09-19): fallback for the menu bar icon bug below. `record_panel.RecordButtonPanel` is a borderless `NSPanel` with `NSWindowStyleMaskNonactivatingPanel` at `NSFloatingWindowLevel`, joins all Spaces, frame autosaved as `VoiceTyperRecordButton`. Non-activating is essential: the app pastes via System Events ⌘V into the frontmost app, so any control that activates VoiceTyper (a Dock icon, a normal window) would make the transcript land nowhere. That is why the Dock-icon fallback was rejected. `set_state`/`show`/`hide` hop to the main thread with `AppHelper.callAfter` because `_stop_and_transcribe` runs on pynput's listener thread. Created in `_setup_record_button` (on `before_start`, like the status item), so `_record_panel` is `None` during `__init__` and `_update_record_button` must tolerate that. Visibility persisted as `AppSettings.show_record_button` (default True) and toggled by the **Floating Record Button** menu item. Tests fake `record_panel` in `load_main_module`. Borderless panels are not kept on screen by AppKit, and the user dragged it until only a 12px sliver was visible; `keep_panel_on_screen` (pure `clamp_origin`, tested in `tests/test_record_panel.py`) now clamps the frame on restore, on `show()`, and in the `windowDidMove:` delegate. To reposition from a shell: `defaults write com.voicetyper.app "NSWindow Frame VoiceTyperRecordButton" "X Y 168 52 0 0 SCREEN_W SCREEN_H "` then restart the app.
- macOS 26.6 (Darwin 25.6) menu bar icon bug (2026-09-19): Control Center stopped hosting *any newly created* third-party status item mid-session — VoiceTyper's, a bare AppKit probe (`autosaveName` + `visible=True`), and LogiPluginService's all get their window parked at y=-22 with `isOnActiveSpace=False`, while Amphetamine (running since before the break) stays visible. Matches public reports: steipete/CodexBar#3377, waydabber/BetterDisplay#5314. The app is fine (process alive, hotkey works, no crash reports) — only the icon is missing. Things verified NOT to help: System Settings > Menu Bar per-app toggle, `killall ControlCenter` (before or after launching the app), deleting `NSStatusItem Visible Item-N` keys in `com.apple.controlcenter`, launching via `open` vs. the raw binary. `main.py` now sets `autosaveName="VoiceTyper"` and `visible=True` in `_pin_status_item` (correct practice, avoids the transient `Item-N` identity) but that alone does not cure it. A full reboot did NOT fix it either (icon still absent, no Control Center window named `VoiceTyper` even parked off-screen). Do not spend time re-investigating; if it recurs, check `CGWindowListCopyWindowInfo` for a layer-25 Control Center window named `VoiceTyper` — absent = OS bug.
- Diagnostics that work from a shell: `osascript` UI scripting reports the status item's *in-process* position, which is meaningless when Control Center isn't hosting it; `screencapture` from the terminal may omit other apps' windows (no Screen Recording grant). Use `CGWindowListCopyWindowInfo` (layer 25, owner "Control Center") as the source of truth for what is actually in the menu bar.
- The app's `print` output is block-buffered when stdout goes to the log file; only lines with `flush=True` appear promptly. For live diagnosis run the binary with `PYTHONUNBUFFERED=1`.

## Current state (2026-09-19)
- Mac app built from main (keyboard-layout fix + Start/Stop Recording menu item + status item autosave name + floating record button), pynput 1.8.2, installed to /Applications, running under launchd. Needs Accessibility / Input Monitoring re-granted after each rebuild.
- Menu bar icon still invisible after a reboot (macOS 26.6 Control Center bug above). The floating record button is the working mouse control; hotkey works once permissions are re-granted.
