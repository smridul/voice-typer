# HANDOFF

## Last completed work (2026-09-21)
- User reported "recording is not working". The running instance had been launched outside launchd (stdout → /dev/null) so there were no logs; a restart fixed it. Most likely cause: stale PortAudio device table after the saved DJI mic was unplugged (see CLAUDE.md gotchas). Not fixed in code yet.
- Because the menu bar icon is still missing (macOS 26 bug), the user could not change the input source. Added a **right-click context menu on the floating record button** that shows the app's full menu (`RecordButtonPanel.set_context_menu`, wired in `_setup_record_button`). 101 unit tests pass; AppKit smoke test confirmed the popup opens without activating the app. Rebuilt, installed, running under launchd.

## Current state
- App installed and running under launchd with the right-click menu. Accessibility / Input Monitoring need re-granting after the rebuild (hotkey dead until then; floating button works regardless).
- Menu bar icon still absent (OS bug); floating button + right-click menu is the full replacement.

## Next steps
- Self-heal stale PortAudio devices: on `sd.InputStream` failure in `_start_recording`, re-init PortAudio and retry once (write the failing test first).
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- Confirm with the user whether the DJI mic was unplugged before recording broke (would confirm the stale-device hypothesis).
