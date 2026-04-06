# Language Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent `Context Language` and `Output Language` controls to the menubar app so it supports English and Hindi speech/output combinations, including Hindi speech -> romanized Hindi output.

**Architecture:** Keep `main.py` as the menubar entrypoint, but move the new logic into two focused helper modules: one for persistent language settings and one for transcript conversion. `main.py` will read the selected context/output settings, transcribe with the correct speech language, optionally convert the transcript to the requested output form, and then paste the final text.

**Tech Stack:** Python 3, `rumps`, `groq`, built-in `json`, built-in `pathlib`, built-in `unittest`

---

## File Structure

- Modify: `main.py`
  - Keep audio capture, menubar status, hotkey handling, and paste behavior.
  - Add menu groups for context/output language and wire them to the new helper modules.
- Create: `language_preferences.py`
  - Define supported language codes and labels.
  - Load/save persistent settings to a local JSON file.
- Create: `language_processing.py`
  - Contain the transcript conversion rules.
  - Build the exact prompt for translation/transliteration when output differs from context.
- Create: `tests/__init__.py`
  - Make the `tests` package importable for `unittest`.
- Create: `tests/test_language_preferences.py`
  - Cover default settings, round-trip persistence, and invalid-file fallback.
- Create: `tests/test_language_processing.py`
  - Cover same-language passthrough, English -> Hindi translation prompting, and Hindi -> English transliteration prompting.
- Modify: `README.md`
  - Document the new menu controls and what each language combination does.

## Task 1: Add Persistent Language Settings

**Files:**
- Create: `language_preferences.py`
- Create: `tests/__init__.py`
- Create: `tests/test_language_preferences.py`

- [ ] **Step 1: Write the failing settings tests**

Create `tests/__init__.py` with:

```python
# Test package marker for unittest discovery.
```

Create `tests/test_language_preferences.py` with:

```python
import json
import tempfile
import unittest
from pathlib import Path

from language_preferences import (
    DEFAULT_CONTEXT_LANGUAGE,
    DEFAULT_OUTPUT_LANGUAGE,
    LanguageSettings,
    load_settings,
    save_settings,
)


class LanguagePreferencesTests(unittest.TestCase):
    def test_load_settings_returns_defaults_when_file_missing(self):
        missing_path = Path(tempfile.gettempdir()) / "voicetyper-missing-settings.json"
        if missing_path.exists():
            missing_path.unlink()

        settings = load_settings(missing_path)

        self.assertEqual(
            settings,
            LanguageSettings(
                context_language=DEFAULT_CONTEXT_LANGUAGE,
                output_language=DEFAULT_OUTPUT_LANGUAGE,
            ),
        )

    def test_save_settings_round_trips_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            expected = LanguageSettings(context_language="hi", output_language="en")

            save_settings(settings_path, expected)
            actual = load_settings(settings_path)

        self.assertEqual(actual, expected)

    def test_load_settings_falls_back_to_defaults_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text("{not valid json", encoding="utf-8")

            settings = load_settings(settings_path)

        self.assertEqual(settings.context_language, DEFAULT_CONTEXT_LANGUAGE)
        self.assertEqual(settings.output_language, DEFAULT_OUTPUT_LANGUAGE)

    def test_save_settings_writes_expected_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings = LanguageSettings(context_language="en", output_language="hi")

            save_settings(settings_path, settings)
            payload = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload,
            {"context_language": "en", "output_language": "hi"},
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m unittest tests.test_language_preferences -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'language_preferences'`

- [ ] **Step 3: Write the minimal settings implementation**

Create `language_preferences.py` with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


DEFAULT_CONTEXT_LANGUAGE = "en"
DEFAULT_OUTPUT_LANGUAGE = "en"

LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
}

LANGUAGE_CODES_BY_LABEL = {
    "English": "en",
    "Hindi": "hi",
}


@dataclass(frozen=True)
class LanguageSettings:
    context_language: str = DEFAULT_CONTEXT_LANGUAGE
    output_language: str = DEFAULT_OUTPUT_LANGUAGE


