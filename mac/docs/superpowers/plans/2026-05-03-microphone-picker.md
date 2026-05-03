# Microphone Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a microphone picker submenu to the VoiceTyper menu bar app and fix the underlying device-resolution bug so the app follows macOS Sound → Input by default.

**Architecture:** Rename `language_preferences` module + `LanguageSettings` dataclass to a generic `app_settings` / `AppSettings` and add an optional `input_device_name` field. In `main.py`, replace the buggy `_resolve_input_device()` fallback with a name-based lookup that returns `None` (live OS default) when no device is pinned. Add a "Microphone" rumps submenu listing `System Default` + discovered input devices, with checkmark state and a "Refresh devices" item.

**Tech Stack:** Python 3, `rumps` (menu bar), `sounddevice` (PortAudio bindings), `unittest`, `dataclasses`.

**Spec:** [`docs/superpowers/specs/2026-05-03-microphone-picker-design.md`](../specs/2026-05-03-microphone-picker-design.md)

**Working directory for all commands:** `/Users/mridulshrivastava/code/voice-typer/mac`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `mac/language_preferences.py` | DELETE (renamed) | — |
| `mac/app_settings.py` | CREATE (renamed from above) | Settings dataclass + load/save (now includes `input_device_name`) |
| `mac/main.py` | MODIFY | Import update, microphone submenu, fixed `_resolve_input_device`, settings construction sites |
| `mac/tests/test_language_preferences.py` | DELETE (renamed) | — |
| `mac/tests/test_app_settings.py` | CREATE (renamed from above) | Existing tests, updated for rename + new field tests |

---

## Task 1: Rename `language_preferences` → `app_settings` (pure rename, no behavior change)

**Files:**
- Rename: `mac/language_preferences.py` → `mac/app_settings.py`
- Rename: `mac/tests/test_language_preferences.py` → `mac/tests/test_app_settings.py`
- Modify: `mac/main.py:31-36` (import statement)

This is a mechanical rename. Class `LanguageSettings` → `AppSettings`. All other behavior unchanged. After this task all existing tests must still pass.

- [ ] **Step 1.1: Move the module file**

```bash
git mv mac/language_preferences.py mac/app_settings.py
git mv mac/tests/test_language_preferences.py mac/tests/test_app_settings.py
```

- [ ] **Step 1.2: Rename the class inside `mac/app_settings.py`**

In `mac/app_settings.py`, replace every `LanguageSettings` with `AppSettings`:

```python
@dataclass(frozen=True)
class AppSettings:
    context_language: str
    output_language: str


def _default_settings():
    return AppSettings(
        context_language=DEFAULT_CONTEXT_LANGUAGE,
        output_language=DEFAULT_OUTPUT_LANGUAGE,
    )


def load_settings(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return _default_settings()

    if not isinstance(payload, dict):
        return _default_settings()

    return AppSettings(
        context_language=_sanitize_language(
            payload.get("context_language"),
            DEFAULT_CONTEXT_LANGUAGE,
        ),
        output_language=_sanitize_language(
            payload.get("output_language"),
            DEFAULT_OUTPUT_LANGUAGE,
        ),
    )
```

- [ ] **Step 1.3: Update imports in `mac/main.py:31-36`**

Replace:
```python
from language_preferences import (
    LANGUAGE_LABELS,
    LanguageSettings,
    load_settings,
    save_settings,
)
```

With:
```python
from app_settings import (
    LANGUAGE_LABELS,
    AppSettings,
    load_settings,
    save_settings,
)
```

Then in `mac/main.py:249` and `mac/main.py:260`, replace both `LanguageSettings(` with `AppSettings(`. Use editor find/replace within the file.

- [ ] **Step 1.4: Update imports and references in `mac/tests/test_app_settings.py`**

Top-of-file imports (lines 10–17), replace:
```python
import language_preferences
from language_preferences import (
    DEFAULT_CONTEXT_LANGUAGE,
    DEFAULT_OUTPUT_LANGUAGE,
    LanguageSettings,
    load_settings,
    save_settings,
)
```

