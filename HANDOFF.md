# HANDOFF

## Last completed work (2026-09-19, afternoon)
- Reboot did not bring the menu bar icon back (Control Center has no window for it at all), so the fallback was built: a **floating 🎙️ Record / 🔴 Stop button** (`mac/record_panel.py`, non-activating `NSPanel`), wired into `main.py` with a **Floating Record Button** menu toggle persisted as `AppSettings.show_record_button`. Chosen over a Dock icon because a Dock icon would activate the app and break the ⌘V paste into the user's editor.
- Smoke-tested the real panel under an AppKit run loop (visible, click reaches the callback, busy state disables the button). 95 unit tests pass. Rebuilt, installed to /Applications, running under launchd; macOS reports the panel window on screen.

## Current state
- Floating button visible bottom-right; menu bar icon still absent (OS bug). Hotkey waiting for Accessibility/Input Monitoring re-grant after the rebuild.
- User confirmed the floating button works end to end. Committed.

## Next steps
- Possible polish if wanted: remember/pick a specific display for the default position (currently `NSScreen.mainScreen()`, which landed on the left-hand display), a keyboard-free way to reach the menu while the icon is missing (e.g. right-click on the button opens the same menu).
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- Does the user want the button on a specific screen / corner by default?
