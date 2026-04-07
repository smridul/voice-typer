import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import language_preferences
from language_preferences import (
    DEFAULT_CONTEXT_LANGUAGE,
    DEFAULT_OUTPUT_LANGUAGE,
    LanguageSettings,
    load_settings,
    save_settings,
)


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


class FakeApp:
    def __init__(
        self,
        name,
        title=None,
        icon=None,
        template=None,
        menu=None,
        quit_button="Quit",
    ):
        self.name = name
        self.title = title
        self.menu = menu or []
        self.quit_button = quit_button


class FakeStream:
    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class FakeHotKeys:
    def __init__(self, mapping):
        self.mapping = mapping
        self.daemon = False
        self.started = False

    def start(self):
        self.started = True


class FakeAudioArray:
    def tobytes(self):
        return b"fake-audio"


class FakeGroqClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.audio = types.SimpleNamespace(
            transcriptions=types.SimpleNamespace(
                create=lambda **kwargs: types.SimpleNamespace(text=""),
            )
        )


def load_main_module(
    notifications,
    *,
    migrated_settings_path=None,
    initial_api_key="test-key",
):
    fake_rumps = types.ModuleType("rumps")
    fake_rumps.MenuItem = FakeMenuItem
    fake_rumps.App = FakeApp
    fake_rumps.notification = (
        lambda app_name, title, message: notifications.append(
            (app_name, title, message)
        )
    )

    fake_sounddevice = types.ModuleType("sounddevice")
    fake_sounddevice.InputStream = lambda **kwargs: FakeStream()

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.concatenate = lambda frames, axis=0: FakeAudioArray()

    fake_pyperclip = types.ModuleType("pyperclip")
    fake_pyperclip.copy = lambda text: None

    fake_pyautogui = types.ModuleType("pyautogui")
    fake_pyautogui.hotkey = lambda *keys: None

    fake_keyboard = types.ModuleType("pynput.keyboard")
    fake_keyboard.GlobalHotKeys = FakeHotKeys

    fake_pynput = types.ModuleType("pynput")
    fake_pynput.keyboard = fake_keyboard

    fake_groq = types.ModuleType("groq")
    fake_groq.Groq = FakeGroqClient

    if migrated_settings_path is None:
        migrated_settings_path = (
            Path(tempfile.gettempdir())
            / f"voice-typer-settings-{len(notifications)}-{id(notifications)}.json"
        )

    keychain_state = {
        "api_key": initial_api_key,
        "saved_keys": [],
    }

    fake_app_paths = types.ModuleType("app_paths")
    fake_app_paths.migrate_legacy_settings_if_needed = (
        lambda home_dir=None, repo_dir=None: Path(migrated_settings_path)
    )

    fake_keychain = types.ModuleType("keychain")

    class FakeKeychainError(Exception):
        pass

    fake_keychain.KeychainError = FakeKeychainError
    fake_keychain.load_api_key = lambda: keychain_state["api_key"]

    def save_api_key(api_key):
        keychain_state["api_key"] = api_key
        keychain_state["saved_keys"].append(api_key)

    fake_keychain.save_api_key = save_api_key

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    module_name = f"voice_typer_main_test_{len(notifications)}_{id(notifications)}"

    with patch.dict(
        sys.modules,
        {
            "rumps": fake_rumps,
            "sounddevice": fake_sounddevice,
            "numpy": fake_numpy,
            "pyperclip": fake_pyperclip,
            "pyautogui": fake_pyautogui,
            "pynput": fake_pynput,
            "pynput.keyboard": fake_keyboard,
            "groq": fake_groq,
            "app_paths": fake_app_paths,
            "keychain": fake_keychain,
        },
    ):
        spec = importlib.util.spec_from_file_location(module_name, main_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    module._test_keychain_state = keychain_state
    module._test_settings_path = Path(migrated_settings_path)
    return module


class LanguagePreferencesTests(unittest.TestCase):
    def test_load_settings_returns_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing-settings.json"
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

    def test_load_settings_falls_back_to_defaults_for_invalid_json_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text("[]", encoding="utf-8")

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

    def test_save_settings_preserves_existing_file_when_write_is_interrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            original = LanguageSettings(context_language="hi", output_language="en")
            updated = LanguageSettings(context_language="en", output_language="hi")
            save_settings(settings_path, original)

            interrupted_temp_path = Path(tmpdir) / "settings-interrupted.tmp"

            class InterruptedTempFile:
                def __init__(self, *args, **kwargs):
                    self.name = str(interrupted_temp_path)

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def write(self, data):
                    interrupted_temp_path.write_text(
                        '{"context_language":',
                        encoding="utf-8",
                    )
                    raise OSError("disk full")

            with patch.object(
                language_preferences.tempfile,
                "NamedTemporaryFile",
                InterruptedTempFile,
            ):
                with self.assertRaises(OSError):
                    save_settings(settings_path, updated)

            self.assertEqual(load_settings(settings_path), original)
            self.assertEqual(
                sorted(path.name for path in Path(tmpdir).iterdir()),
                ["settings.json"],
            )

    def test_supported_language_labels_are_stable(self):
        from language_preferences import LANGUAGE_LABELS

        self.assertEqual(LANGUAGE_LABELS.get("en"), "English")
        self.assertEqual(LANGUAGE_LABELS.get("hi"), "Hindi")

    def test_set_context_language_persists_and_updates_menu_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()

            app._set_context_language(app._context_language_items["hi"])

            self.assertEqual(
                app.settings,
                LanguageSettings(context_language="hi", output_language="en"),
            )
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {"context_language": "hi", "output_language": "en"},
            )
            self.assertEqual(app._context_language_items["hi"].state, 1)
            self.assertEqual(app._context_language_items["en"].state, 0)
            self.assertEqual(notifications, [])

    def test_language_callbacks_keep_state_consistent_when_save_fails(self):
        for setter_name, items_attr in (
            ("_set_context_language", "_context_language_items"),
            ("_set_output_language", "_output_language_items"),
        ):
            with self.subTest(setter_name=setter_name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    notifications = []
                    settings_path = Path(tmpdir) / "settings.json"
                    main = load_main_module(
                        notifications,
                        migrated_settings_path=settings_path,
                    )
                    app = main.VoiceTyper()
                    original_settings = app.settings
                    main.save_settings = lambda path, settings: (_ for _ in ()).throw(
                        OSError("disk full")
                    )

                    getattr(app, setter_name)(getattr(app, items_attr)["hi"])

                    self.assertEqual(app.settings, original_settings)
                    self.assertEqual(app._context_language_items["en"].state, 1)
                    self.assertEqual(app._context_language_items["hi"].state, 0)
                    self.assertEqual(app._output_language_items["en"].state, 1)
                    self.assertEqual(app._output_language_items["hi"].state, 0)
                    self.assertFalse(settings_path.exists())
                    self.assertEqual(len(notifications), 1)
                    self.assertEqual(notifications[0][0], "VoiceTyper")
                    self.assertEqual(notifications[0][1], "Error")
                    self.assertIn("disk full", notifications[0][2])

    def test_stop_and_transcribe_uses_settings_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()
            app.settings = LanguageSettings(context_language="hi", output_language="en")
            app.frames = [object()]

            transcription_calls = []
            conversion_calls = []
            typed_text = []

            def create_transcription(**kwargs):
                transcription_calls.append(kwargs)
                app.settings = LanguageSettings(
                    context_language="en",
                    output_language="hi",
                )
                return types.SimpleNamespace(text="  namaste world  ")

            app.client = types.SimpleNamespace(
                audio=types.SimpleNamespace(
                    transcriptions=types.SimpleNamespace(create=create_transcription)
                )
            )
            app._type_text = typed_text.append
            main.convert_transcript = (
                lambda client, transcript, context_language, output_language: (
                    conversion_calls.append(
                        {
                            "transcript": transcript,
                            "context_language": context_language,
                            "output_language": output_language,
                        }
                    )
                    or f"{context_language}->{output_language}:{transcript}"
                )
            )

            app._stop_and_transcribe()

            self.assertEqual(transcription_calls[0]["language"], "hi")
            self.assertEqual(
                conversion_calls,
                [
                    {
                        "transcript": "namaste world",
                        "context_language": "hi",
                        "output_language": "en",
                    }
                ],
            )
            self.assertEqual(typed_text, ["hi->en:namaste world"])
            self.assertEqual(notifications, [])

    def test_stop_and_transcribe_resets_status_when_temp_audio_creation_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()
            app.frames = [object()]
            typed_text = []
            app._type_text = typed_text.append

            with patch.object(
                main.tempfile,
                "NamedTemporaryFile",
                side_effect=OSError("disk full"),
            ):
                app._stop_and_transcribe()

            self.assertEqual(app.title, "🎙️")
            self.assertEqual(app._status_item.title, "Status: Ready")
            self.assertFalse(app.recording)
            self.assertEqual(typed_text, [])
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0][0], "VoiceTyper")
            self.assertEqual(notifications[0][1], "Error")
            self.assertIn("disk full", notifications[0][2])

    def test_missing_keychain_api_key_keeps_app_in_setup_required_state(self):
        notifications = []
        main = load_main_module(notifications, initial_api_key=None)
        app = main.VoiceTyper()

        self.assertIsNone(app.client)
        self.assertEqual(app.title, "🎙️")
        self.assertEqual(app._status_item.title, "Status: API key required")

        app._on_hotkey()

        self.assertFalse(app.recording)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Setup Required")
        self.assertIn("Set API Key", notifications[0][2])

    def test_setting_api_key_updates_keychain_and_client(self):
        notifications = []
        main = load_main_module(notifications, initial_api_key=None)
        app = main.VoiceTyper()
        main.prompt_for_api_key = lambda: "new-test-key"

        app._set_api_key(None)

        self.assertEqual(main._test_keychain_state["saved_keys"], ["new-test-key"])
        self.assertIsNotNone(app.client)
        self.assertEqual(app.client.api_key, "new-test-key")
        self.assertEqual(app._status_item.title, "Status: Ready")


if __name__ == "__main__":
    unittest.main()