With:
```python
import app_settings
from app_settings import (
    DEFAULT_CONTEXT_LANGUAGE,
    DEFAULT_OUTPUT_LANGUAGE,
    AppSettings,
    load_settings,
    save_settings,
)
```

Then find/replace within the file:
- `LanguageSettings` → `AppSettings` (every occurrence)
- `language_preferences.tempfile` → `app_settings.tempfile` (line 365 region)
- `from language_preferences import LANGUAGE_LABELS` → `from app_settings import LANGUAGE_LABELS` (line 379)

The class name `LanguagePreferencesTests` (line 219) can stay — it's just a test class name and renaming it is churn without value.

- [ ] **Step 1.5: Run all tests to verify the rename is clean**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest discover tests -v
```

Expected: all existing tests pass. No new tests yet.

- [ ] **Step 1.6: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/app_settings.py mac/main.py mac/tests/test_app_settings.py
# Confirm the renames are picked up:
git status
git commit -m "refactor: rename language_preferences -> app_settings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Add `input_device_name` field to `AppSettings` (TDD)

**Files:**
- Modify: `mac/app_settings.py`
- Modify: `mac/tests/test_app_settings.py`

Add `input_device_name: Optional[str] = None`. `None` means System Default. Persist as `"input_device_name"` key in JSON. Missing or non-string field loads as `None`.

- [ ] **Step 2.1: Write the failing tests**

Append to `mac/tests/test_app_settings.py`, inside `LanguagePreferencesTests`:

```python
    def test_load_settings_returns_none_input_device_when_field_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({"context_language": "en", "output_language": "en"}),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertIsNone(settings.input_device_name)

    def test_load_settings_preserves_input_device_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "input_device_name": "External Microphone",
                }),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertEqual(settings.input_device_name, "External Microphone")

    def test_load_settings_returns_none_for_non_string_input_device(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "input_device_name": 42,
                }),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertIsNone(settings.input_device_name)

    def test_save_settings_round_trips_input_device_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            expected = AppSettings(
                context_language="en",
                output_language="en",
                input_device_name="External Microphone",
            )

            save_settings(settings_path, expected)
            actual = load_settings(settings_path)

        self.assertEqual(actual, expected)

    def test_save_settings_writes_null_input_device_when_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings = AppSettings(
                context_language="en",
                output_language="en",
                input_device_name=None,
            )

            save_settings(settings_path, settings)
            payload = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertIsNone(payload["input_device_name"])
```

- [ ] **Step 2.2: Run the new tests to verify they fail**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_load_settings_returns_none_input_device_when_field_missing -v
```

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'input_device_name'` or `AttributeError: 'AppSettings' object has no attribute 'input_device_name'`.

- [ ] **Step 2.3: Implement the field in `mac/app_settings.py`**

Add `Optional` to the typing import at the top:

```python
from typing import Optional
```

Update the dataclass:

```python
@dataclass(frozen=True)
class AppSettings:
    context_language: str
    output_language: str
    input_device_name: Optional[str] = None
```

Update `_default_settings`:

```python
def _default_settings():
    return AppSettings(
        context_language=DEFAULT_CONTEXT_LANGUAGE,
        output_language=DEFAULT_OUTPUT_LANGUAGE,
        input_device_name=None,
    )
```

Update `load_settings` — add input device parsing after the language fields:

```python
def load_settings(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return _default_settings()

    if not isinstance(payload, dict):
        return _default_settings()

    raw_device = payload.get("input_device_name")
    input_device_name = raw_device if isinstance(raw_device, str) else None

    return AppSettings(
        context_language=_sanitize_language(
            payload.get("context_language"),
            DEFAULT_CONTEXT_LANGUAGE,
        ),
        output_language=_sanitize_language(
            payload.get("output_language"),
            DEFAULT_OUTPUT_LANGUAGE,
        ),
        input_device_name=input_device_name,
    )
```

Update `save_settings` to write the new key:

```python
def save_settings(path, settings):
    payload = {
        "context_language": settings.context_language,
        "output_language": settings.output_language,
        "input_device_name": settings.input_device_name,
    }
    settings_path = Path(path)
    temp_path = None
    # ... rest unchanged
```

- [ ] **Step 2.4: Run all settings tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass, including the five new ones.

NOTE: `test_save_settings_writes_expected_payload` (line 325 originally) currently asserts the payload equals `{"context_language": "en", "output_language": "hi"}`. After this change the payload will also include `"input_device_name": null`. Update that test:

```python
    def test_save_settings_writes_expected_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings = AppSettings(context_language="en", output_language="hi")

            save_settings(settings_path, settings)
            payload = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload,
            {
                "context_language": "en",
                "output_language": "hi",
                "input_device_name": None,
            },
        )