def _sanitize_language(code: str | None, fallback: str) -> str:
    if code in LANGUAGE_LABELS:
        return code
    return fallback


def load_settings(path: Path) -> LanguageSettings:
    if not path.exists():
        return LanguageSettings()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return LanguageSettings()

    return LanguageSettings(
        context_language=_sanitize_language(
            payload.get("context_language"),
            DEFAULT_CONTEXT_LANGUAGE,
        ),
        output_language=_sanitize_language(
            payload.get("output_language"),
            DEFAULT_OUTPUT_LANGUAGE,
        ),
    )


def save_settings(path: Path, settings: LanguageSettings) -> None:
    path.write_text(
        json.dumps(asdict(settings), indent=2, sort_keys=True),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
python -m unittest tests.test_language_preferences -v
```

Expected: PASS with `OK`

- [ ] **Step 5: Commit**

```bash
git add language_preferences.py tests/__init__.py tests/test_language_preferences.py
git commit -m "feat: add persistent language settings"
```

## Task 2: Add Transcript Conversion Rules

**Files:**
- Create: `language_processing.py`
- Create: `tests/test_language_processing.py`

- [ ] **Step 1: Write the failing conversion tests**

Create `tests/test_language_processing.py` with:

```python
import unittest
from types import SimpleNamespace

from language_processing import convert_transcript


class FakeCompletions:
    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.response_text)
                )
            ]
        )


class FakeClient:
    def __init__(self, response_text):
        self.chat = SimpleNamespace(completions=FakeCompletions(response_text))


class LanguageProcessingTests(unittest.TestCase):
    def test_same_language_output_skips_model_call(self):
        client = FakeClient("unused")

        result = convert_transcript(
            client=client,
            transcript="I need to go tomorrow",
            context_language="en",
            output_language="en",
        )

        self.assertEqual(result, "I need to go tomorrow")
        self.assertEqual(client.chat.completions.calls, [])

    def test_english_to_hindi_uses_translation_prompt(self):
        client = FakeClient("मुझे कल जाना है")

        result = convert_transcript(
            client=client,
            transcript="I need to go tomorrow",
            context_language="en",
            output_language="hi",
        )

        self.assertEqual(result, "मुझे कल जाना है")
        self.assertEqual(len(client.chat.completions.calls), 1)
        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("Translate the text into natural Hindi written in Devanagari script.", messages[0]["content"])
        self.assertIn("I need to go tomorrow", messages[1]["content"])

    def test_hindi_to_english_uses_romanization_prompt(self):
        client = FakeClient("mujhe kal jana hai")

        result = convert_transcript(
            client=client,
            transcript="मुझे कल जाना है",
            context_language="hi",
            output_language="en",
        )

        self.assertEqual(result, "mujhe kal jana hai")
        self.assertEqual(len(client.chat.completions.calls), 1)
        messages = client.chat.completions.calls[0]["messages"]
        self.assertIn("Transliterate the Hindi text into natural Latin-script Hindi.", messages[0]["content"])
        self.assertIn("मुझे कल जाना है", messages[1]["content"])

    def test_empty_model_response_raises_value_error(self):
        client = FakeClient("   ")

        with self.assertRaises(ValueError):
            convert_transcript(
                client=client,
                transcript="मुझे कल जाना है",
                context_language="hi",
                output_language="en",
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
python -m unittest tests.test_language_processing -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'language_processing'`

- [ ] **Step 3: Write the minimal conversion implementation**

Create `language_processing.py` with:

```python
from __future__ import annotations


TEXT_MODEL = "llama-3.1-8b-instant"


def _conversion_messages(transcript: str, context_language: str, output_language: str):
    if context_language == "en" and output_language == "hi":
        instruction = (
            "Translate the text into natural Hindi written in Devanagari script. "
            "Return only the converted text with no quotes or commentary."
        )
    elif context_language == "hi" and output_language == "en":
        instruction = (
            "Transliterate the Hindi text into natural Latin-script Hindi. "
            "Do not translate it into English meaning. "
            "Return only the converted text with no quotes or commentary."
        )
    else:
        return None

    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": transcript},
    ]


