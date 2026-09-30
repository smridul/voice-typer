# HANDOFF

## Last completed work (2026-09-30)
- User asked for 📋 Paste (⌘V) and ⏎ Enter buttons next to Record on the floating panel: for when they switch windows before the transcript pastes, and to submit after clicking Stop. Implemented (TDD, 138 tests pass), AppKit smoke-tested, rebuilt, installed, running under launchd. User confirmed both buttons work; committed.

- Follow-ups the same day: the paste button uses the macOS `doc.on.clipboard` icon (the 📋 emoji read as a trash can); committed 6f147f7. Then: clicking Enter while recording now stops, pastes, then presses Return (one click for short messages). 144 tests pass; rebuilt and installed; user-confirmed working; committed.

## Earlier (2026-09-24)
- User reported that with the Bluetooth DJI mic, the first ~3-5 s of each recording were lost: 🔴 showed immediately, but audio only started once a "Mac mini Speakers" banner appeared.
- Root cause (measured with a probe script): the DJI over Bluetooth hands-free profile returns exact digital zeros for ~3.7 s after the stream opens.
- Fix: silence gate + "Connecting mic…" state until real audio arrives. The stream stays open after a recording for a configurable window, set with the **Keep Mic Ready** menu (Off / 1 / 3 / 10 / 30 min / Always, default 3 min, `mic_warm_seconds` in settings.json). Also fixed the language/mic setters dropping other settings. Added a warm-mic indicator (the user asked how to tell when the warm window ends): floating button 🟢 Record / 🎙️ Record, menu bar icon 🟢 / 🎙️, and status line "Ready (mic warm)". 126 tests pass. Rebuilt, installed, running under launchd.

- Follow-up: user reported 🟡 turned 🔴 immediately on a cold start, before the mic was really live. Measured: the Bluetooth link replays ~0.3 s of stale audio (with 30-sample zero runs) for ~3 s after the zeros. New `mic_warmup.LiveAudioDetector` waits for 3 consecutive blocks with no long zero runs; tested against two real captures (`mac/tests/fixtures/`). 133 tests pass; rebuilt and installed. User confirmed it works on a cold start; committed and pushed.

## Current state
- Paste/Enter buttons: installed 2026-09-30, user-confirmed working, committed. Accessibility / Input Monitoring may need re-granting after the rebuild.
- User confirmed on the Mac mini with the DJI that it works (2026-09-24). Committed to main.
- Menu bar icon shows on the Mac mini; it is only missing on the MacBook Pro (macOS 26 bug). There, the Keep Mic Ready menu is reachable by right-clicking the floating button.

## Next steps
- Self-heal stale PortAudio devices: on `sd.InputStream` failure in `_open_input_stream`, re-init PortAudio and retry once (write the failing test first).
- Consider signing the bundle with a stable self-signed certificate so TCC grants survive rebuilds.

## Open questions
- Is the always-on orange mic dot during the warm window acceptable, or should the default be shorter?