```

Also update `test_set_context_language_persists_and_updates_menu_state` (around line 384) — its assertion on the saved JSON will need to add `"input_device_name": None`:

```python
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "context_language": "hi",
                    "output_language": "en",
                    "input_device_name": None,
                },
            )
```

Re-run tests:

```bash
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass.

- [ ] **Step 2.5: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/app_settings.py mac/tests/test_app_settings.py
git commit -m "feat: add input_device_name to AppSettings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Preserve `input_device_name` through language-change persistence

**Files:**
- Modify: `mac/main.py:244-264` (`_set_context_language`, `_set_output_language`)
- Modify: `mac/tests/test_app_settings.py`

The two existing setters construct a brand-new `AppSettings` from two fields, which would silently reset `input_device_name` to `None` every time the user changes a language. Pass the current value through.

- [ ] **Step 3.1: Write the failing test**

Add to `LanguagePreferencesTests` in `mac/tests/test_app_settings.py`:

```python
    def test_set_context_language_preserves_input_device_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()
            app.settings = AppSettings(
                context_language="en",
                output_language="en",
                input_device_name="External Microphone",
            )

            app._set_context_language(app._context_language_items["hi"])

            self.assertEqual(app.settings.input_device_name, "External Microphone")
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["input_device_name"], "External Microphone")

    def test_set_output_language_preserves_input_device_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()
            app.settings = AppSettings(
                context_language="en",
                output_language="en",
                input_device_name="External Microphone",
            )

            app._set_output_language(app._output_language_items["hi"])

            self.assertEqual(app.settings.input_device_name, "External Microphone")
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["input_device_name"], "External Microphone")
```

- [ ] **Step 3.2: Run the new tests to verify they fail**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_set_context_language_preserves_input_device_name -v
```

Expected: FAIL — `app.settings.input_device_name` will be `None` because the existing setter reconstructs the dataclass without that field.

- [ ] **Step 3.3: Update both setters in `mac/main.py`**

Replace `_set_context_language` (around line 244):

```python
    def _set_context_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.context_language:
            return

        updated_settings = AppSettings(
            context_language=language_code,
            output_language=self.settings.output_language,
            input_device_name=self.settings.input_device_name,
        )
        self._save_and_apply_settings(updated_settings)
```

Replace `_set_output_language` (around line 255):

```python
    def _set_output_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.output_language:
            return

        updated_settings = AppSettings(
            context_language=self.settings.context_language,
            output_language=language_code,
            input_device_name=self.settings.input_device_name,
        )
        self._save_and_apply_settings(updated_settings)