def convert_transcript(client, transcript: str, context_language: str, output_language: str) -> str:
    cleaned = transcript.strip()
    if not cleaned:
        return ""

    messages = _conversion_messages(cleaned, context_language, output_language)
    if messages is None:
        return cleaned

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0,
        messages=messages,
    )
    converted = response.choices[0].message.content.strip()
    if not converted:
        raise ValueError("Conversion returned empty text.")

    return converted
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
python -m unittest tests.test_language_processing -v
```

Expected: PASS with `OK`

- [ ] **Step 5: Commit**

```bash
git add language_processing.py tests/test_language_processing.py
git commit -m "feat: add transcript conversion rules"
```

## Task 3: Wire Language Menus and Processing into the App

**Files:**
- Modify: `main.py`
- Modify: `tests/test_language_preferences.py`

- [ ] **Step 1: Extend the tests with a failing app-path assertion**

Append this test to `tests/test_language_preferences.py`:

```python
    def test_supported_language_labels_are_stable(self):
        from language_preferences import LANGUAGE_LABELS

        self.assertEqual(
            LANGUAGE_LABELS,
            {"en": "English", "hi": "Hindi"},
        )
```

Run:

```bash
python -m unittest tests.test_language_preferences -v
```

Expected: PASS with `OK`

This step confirms the menu code can rely on the exported labels before wiring them into `main.py`.

- [ ] **Step 2: Replace the hard-coded app setup with language-aware menu state**

Update the import block at the top of `main.py` to:

```python
import threading
import tempfile
import wave
import time
import os
from pathlib import Path

import rumps
import sounddevice as sd
import numpy as np
import pyperclip
import pyautogui
from pynput import keyboard
from groq import Groq

from language_preferences import LANGUAGE_LABELS, LanguageSettings, load_settings, save_settings
from language_processing import convert_transcript
```

Add these constants below `HOTKEY`:

```python
SETTINGS_PATH = Path(__file__).with_name("settings.json")
TRANSCRIPTION_LANGUAGE_CODES = {
    "en": "en",
    "hi": "hi",
}
```

Replace the current `__init__` and add the menu helpers below it:

```python
class VoiceTyper(rumps.App):
    def __init__(self):
        super().__init__("VoiceTyper", icon=None, quit_button="Quit")
        self.title = "🎙️"
        self._status_item = rumps.MenuItem("Status: Ready")

        self.client = Groq(api_key=GROQ_API_KEY)
        self.recording = False
        self.frames = []
        self._stream = None
        self.settings = load_settings(SETTINGS_PATH)

        self._context_menu = rumps.MenuItem("Context Language")
        self._output_menu = rumps.MenuItem("Output Language")
        self._context_items = {}
        self._output_items = {}
        self._build_language_menu()
        self._refresh_language_menu()

        self.menu = [
            self._status_item,
            None,
            self._context_menu,
            self._output_menu,
            None,
        ]

        self._hotkey_listener = keyboard.GlobalHotKeys({
            HOTKEY: self._on_hotkey
        })
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

        print(f"✅ VoiceTyper running. Hold {HOTKEY} to record.")

    def _build_language_menu(self):
        for code, label in LANGUAGE_LABELS.items():
            context_item = rumps.MenuItem(label, callback=self._set_context_language)
            output_item = rumps.MenuItem(label, callback=self._set_output_language)
            self._context_items[code] = context_item
            self._output_items[code] = output_item
            self._context_menu.add(context_item)
            self._output_menu.add(output_item)

    def _refresh_language_menu(self):
        for code, item in self._context_items.items():
            item.state = 1 if self.settings.context_language == code else 0

        for code, item in self._output_items.items():
            item.state = 1 if self.settings.output_language == code else 0

    def _set_context_language(self, sender):
        selected_code = next(
            code for code, label in LANGUAGE_LABELS.items() if label == sender.title
        )
        self.settings = LanguageSettings(
            context_language=selected_code,
            output_language=self.settings.output_language,
        )
        save_settings(SETTINGS_PATH, self.settings)
        self._refresh_language_menu()

    def _set_output_language(self, sender):
        selected_code = next(
            code for code, label in LANGUAGE_LABELS.items() if label == sender.title
        )
        self.settings = LanguageSettings(
            context_language=self.settings.context_language,
            output_language=selected_code,
        )
        save_settings(SETTINGS_PATH, self.settings)
        self._refresh_language_menu()
