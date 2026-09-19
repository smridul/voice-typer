# HANDOFF

## Last completed work (2026-09-19)
- Added a **Start Recording / Stop Recording** item to the menu bar menu (directly under the Status line) so recording can be toggled with the mouse instead of Control+Space. Shared toggle logic lives in `VoiceTyper._toggle_recording()` in `mac/main.py`; the menu path skips the hotkey-permission check so it works even before Accessibility/Input Monitoring is granted.
- 7 new tests in `mac/tests/test_app_settings.py` (`RecordMenuItemTests`); 84 tests pass.
- Rebuilt and installed the app to /Applications and relaunched via launchd; started cleanly, hotkey listener came up.

## Current state
- Working tree committed and pushed.
- Installed app has the new menu item. User still needs to click it once in a real text field to confirm the paste lands at the cursor (status-bar menus don't steal focus, so it should).

## Next steps
- Confirm the menu item works end-to-end for the user.
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- None.