```

- [ ] **Step 3.4: Run all tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass.

- [ ] **Step 3.5: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/main.py mac/tests/test_app_settings.py
git commit -m "fix: preserve input_device_name across language changes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Fix `_resolve_input_device` to follow OS default (TDD)

**Files:**
- Modify: `mac/main.py:371-389` (`_resolve_input_device`)
- Modify: `mac/tests/test_app_settings.py`

The new contract:
- If `self.settings.input_device_name` is set, scan `sd.query_devices()` and return the index of the first device with that exact name and `max_input_channels > 0`. Else fall through.
- Otherwise return `None`. The caller already skips the `device=` kwarg when `None` (see `main.py:417-418`), so PortAudio queries CoreAudio for the live OS default.

This change breaks the existing `test_start_recording_uses_first_input_device_when_default_missing` test because it asserts the old buggy behavior. We replace it with the new correct behavior.

- [ ] **Step 4.1: Write failing tests**

In `mac/tests/test_app_settings.py`, **delete** `test_start_recording_uses_first_input_device_when_default_missing` (around line 220). It encodes the bug we're fixing.

Add the replacement tests inside `LanguagePreferencesTests`:

```python
    def test_start_recording_omits_device_when_no_input_device_name_saved(self):
        notifications = []
        stream_calls = []
        main = load_main_module(
            notifications,
            default_devices=(-1, -1),
            available_devices=[
                {"name": "Fake Speakers", "max_input_channels": 0},
                {"name": "Fake Mic", "max_input_channels": 1},
            ],
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(),
        )
        app = main.VoiceTyper()

        app._start_recording()

        self.assertTrue(app.recording)
        self.assertNotIn("device", stream_calls[0])

    def test_start_recording_uses_named_device_when_saved(self):
        notifications = []
        stream_calls = []
        main = load_main_module(
            notifications,
            default_devices=(-1, -1),
            available_devices=[
                {"name": "Fake Speakers", "max_input_channels": 0},
                {"name": "Fake Mic", "max_input_channels": 1},
                {"name": "External Microphone", "max_input_channels": 1},
            ],
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(),
        )
        app = main.VoiceTyper()
        app.settings = AppSettings(
            context_language="en",
            output_language="en",
            input_device_name="External Microphone",
        )

        app._start_recording()

        self.assertTrue(app.recording)
        self.assertEqual(stream_calls[0]["device"], 2)

    def test_start_recording_falls_back_when_named_device_missing(self):
        notifications = []
        stream_calls = []
        main = load_main_module(
            notifications,
            default_devices=(-1, -1),
            available_devices=[
                {"name": "Fake Mic", "max_input_channels": 1},
            ],
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(),
        )
        app = main.VoiceTyper()
        app.settings = AppSettings(
            context_language="en",
            output_language="en",
            input_device_name="No Such Device",
        )

        app._start_recording()

        self.assertTrue(app.recording)
        self.assertNotIn("device", stream_calls[0])

    def test_start_recording_falls_back_when_named_device_has_no_input(self):
        notifications = []
        stream_calls = []
        main = load_main_module(
            notifications,
            default_devices=(-1, -1),
            available_devices=[
                {"name": "External Microphone", "max_input_channels": 0},
            ],
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(),
        )
        app = main.VoiceTyper()
        app.settings = AppSettings(
            context_language="en",
            output_language="en",
            input_device_name="External Microphone",
        )

        app._start_recording()

        self.assertTrue(app.recording)
        self.assertNotIn("device", stream_calls[0])
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_start_recording_omits_device_when_no_input_device_name_saved -v
```

Expected: FAIL — current `_resolve_input_device` returns index 1, so `stream_calls[0]["device"]` is `1` and the `assertNotIn` check fails.

- [ ] **Step 4.3: Replace `_resolve_input_device` in `mac/main.py`**

Replace the entire method (lines 371–389):

```python
    def _resolve_input_device(self):
        device_name = self.settings.input_device_name
        if not device_name:
            return None

        for index, device in enumerate(sd.query_devices()):
            if hasattr(device, "get"):
                name = device.get("name", "")
                max_input_channels = device.get("max_input_channels", 0)
            else:
                name = getattr(device, "name", "")
                max_input_channels = getattr(device, "max_input_channels", 0)
            if name == device_name and max_input_channels > 0:
                return index

        print(
            f"⚠️ Saved input device '{device_name}' not available; "
            "falling back to system default."
        )
        return None