```

- [ ] **Step 3: Replace the transcription block with the language-aware pipeline**

Replace the body of `_stop_and_transcribe` from the `# Send to Whisper` comment through the `if text:` branch with:

```python
        # Send to Whisper
        try:
            with open(tmp.name, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f,
                    language=TRANSCRIPTION_LANGUAGE_CODES[self.settings.context_language],
                )

            transcript = result.text.strip()
            final_text = convert_transcript(
                client=self.client,
                transcript=transcript,
                context_language=self.settings.context_language,
                output_language=self.settings.output_language,
            )
            if final_text:
                self._type_text(final_text)
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            rumps.notification("VoiceTyper", "Error", str(e))
        finally:
            os.unlink(tmp.name)
            self._reset_status()
```

- [ ] **Step 4: Run the unit tests to verify nothing regressed**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: PASS with `OK`

- [ ] **Step 5: Manual smoke-test the menubar integration**

Run:

```bash
python main.py
```

Expected:
- menubar shows `Context Language` and `Output Language`
- each group shows one checked item
- changing a selection writes `settings.json`
- restarting the app preserves the checked items

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_language_preferences.py
git commit -m "feat: add language menus to voice typer"
```

## Task 4: Document the Feature and Validate the Four Modes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the user-facing language-mode docs**

Update `README.md` by adding this section after `How it works`:

```md
## Language Modes

Use the menubar to choose:

- `Context Language` — the language you are speaking
- `Output Language` — the form you want typed

Supported combinations:

- English context -> English output: normal English text
- English context -> Hindi output: Hindi script
- Hindi context -> English output: romanized Hindi in English letters
- Hindi context -> Hindi output: Hindi script
```

- [ ] **Step 2: Run the automated tests one more time**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: PASS with `OK`

- [ ] **Step 3: Validate each language combination manually**

Run the app:

```bash
python main.py
```

Verify:
- English context + English output with spoken phrase `I need to go tomorrow`
- English context + Hindi output with spoken phrase `I need to go tomorrow`
- Hindi context + English output with spoken phrase `मुझे कल जाना है`
- Hindi context + Hindi output with spoken phrase `मुझे कल जाना है`

Expected:
- the first mode types English text
- the second mode types Hindi script
- the third mode types romanized Hindi
- the fourth mode types Hindi script

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add language mode usage"
```

## Self-Review

### Spec coverage

- Persistent `Context Language` and `Output Language`: covered by Task 1 and Task 3.
- Correct transcription language for English/Hindi context: covered by Task 3.
- Conversion only when output differs from context: covered by Task 2 and Task 3.
- Hindi context -> English output means romanized Hindi, not translation: covered by Task 2 and Task 4 manual validation.
- English context -> Hindi output means Hindi script: covered by Task 2 and Task 4 manual validation.
- Settings survive relaunch: covered by Task 1 persistence and Task 3 manual smoke-test.
- Error handling for empty/failed conversion: covered by Task 2 unit tests and Task 3 integration path.

### Placeholder scan

- No `TODO`, `TBD`, or deferred implementation markers remain.
- Every file path is explicit.
- Every test and command is concrete.

### Type consistency

- `LanguageSettings.context_language` and `LanguageSettings.output_language` use stable codes: `en`, `hi`.
- `LANGUAGE_LABELS` is the single source of truth for menu labels.
- `convert_transcript()` accepts the same language-code values used by settings and menu wiring.
