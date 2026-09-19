# HANDOFF

## Last completed work (2026-09-19)
- Added **Start Recording / Stop Recording** menu item (commit 90224aa). Verified end-to-end by the user (transcript pasted from a menu-driven recording).
- Investigated "app not showing in menu bar": root cause is a macOS 26.6 Control Center bug that stops hosting newly created third-party status items (details + everything ruled out are in CLAUDE.md > Decisions and gotchas). The app itself is healthy; Control+Space works once Input Monitoring is re-granted for the rebuilt bundle.
- `main.py`: status item now gets `autosaveName="VoiceTyper"` + `visible=True` via `_pin_status_item` (hooked on `rumps.events.before_start`). Test in `StatusItemVisibilityTests`. 85 tests pass. Rebuilt, installed, running under launchd.

## Current state
- Icon invisible on this machine until the OS-level state resets; hotkey works. Everything committed and pushed.

## Next steps
- User to log out / reboot and check whether the 🎙️ returns (cheapest untested remedy).
- If the icon stays unreliable on macOS 26.6, decide on a fallback so the user can (a) see the app is running and (b) record mouse-only: options are a Dock icon with a Dock menu (Start/Stop Recording), or a small floating record button window. Needs user's choice.
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- Which fallback the user prefers if the menu bar icon stays broken (Dock icon+menu vs floating button).