```

- [ ] **Step 4.4: Run all tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass. The four new tests cover: omit-when-none, use-when-named, fall-back-when-missing, fall-back-when-no-input.

- [ ] **Step 4.5: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/main.py mac/tests/test_app_settings.py
git commit -m "fix: resolve input device by name; default to OS default

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Build the "Microphone" submenu (skeleton, no callback yet)

**Files:**
- Modify: `mac/main.py` — add `_build_microphone_menu`, `_refresh_microphone_menu`, integrate into `__init__`
- Modify: `mac/tests/test_app_settings.py`

Build the submenu containing `System Default` + one item per discovered input device. Show the checkmark on the currently-selected item. No click handler wired yet — Task 6 adds it. Splitting these tasks lets us verify the menu structure independently.

- [ ] **Step 5.1: Write the failing test**

Add to `LanguagePreferencesTests`:

```python
    def test_microphone_menu_lists_system_default_and_input_devices(self):
        notifications = []
        main = load_main_module(
            notifications,
            available_devices=[
                {"name": "Fake Mic", "max_input_channels": 1},
                {"name": "Fake Speakers", "max_input_channels": 0},
                {"name": "External Microphone", "max_input_channels": 1},
            ],
        )
        app = main.VoiceTyper()

        self.assertIn("System Default", app._microphone_items)
        self.assertIn("Fake Mic", app._microphone_items)
        self.assertIn("External Microphone", app._microphone_items)
        self.assertNotIn("Fake Speakers", app._microphone_items)
        self.assertEqual(app._microphone_items["System Default"].state, 1)
        self.assertEqual(app._microphone_items["Fake Mic"].state, 0)
        self.assertEqual(app._microphone_items["External Microphone"].state, 0)

    def test_microphone_menu_marks_saved_device_as_selected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "input_device_name": "External Microphone",
                }),
                encoding="utf-8",
            )
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
                available_devices=[
                    {"name": "Fake Mic", "max_input_channels": 1},
                    {"name": "External Microphone", "max_input_channels": 1},
                ],
            )
            app = main.VoiceTyper()

        self.assertEqual(app._microphone_items["System Default"].state, 0)
        self.assertEqual(app._microphone_items["External Microphone"].state, 1)
```

- [ ] **Step 5.2: Run the failing tests**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_microphone_menu_lists_system_default_and_input_devices -v
```

Expected: FAIL — `app._microphone_items` does not exist.

- [ ] **Step 5.3: Add the constant and methods to `mac/main.py`**

Add a module-level constant near the other constants (around line 45):

```python
SYSTEM_DEFAULT_MIC_LABEL = "System Default"
```

Add an attribute initialization in `VoiceTyper.__init__` immediately before `self._context_language_items = {}` (around line 175):

```python
        self._microphone_items = {}
```

Add two methods on `VoiceTyper` next to `_build_language_menu` / `_refresh_language_menu` (around line 208):

```python
    def _build_microphone_menu(self):
        microphone_menu = rumps.MenuItem("Microphone")
        self._microphone_items = {}

        system_default_item = rumps.MenuItem(
            SYSTEM_DEFAULT_MIC_LABEL,
            callback=None,
        )
        system_default_item.device_name = None
        self._microphone_items[SYSTEM_DEFAULT_MIC_LABEL] = system_default_item
        microphone_menu[SYSTEM_DEFAULT_MIC_LABEL] = system_default_item

        for device in sd.query_devices():
            if hasattr(device, "get"):
                name = device.get("name", "")
                max_input_channels = device.get("max_input_channels", 0)
            else:
                name = getattr(device, "name", "")
                max_input_channels = getattr(device, "max_input_channels", 0)
            if not name or max_input_channels <= 0:
                continue
            if name in self._microphone_items:
                continue
            item = rumps.MenuItem(name, callback=None)
            item.device_name = name
            self._microphone_items[name] = item
            microphone_menu[name] = item

        return microphone_menu

    def _refresh_microphone_menu(self):
        selected = self.settings.input_device_name
        for label, item in self._microphone_items.items():
            if selected is None:
                item.state = int(label == SYSTEM_DEFAULT_MIC_LABEL)
            else:
                item.state = int(label == selected)
```

Wire the submenu into `self.menu` in `__init__` (line 177–182). Replace:

```python
        self.menu = [
            self._status_item,
            self._set_api_key_item,
            None,
            *self._build_language_menu(),
        ]
        self._refresh_language_menu()
```

With:

```python
        self.menu = [
            self._status_item,
            self._set_api_key_item,
            None,
            self._build_microphone_menu(),
            None,
            *self._build_language_menu(),
        ]
        self._refresh_microphone_menu()
        self._refresh_language_menu()
```

- [ ] **Step 5.4: Run the new tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass, including both new menu-structure tests.

- [ ] **Step 5.5: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/main.py mac/tests/test_app_settings.py
git commit -m "feat: add microphone submenu with current selection state

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Wire microphone selection callback (persist + update checkmarks)

**Files:**
- Modify: `mac/main.py` — `_build_microphone_menu` (attach callback), add `_set_microphone`
- Modify: `mac/tests/test_app_settings.py`

Clicking a device persists `input_device_name` (or `None` for `System Default`) and updates checkmarks. Same persistence path as language changes (`_save_and_apply_settings`).

- [ ] **Step 6.1: Write the failing tests**

Add to `LanguagePreferencesTests`:

```python
    def test_set_microphone_persists_named_device(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
                available_devices=[
                    {"name": "External Microphone", "max_input_channels": 1},
                ],
            )
            app = main.VoiceTyper()

            app._set_microphone(app._microphone_items["External Microphone"])

            self.assertEqual(app.settings.input_device_name, "External Microphone")
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["input_device_name"], "External Microphone")
            self.assertEqual(app._microphone_items["External Microphone"].state, 1)
            self.assertEqual(app._microphone_items["System Default"].state, 0)

    def test_set_microphone_system_default_clears_saved_device(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "input_device_name": "External Microphone",
                }),
                encoding="utf-8",
            )
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
                available_devices=[
                    {"name": "External Microphone", "max_input_channels": 1},
                ],
            )
            app = main.VoiceTyper()

            app._set_microphone(app._microphone_items["System Default"])

        self.assertIsNone(app.settings.input_device_name)
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIsNone(payload["input_device_name"])
        self.assertEqual(app._microphone_items["System Default"].state, 1)
        self.assertEqual(app._microphone_items["External Microphone"].state, 0)

    def test_set_microphone_no_op_when_already_selected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
                available_devices=[
                    {"name": "External Microphone", "max_input_channels": 1},
                ],
            )
            app = main.VoiceTyper()

            app._set_microphone(app._microphone_items["System Default"])

        self.assertFalse(settings_path.exists())
        self.assertEqual(app._microphone_items["System Default"].state, 1)

    def test_set_microphone_keeps_state_consistent_when_save_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
                available_devices=[
                    {"name": "External Microphone", "max_input_channels": 1},
                ],
            )
            app = main.VoiceTyper()
            original_settings = app.settings
            main.save_settings = lambda path, settings: (_ for _ in ()).throw(
                OSError("disk full")
            )

            app._set_microphone(app._microphone_items["External Microphone"])

            self.assertEqual(app.settings, original_settings)
            self.assertEqual(app._microphone_items["System Default"].state, 1)
            self.assertEqual(app._microphone_items["External Microphone"].state, 0)
            self.assertFalse(settings_path.exists())
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0][0], "VoiceTyper")
            self.assertEqual(notifications[0][1], "Error")
            self.assertIn("disk full", notifications[0][2])
```

- [ ] **Step 6.2: Run the failing tests**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_set_microphone_persists_named_device -v
```

Expected: FAIL — `_set_microphone` does not exist.

- [ ] **Step 6.3: Update `_save_and_apply_settings` and add `_set_microphone`**

The existing `_save_and_apply_settings` already calls `self._refresh_language_menu()` on both success and failure paths. Add a microphone menu refresh alongside. Replace the method (around line 231):

```python
    def _save_and_apply_settings(self, updated_settings):
        try:
            save_settings(self._settings_path, updated_settings)
        except OSError as error:
            self._refresh_language_menu()
            self._refresh_microphone_menu()
            print(f"❌ Failed to save settings: {error}")
            rumps.notification("VoiceTyper", "Error", str(error))
            return False

        self.settings = updated_settings
        self._refresh_language_menu()
        self._refresh_microphone_menu()
        return True
