# HANDOFF

## Last completed work (2026-09-09)
- Pulled commit abd17f2 (fix: prevent macOS media keys from disabling voice hotkey) from the other laptop.
- Upgraded root `venv` to pynput 1.8.2, rebuilt and installed the app.
- After the user granted Accessibility, the app crashed with SIGTRAP: pynput's listener thread called Text Input Services (`TSMGetInputSourceProperty`) and macOS 26 asserted it must run on the main queue. Crash report: `~/Library/Logs/DiagnosticReports/VoiceTyper-2026-09-09-200127.ips`.
- Fixed in `mac/main.py`: `refresh_keyboard_layout_context()` loads the layout on the main thread before each listener start, and `install_cached_keycode_context()` patches `pynput.keyboard._darwin.keycode_context` to yield the cached value. Tests added in `mac/tests/test_hotkey_backend.py` and `mac/tests/test_app_settings.py` (77 tests pass).
- Rebuilt and reinstalled the app with the fix. README, CLAUDE.md, HANDOFF.md updated.

## Current state
- Fix is in the working tree, NOT committed. Files changed: mac/main.py, mac/README.md, mac/tests/test_hotkey_backend.py, mac/tests/test_app_settings.py; new: CLAUDE.md, HANDOFF.md.
- Installed app is waiting for the user to re-grant Accessibility and Input Monitoring (each rebuild invalidates the ad-hoc-signed grant).

## Next steps
- Confirm Control+Space works after re-granting, and that no new `VoiceTyper-*.ips` crash report appears.
- Commit the fix once confirmed.
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- None.
