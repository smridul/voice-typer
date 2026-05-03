# Microphone picker in menu bar

## Background

VoiceTyper currently uses `_resolve_input_device()` in `mac/main.py` to pick an audio input. The function falls through to a `sd.query_devices()` loop that returns the **first input-capable device** — almost always the built-in MacBook microphone — and pins the recording stream to that index. Result: the macOS Sound → Input selection is ignored, and recording dies in clamshell mode because the built-in mic is suspended when the lid is closed.

This spec adds a microphone picker to the menu bar app and fixes the underlying device-resolution bug as the same change.

## Goals

- Let the user pick the input device from the menu bar.
- Default behavior follows macOS Sound → Input live (the bug fix).
- Selection persists across app restarts.
- Recording in clamshell mode works when the user has selected (or the OS default is) an external mic.

## Non-goals (YAGNI)

- No "current input" indicator in the status line.
- No mid-recording device hot-swap. The device is resolved once when recording starts.
- No advanced disambiguation when two devices have identical names — first match wins.

## UI

A new submenu **"Microphone"** in the main rumps menu, placed between `Set API Key…` and the language submenus.

Items:
1. `System Default` — always present, first item.
2. One item per device returned by `sd.query_devices()` with `max_input_channels > 0`.

Behavior:
- The currently-selected item shows a checkmark (`MenuItem.state = 1`), matching the language menu pattern.
- Default for new users / fresh settings: `System Default`.
- The submenu is built once at app start. A `Refresh devices` item is appended at the bottom; clicking it rebuilds the device list in place. This keeps the implementation simple — no rumps event-hook research, no polling timer.
- Clicking a device persists the selection and updates the checkmark immediately. No notification banner on selection (matches the language menu).

## Persistence

Save the chosen device by **name** (string), not index. Indices shift when devices are added/removed; names are stable.

Schema change in `mac/language_preferences.py`:
- Rename the module file to `mac/app_settings.py` and the dataclass `LanguageSettings` → `AppSettings`. Update the single import site in `mac/main.py`.
- Add field `input_device_name: Optional[str] = None`. `None` ⇒ System Default.
- `load_settings` reads the field if present and returns `None` if missing or not a string. This is the migration: old settings files without the field load correctly with `input_device_name = None`.
- `save_settings` writes the field unconditionally (writing `null` when `None`).

The on-disk JSON gains one optional key:
```json
{
  "context_language": "en",
  "output_language": "en",
  "input_device_name": "External Microphone"
}
```

## Resolution at recording time

`_resolve_input_device()` in `main.py` becomes:

1. If `self.settings.input_device_name` is set:
   - Iterate `sd.query_devices()`. Return the index of the first device whose `name` equals the saved name **and** whose `max_input_channels > 0`.
   - If no match: log a warning (`print` to stderr, consistent with existing logging) and fall through to step 2. Do not show a notification — recording is in progress and the fallback is silent and reasonable.
2. Return `None`. The caller already handles `None` correctly (`main.py:417-418` skips the `device=` kwarg). PortAudio then queries CoreAudio for the live OS default at stream-creation time. **This is the bug fix.**

The existing `>= 0` index check on `sd.default.device` is removed — it was the buggy path that triggered the "first input device" fallback.

## Edge cases

- **Saved device is gone at recording time.** Silent fallback to System Default. Logged once per recording. No user-facing notification.
- **Two devices with identical names.** First match wins. Documented as a known limitation; rare in practice.
- **Device unplugged while submenu is open.** The next open rebuilds the list. Stale state for the duration of one open submenu is acceptable.
- **Selected device returns to system between app launches** (e.g. AirPods reconnect). Lookup by name will find it again — no user action required.

## Files touched

- `mac/main.py`
  - Add `_microphone_items: dict[str, rumps.MenuItem]` and `_system_default_item`.
  - Add `_build_microphone_menu()`, `_refresh_microphone_menu()`, `_set_microphone(sender)`.
  - Insert the submenu into `self.menu` in `__init__`.
  - Replace `_resolve_input_device()` with the new logic.
  - Update settings save/apply path to support the new field (extend `_save_and_apply_settings` or add a parallel path — single call site, keep it simple).
- `mac/language_preferences.py` → renamed to `mac/app_settings.py`
  - Rename `LanguageSettings` → `AppSettings`, add `input_device_name: Optional[str] = None`.
  - Update `load_settings` / `save_settings` for the new field.
- Module rename ripples: update `from language_preferences import …` to `from app_settings import …` in `main.py`. No other consumers found in the repo (verify during implementation).

## Tests

Unit tests in `mac/tests/`:
- `test_app_settings.py` (rename existing language settings tests if any, otherwise add):
  - `load_settings` returns `input_device_name=None` for legacy file (no field).
  - `load_settings` preserves `input_device_name` when present.
  - `load_settings` returns `None` when field is non-string (defensive).
  - `save_settings` round-trips the field.
- `test_resolve_input_device.py`:
  - Returns `None` when `input_device_name` is `None`.
  - Returns the matching index when `input_device_name` matches a device with input channels.
  - Returns `None` (with log) when `input_device_name` doesn't match any device.
  - Returns `None` when the matching device has `max_input_channels == 0` (defensive).

Mock `sd.query_devices()` in the resolver tests — no real audio hardware required.

## Verification

Manual on-device:
1. Launch app, open menu → "Microphone" → confirm `System Default` is checked.
2. Plug in headphones with mic. Open submenu → confirm headphones appear. Pick them. Checkmark moves.
3. Quit and relaunch. Checkmark is still on the headphones.
4. Close the lid (clamshell mode with external display). Trigger recording via hotkey. Confirm audio is captured.
5. Unplug headphones. Trigger recording. Confirm fallback to System Default works (no crash, recording succeeds).
6. Switch back to `System Default`. Change macOS Sound → Input. Trigger recording. Confirm app follows the new OS default.

Automated:
- `pytest mac/tests/` passes.