```

Add `_set_microphone` next to `_set_output_language` (around line 264):

```python
    def _set_microphone(self, sender):
        device_name = getattr(sender, "device_name", None)
        if device_name == self.settings.input_device_name:
            return

        updated_settings = AppSettings(
            context_language=self.settings.context_language,
            output_language=self.settings.output_language,
            input_device_name=device_name,
        )
        self._save_and_apply_settings(updated_settings)
```

Update `_build_microphone_menu` to attach the callback. Change both `rumps.MenuItem(... callback=None)` lines to `callback=self._set_microphone`:

```python
        system_default_item = rumps.MenuItem(
            SYSTEM_DEFAULT_MIC_LABEL,
            callback=self._set_microphone,
        )
```

```python
            item = rumps.MenuItem(name, callback=self._set_microphone)
```

- [ ] **Step 6.4: Run all tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass.

- [ ] **Step 6.5: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/main.py mac/tests/test_app_settings.py
git commit -m "feat: persist microphone selection from menu

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Add "Refresh devices" item to rebuild the device list

**Files:**
- Modify: `mac/main.py` — extend `_build_microphone_menu`, add `_refresh_microphone_devices`
- Modify: `mac/tests/test_app_settings.py`

Append a `Refresh devices` item at the bottom of the submenu. Clicking it re-queries `sd.query_devices()` and rebuilds the submenu's children in place. Implementation strategy: keep a reference to the submenu `MenuItem`, clear its children, and repopulate.

`rumps.MenuItem` exposes its children dict via `__setitem__` (used in `_build_microphone_menu`) and supports clearing through assignment of an empty `MenuItem`. The simplest portable approach: hold a reference to the submenu, and on refresh delete each non-Refresh child and re-add discovered devices. We do this by re-querying and updating `_microphone_items` plus the submenu's children dict directly (`rumps.MenuItem.clear()` exists).

- [ ] **Step 7.1: Write the failing test**

Add to `LanguagePreferencesTests`:

```python
    def test_refresh_devices_updates_microphone_menu_in_place(self):
        notifications = []
        device_list = [
            {"name": "Fake Mic", "max_input_channels": 1},
        ]
        main = load_main_module(
            notifications,
            available_devices=device_list,
        )
        app = main.VoiceTyper()
        self.assertIn("Fake Mic", app._microphone_items)
        self.assertNotIn("New Headset", app._microphone_items)

        device_list.append({"name": "New Headset", "max_input_channels": 1})
        app._refresh_microphone_devices(app._microphone_items["System Default"])

        self.assertIn("New Headset", app._microphone_items)
        self.assertIn("Fake Mic", app._microphone_items)
        self.assertIn("System Default", app._microphone_items)

    def test_refresh_devices_drops_unplugged_devices(self):
        notifications = []
        device_list = [
            {"name": "Fake Mic", "max_input_channels": 1},
            {"name": "Removable Headset", "max_input_channels": 1},
        ]
        main = load_main_module(
            notifications,
            available_devices=device_list,
        )
        app = main.VoiceTyper()
        self.assertIn("Removable Headset", app._microphone_items)

        device_list.pop()
        app._refresh_microphone_devices(app._microphone_items["System Default"])

        self.assertNotIn("Removable Headset", app._microphone_items)
        self.assertIn("Fake Mic", app._microphone_items)
```

- [ ] **Step 7.2: Run the failing tests**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings.LanguagePreferencesTests.test_refresh_devices_updates_microphone_menu_in_place -v
```

Expected: FAIL — `_refresh_microphone_devices` does not exist.

- [ ] **Step 7.3: Add a constant and refactor `_build_microphone_menu` to keep a reference**

Add another constant near `SYSTEM_DEFAULT_MIC_LABEL`:

```python
REFRESH_MIC_DEVICES_LABEL = "Refresh devices"
```

In `__init__`, add:

```python
        self._microphone_menu = None
```

(place this immediately above `self._microphone_items = {}`).

Replace `_build_microphone_menu` so it stores the submenu reference and appends the Refresh item:

```python
    def _build_microphone_menu(self):
        microphone_menu = rumps.MenuItem("Microphone")
        self._microphone_menu = microphone_menu
        self._populate_microphone_devices()

        refresh_item = rumps.MenuItem(
            REFRESH_MIC_DEVICES_LABEL,
            callback=self._refresh_microphone_devices,
        )
        microphone_menu[REFRESH_MIC_DEVICES_LABEL] = refresh_item

        return microphone_menu

    def _populate_microphone_devices(self):
        microphone_menu = self._microphone_menu
        if microphone_menu is None:
            return

        # Drop existing device entries (and Refresh item if present)
        microphone_menu.clear()
        self._microphone_items = {}

        system_default_item = rumps.MenuItem(
            SYSTEM_DEFAULT_MIC_LABEL,
            callback=self._set_microphone,
        )
        system_default_item.device_name = None
        self._microphone_items[SYSTEM_DEFAULT_MIC_LABEL] = system_default_item
        microphone_menu[SYSTEM_DEFAULT_MIC_LABEL] = system_default_item

        for device in sd.query_devices():
            if hasattr(device, "get"):
                name = device.get("name", "")
                max_input_channels = device.get("max_input_channels", 0)
            else:
                name = getattr(device, "name", "")
                max_input_channels = getattr(device, "max_input_channels", 0)
            if not name or max_input_channels <= 0:
                continue
            if name in self._microphone_items:
                continue
            item = rumps.MenuItem(name, callback=self._set_microphone)
            item.device_name = name
            self._microphone_items[name] = item
            microphone_menu[name] = item

        self._refresh_microphone_menu()

    def _refresh_microphone_devices(self, _sender):
        self._populate_microphone_devices()
        # Re-add the Refresh item, since clear() removed it
        refresh_item = rumps.MenuItem(
            REFRESH_MIC_DEVICES_LABEL,
            callback=self._refresh_microphone_devices,
        )
        if self._microphone_menu is not None:
            self._microphone_menu[REFRESH_MIC_DEVICES_LABEL] = refresh_item
```

NOTE: `rumps.MenuItem.clear()` removes all children — verified against the rumps API. The `FakeMenuItem` in tests does not implement `clear`. Add it to `FakeMenuItem` in `mac/tests/test_app_settings.py`:

```python
class FakeMenuItem:
    def __init__(
        self,
        title,
        callback=None,
        key=None,
        icon=None,
        dimensions=None,
        template=None,
    ):
        self.title = str(title)
        self.callback = callback
        self.state = 0
        self.children = {}

    def __setitem__(self, key, value):
        self.children[str(key)] = value

    def __contains__(self, key):
        return str(key) in self.children

    def clear(self):
        self.children.clear()
```

- [ ] **Step 7.4: Run all tests to verify they pass**

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest tests.test_app_settings -v
```

Expected: all tests pass.

- [ ] **Step 7.5: Manual verification on the running app**

This step is hands-on and not automated. The agent should report back to the user that the automated suite passes and request a manual run-through covering:

1. Launch app, open menu → "Microphone" → confirm `System Default` is checked.
2. Plug in headphones with mic. Click `Refresh devices`. Confirm the headphones appear. Pick them. Checkmark moves.
3. Quit and relaunch. Checkmark is still on the headphones.
4. Close the lid (clamshell mode with external display). Trigger recording via hotkey. Confirm audio is captured.
5. Unplug headphones. Trigger recording. Confirm fallback to System Default works.
6. Switch back to `System Default`. Change macOS Sound → Input. Trigger recording. Confirm app follows the new OS default.

- [ ] **Step 7.6: Commit**

```bash
cd /Users/mridulshrivastava/code/voice-typer
git add mac/main.py mac/tests/test_app_settings.py
git commit -m "feat: add Refresh devices item to microphone submenu

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Verification Summary

After all tasks complete:

```bash
cd /Users/mridulshrivastava/code/voice-typer/mac
python -m unittest discover tests -v
```

Expected: all tests pass (existing + ~15 new).

Manual verification checklist is in Step 7.5.
