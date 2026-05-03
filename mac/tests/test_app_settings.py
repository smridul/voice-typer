import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import app_settings
from app_settings import (
    DEFAULT_CONTEXT_LANGUAGE,
    DEFAULT_OUTPUT_LANGUAGE,
    AppSettings,
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


class FakeTimer:
    def __init__(self, callback, interval):
        self.callback = callback
        self.interval = interval
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakeAudioArray:
    def tobytes(self):
        return b"fake-audio"


class FakeGroqClient:
    def __init__(self, api_key, **kwargs):
        self.api_key = api_key
        self.kwargs = kwargs
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
    hotkey_permission=True,
    hotkey_prompt_result=False,
    default_devices=(0, 1),
    available_devices=None,
    input_stream_factory=None,
):
    fake_rumps = types.ModuleType("rumps")
    fake_rumps.MenuItem = FakeMenuItem
    fake_rumps.App = FakeApp
    fake_rumps.Timer = FakeTimer
    fake_rumps.notification = (
        lambda app_name, title, message: notifications.append(
            (app_name, title, message)
        )
    )

    fake_sounddevice = types.ModuleType("sounddevice")
    if available_devices is None:
        available_devices = [
            {"name": "Fake Mic", "max_input_channels": 1},
            {"name": "Fake Speakers", "max_input_channels": 0},
        ]
    if input_stream_factory is None:
        input_stream_factory = lambda **kwargs: FakeStream()
    fake_sounddevice.InputStream = input_stream_factory
    fake_sounddevice.default = types.SimpleNamespace(device=list(default_devices))
    fake_sounddevice.query_devices = lambda: available_devices

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.concatenate = lambda frames, axis=0: FakeAudioArray()

    clipboard_state = {"value": None}
    fake_pyperclip = types.ModuleType("pyperclip")
    fake_pyperclip.copy = lambda text: clipboard_state.__setitem__("value", text)

    fake_pyautogui = types.ModuleType("pyautogui")
    fake_pyautogui.hotkey = lambda *keys: None

    fake_keyboard = types.ModuleType("pynput.keyboard")
    fake_keyboard.GlobalHotKeys = FakeHotKeys

    fake_pynput = types.ModuleType("pynput")
    fake_pynput.keyboard = fake_keyboard

    fake_groq = types.ModuleType("groq")
    fake_groq.Groq = FakeGroqClient
    fake_groq.AuthenticationError = type("AuthenticationError", (Exception,), {})

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

    module.has_hotkey_permission = lambda: hotkey_permission
    module.prompt_for_hotkey_permission = lambda: hotkey_prompt_result
    module._test_keychain_state = keychain_state
    module._test_settings_path = Path(migrated_settings_path)
    module._test_clipboard_state = clipboard_state
    return module


class LanguagePreferencesTests(unittest.TestCase):
    def test_start_recording_uses_first_input_device_when_default_missing(self):
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
        self.assertEqual(app.title, "🔴")
        self.assertEqual(app._status_item.title, "Status: Recording…")
        self.assertEqual(stream_calls[0]["device"], 1)

    def test_start_recording_resets_status_when_stream_creation_fails(self):
        notifications = []
        main = load_main_module(
            notifications,
            input_stream_factory=lambda **kwargs: (_ for _ in ()).throw(OSError("No input device")),
        )
        app = main.VoiceTyper()

        app._start_recording()

        self.assertFalse(app.recording)
        self.assertEqual(app.title, "🎙️")
        self.assertEqual(app._status_item.title, "Status: Ready")
        self.assertEqual(app.frames, [])
        self.assertEqual(app._stream, None)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Error")
        self.assertIn("No input device", notifications[0][2])

    def test_start_recording_stops_when_microphone_permission_not_granted(self):
        notifications = []
        stream_calls = []
        main = load_main_module(
            notifications,
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(),
        )
        main.request_microphone_permission = lambda: False
        app = main.VoiceTyper()

        app._start_recording()

        self.assertFalse(app.recording)
        self.assertEqual(app.title, "🎙️")
        self.assertEqual(app._status_item.title, "Status: Ready")
        self.assertEqual(stream_calls, [])
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Permissions Required")
        self.assertIn("Microphone", notifications[0][2])

    def test_load_settings_returns_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing-settings.json"
            settings = load_settings(missing_path)

        self.assertEqual(
            settings,
            AppSettings(
                context_language=DEFAULT_CONTEXT_LANGUAGE,
                output_language=DEFAULT_OUTPUT_LANGUAGE,
            ),
        )

    def test_save_settings_round_trips_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            expected = AppSettings(context_language="hi", output_language="en")

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

    def test_save_settings_preserves_existing_file_when_write_is_interrupted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            original = AppSettings(context_language="hi", output_language="en")
            updated = AppSettings(context_language="en", output_language="hi")
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
                app_settings.tempfile,
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
        from app_settings import LANGUAGE_LABELS

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
                AppSettings(context_language="hi", output_language="en"),
            )
            self.assertEqual(
                json.loads(settings_path.read_text(encoding="utf-8")),
                {
                    "context_language": "hi",
                    "output_language": "en",
                    "input_device_name": None,
                },
            )
            self.assertEqual(app._context_language_items["hi"].state, 1)
            self.assertEqual(app._context_language_items["en"].state, 0)
            self.assertEqual(notifications, [])

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
            app.settings = AppSettings(context_language="hi", output_language="en")
            app.frames = [object()]

            transcription_calls = []
            conversion_calls = []
            typed_text = []

            def create_transcription(**kwargs):
                transcription_calls.append(kwargs)
                app.settings = AppSettings(
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

    def test_type_text_uses_osascript_paste_after_copying_clipboard(self):
        notifications = []
        main = load_main_module(notifications)
        app = main.VoiceTyper()
        run_calls = []

        def fake_run(command, capture_output=False, text=False, check=False):
            run_calls.append(
                {
                    "command": command,
                    "capture_output": capture_output,
                    "text": text,
                    "check": check,
                }
            )
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(main.subprocess, "run", side_effect=fake_run):
            with patch.object(main.time, "sleep", return_value=None):
                app._type_text("hello world")

        self.assertEqual(main._test_clipboard_state["value"], "hello world")
        self.assertEqual(
            run_calls,
            [
                {
                    "command": [
                        "osascript",
                        "-e",
                        'tell application "System Events" to keystroke "v" using command down',
                    ],
                    "capture_output": True,
                    "text": True,
                    "check": False,
                }
            ],
        )
        self.assertEqual(notifications, [])

    def test_type_text_keeps_clipboard_when_paste_command_fails(self):
        notifications = []
        main = load_main_module(notifications)
        app = main.VoiceTyper()

        with patch.object(
            main.subprocess,
            "run",
            return_value=types.SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="Automation not allowed",
            ),
        ):
            with patch.object(main.time, "sleep", return_value=None):
                app._type_text("hello world")

        self.assertEqual(main._test_clipboard_state["value"], "hello world")
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Copied to Clipboard")
        self.assertIn("Cmd+V", notifications[0][2])

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

    def test_invalid_key_after_authentication_error_requires_new_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            notifications = []
            settings_path = Path(tmpdir) / "settings.json"
            main = load_main_module(
                notifications,
                migrated_settings_path=settings_path,
            )
            app = main.VoiceTyper()
            app.frames = [object()]
            app.client = types.SimpleNamespace(
                audio=types.SimpleNamespace(
                    transcriptions=types.SimpleNamespace(
                        create=lambda **kwargs: (_ for _ in ()).throw(
                            main.AuthenticationError("Invalid API Key")
                        )
                    )
                )
            )

            app._stop_and_transcribe()

            self.assertEqual(app._status_item.title, "Status: API key invalid")
            self.assertTrue(app._api_key_invalid)
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0][0], "VoiceTyper")
            self.assertEqual(notifications[0][1], "Invalid API Key")
            self.assertIn("Set API Key", notifications[0][2])

    def test_hotkey_prompts_for_new_key_when_stored_key_is_invalid(self):
        notifications = []
        main = load_main_module(notifications)
        app = main.VoiceTyper()
        app._api_key_invalid = True

        app._on_hotkey()

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Setup Required")
        self.assertIn("invalid", notifications[0][2].lower())

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

    def test_client_uses_request_timeout(self):
        notifications = []
        main = load_main_module(notifications)
        app = main.VoiceTyper()

        self.assertIsNotNone(app.client)
        self.assertEqual(app.client.kwargs["timeout"], main.GROQ_REQUEST_TIMEOUT_SECONDS)

    def test_stop_and_transcribe_notifies_when_transcript_is_empty(self):
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

            app.client = types.SimpleNamespace(
                audio=types.SimpleNamespace(
                    transcriptions=types.SimpleNamespace(
                        create=lambda **kwargs: types.SimpleNamespace(text="   ")
                    )
                )
            )

            app._stop_and_transcribe()

            self.assertEqual(typed_text, [])
            self.assertEqual(app.title, "🎙️")
            self.assertEqual(app._status_item.title, "Status: Ready")
            self.assertEqual(len(notifications), 1)
            self.assertEqual(notifications[0][0], "VoiceTyper")
            self.assertEqual(notifications[0][1], "No Speech Detected")
            self.assertIn("longer", notifications[0][2])

    def test_missing_hotkey_permission_warns_on_startup(self):
        notifications = []
        main = load_main_module(notifications, hotkey_permission=False)
        prompts = []
        main.prompt_for_hotkey_permission = lambda: prompts.append(True)

        app = main.VoiceTyper()

        self.assertEqual(app._status_item.title, "Status: Hotkey permission required")
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][0], "VoiceTyper")
        self.assertEqual(notifications[0][1], "Permissions Required")
        self.assertIn("Accessibility", notifications[0][2])
        self.assertIn("Input Monitoring", notifications[0][2])
        self.assertIsNone(app._hotkey_listener)
        self.assertTrue(app._hotkey_permission_timer.started)
        self.assertEqual(prompts, [True])

    def test_hotkey_listener_starts_after_permission_becomes_available(self):
        notifications = []
        permission_state = {"allowed": False}
        main = load_main_module(notifications, hotkey_permission=False)
        main.has_hotkey_permission = lambda: permission_state["allowed"]

        app = main.VoiceTyper()

        self.assertFalse(app._hotkey_enabled)
        self.assertIsNone(app._hotkey_listener)

        permission_state["allowed"] = True
        app._refresh_hotkey_permission(None)

        self.assertTrue(app._hotkey_enabled)
        self.assertIsNotNone(app._hotkey_listener)
        self.assertTrue(app._hotkey_listener.started)
        self.assertTrue(app._hotkey_permission_timer.stopped)
        self.assertEqual(app._status_item.title, "Status: Ready")


if __name__ == "__main__":
    unittest.main()
