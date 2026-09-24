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
    MIC_WARM_ALWAYS,
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

    def __contains__(self, key):
        return str(key) in self.children

    def clear(self):
        self.children.clear()


class FakeStatusItem:
    def __init__(self):
        self.autosave_name = None
        self.visible = None

    def setAutosaveName_(self, name):
        self.autosave_name = name

    def setVisible_(self, visible):
        self.visible = visible


class FakeRecordPanel:
    instances = []

    def __init__(self, on_toggle):
        self.on_toggle = on_toggle
        self.visible = None
        self.states = []
        self.context_menu = None
        FakeRecordPanel.instances.append(self)

    def set_context_menu(self, nsmenu):
        self.context_menu = nsmenu

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def set_state(self, title, enabled=True):
        self.states.append((title, enabled))


class FakeEventEmitter:
    def __init__(self):
        self.callbacks = []

    def register(self, callback):
        self.callbacks.append(callback)

    def emit(self):
        for callback in self.callbacks:
            callback()


class FakeMenu(list):
    """Mirrors rumps.Menu: a sequence of items backed by an NSMenu (`_menu`)."""

    def __init__(self, items=()):
        super().__init__(items)
        self._menu = object()


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

    @property
    def menu(self):
        return self._menu

    @menu.setter
    def menu(self, items):
        self._menu = FakeMenu(items)

    def run(self, **options):
        # Mirrors rumps: the status item exists only once run() has started,
        # and before_start fires right after it is created.
        self._nsapp = types.SimpleNamespace(nsstatusitem=FakeStatusItem())
        self.events.before_start.emit()


class FakeBlock:
    """Stands in for a numpy audio block; `live=False` is Bluetooth warm-up silence."""

    def __init__(self, live=True):
        self.live = live

    def any(self):
        return self.live

    def copy(self):
        return self


class FakeStream:
    # Tests that construct the stream themselves flip this off to simulate a
    # Bluetooth mic that is still bringing up its voice link.
    deliver_audio_on_start = True

    def __init__(self, callback=None, **kwargs):
        self.callback = callback
        self.kwargs = kwargs
        self.active = False
        self.closed = False

    def start(self):
        self.active = True
        if self.callback is not None and self.deliver_audio_on_start:
            self.feed(FakeBlock())

    def feed(self, block):
        self.callback(block, 1, None, None)

    def stop(self):
        self.active = False

    def close(self):
        self.active = False
        self.closed = True


class FakeHotKeys:
    def __init__(self, mapping):
        self.mapping = mapping
        self.daemon = False
        self.started = False
        self.running = False

    def start(self):
        self.started = True
        self.running = True

    def is_alive(self):
        return self.running

    def stop(self):
        self.running = False


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
    fake_rumps.events = types.SimpleNamespace(before_start=FakeEventEmitter())
    fake_rumps.App = type("FakeApp", (FakeApp,), {"events": fake_rumps.events})
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
        input_stream_factory = lambda **kwargs: FakeStream(**kwargs)
    fake_sounddevice.InputStream = input_stream_factory
    fake_sounddevice.default = types.SimpleNamespace(device=list(default_devices))
    fake_sounddevice.query_devices = lambda: available_devices
    fake_sounddevice._terminate = lambda: None
    fake_sounddevice._initialize = lambda: None

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

    fake_record_panel = types.ModuleType("record_panel")
    fake_record_panel.RecordButtonPanel = FakeRecordPanel

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
            "record_panel": fake_record_panel,
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
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(**kwargs),
        )
        app = main.VoiceTyper()

        app._start_recording()

        self.assertTrue(app.recording)
        self.assertEqual(app.title, "🔴")
        self.assertEqual(app._status_item.title, "Status: Recording…")
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
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(**kwargs),
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
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(**kwargs),
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
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(**kwargs),
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
            input_stream_factory=lambda **kwargs: stream_calls.append(kwargs) or FakeStream(**kwargs),
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
                "show_record_button": True,
                "mic_warm_seconds": 180,
            },
        )

    def test_load_settings_defaults_show_record_button_to_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({"context_language": "en", "output_language": "en"}),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertTrue(settings.show_record_button)

    def test_load_settings_preserves_hidden_record_button(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "show_record_button": False,
                }),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertFalse(settings.show_record_button)

    def test_load_settings_ignores_non_bool_show_record_button(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "show_record_button": "no",
                }),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertTrue(settings.show_record_button)

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
                    "show_record_button": True,
                    "mic_warm_seconds": 180,
                },
            )
            self.assertEqual(app._context_language_items["hi"].state, 1)
            self.assertEqual(app._context_language_items["en"].state, 0)
            self.assertEqual(notifications, [])

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
        self.assertTrue(app._hotkey_permission_timer.started)
        self.assertFalse(app._hotkey_permission_timer.stopped)
        self.assertEqual(app._status_item.title, "Status: Ready")

    def test_hotkey_health_timer_runs_even_with_permission_at_startup(self):
        app = load_main_module([]).VoiceTyper()
        self.assertTrue(app._hotkey_permission_timer.started)
        self.assertFalse(app._hotkey_permission_timer.stopped)

    def test_dead_hotkey_listener_is_replaced_and_shortcut_works(self):
        app = load_main_module([]).VoiceTyper()
        dead_listener = app._hotkey_listener
        dead_listener.running = False

        app._refresh_hotkey_permission()

        self.assertIsNot(app._hotkey_listener, dead_listener)
        self.assertTrue(app._hotkey_listener.is_alive())
        self.assertTrue(app._hotkey_enabled)
        with patch.object(app, "_start_recording") as start_recording:
            with patch("threading.Thread") as thread:
                app._hotkey_listener.mapping["<ctrl>+<space>"]()
            self.assertEqual(thread.call_args.kwargs["target"], start_recording)

    def test_healthy_listener_is_retained_without_resetting_busy_status(self):
        app = load_main_module([]).VoiceTyper()
        listener = app._hotkey_listener
        for title, status, recording in (
            ("🔴", "Status: Recording…", True),
            ("⏳", "Status: Transcribing…", False),
        ):
            app.title = title
            app._status_item.title = status
            app.recording = recording
            app._refresh_hotkey_permission()
            self.assertIs(app._hotkey_listener, listener)
            self.assertEqual(app.title, title)
            self.assertEqual(app._status_item.title, status)

    def test_permission_revocation_stops_listener_and_restoration_recovers(self):
        main = load_main_module([])
        app = main.VoiceTyper()
        listener = app._hotkey_listener
        main.has_hotkey_permission = lambda: False
        self.assertFalse(app._refresh_hotkey_permission())
        self.assertFalse(listener.running)
        self.assertFalse(app._hotkey_enabled)
        self.assertEqual(app._status_item.title, "Status: Hotkey permission required")

        main.has_hotkey_permission = lambda: True
        self.assertTrue(app._refresh_hotkey_permission())
        self.assertIsNot(app._hotkey_listener, listener)
        self.assertEqual(app._status_item.title, "Status: Ready")

    def test_keyboard_layout_is_refreshed_before_listener_starts(self):
        main = load_main_module([])
        order = []
        main.refresh_keyboard_layout_context = lambda: order.append("refresh")
        with patch.object(FakeHotKeys, "start", lambda self: order.append("start")):
            main.VoiceTyper()
        self.assertEqual(order, ["refresh", "start"])

    def test_listener_start_failure_reports_unavailable_and_retries(self):
        main = load_main_module([])
        with patch.object(FakeHotKeys, "start", side_effect=RuntimeError("tap failed")):
            app = main.VoiceTyper()
        self.assertFalse(app._hotkey_enabled)
        self.assertEqual(app._status_item.title, "Status: Hotkey reconnecting…")
        self.assertTrue(app._hotkey_permission_timer.started)

        self.assertTrue(app._refresh_hotkey_permission())
        self.assertTrue(app._hotkey_listener.running)
        self.assertEqual(app._status_item.title, "Status: Ready")

    def test_stopping_listener_is_not_replaced_until_thread_exits(self):
        app = load_main_module([]).VoiceTyper()
        listener = app._hotkey_listener
        listener.running = False
        listener.is_alive = lambda: True
        self.assertFalse(app._refresh_hotkey_permission())
        self.assertIs(app._hotkey_listener, listener)
        self.assertFalse(app._hotkey_enabled)
        self.assertEqual(app._status_item.title, "Status: Hotkey reconnecting…")


if __name__ == "__main__":
    unittest.main()


class RecordMenuItemTests(unittest.TestCase):
    def test_record_menu_item_appears_below_status_and_starts_idle(self):
        app = load_main_module([]).VoiceTyper()

        self.assertIs(app.menu[1], app._record_item)
        self.assertEqual(app._record_item.title, "Start Recording")

    def test_record_menu_item_starts_recording_when_idle(self):
        app = load_main_module([]).VoiceTyper()
        with patch.object(app, "_start_recording") as start_recording:
            with patch("threading.Thread") as thread:
                app._record_item.callback(app._record_item)
        self.assertEqual(thread.call_args.kwargs["target"], start_recording)
        thread.return_value.start.assert_called_once()

    def test_record_menu_item_stops_recording_when_recording(self):
        app = load_main_module([]).VoiceTyper()
        app.recording = True
        with patch.object(app, "_stop_and_transcribe") as stop_and_transcribe:
            with patch("threading.Thread") as thread:
                app._record_item.callback(app._record_item)
        self.assertEqual(thread.call_args.kwargs["target"], stop_and_transcribe)

    def test_record_menu_item_works_without_hotkey_permission(self):
        notifications = []
        app = load_main_module(notifications, hotkey_permission=False).VoiceTyper()
        self.assertFalse(app._hotkey_enabled)
        notifications.clear()

        with patch.object(app, "_start_recording") as start_recording:
            with patch("threading.Thread") as thread:
                app._record_item.callback(app._record_item)

        self.assertEqual(thread.call_args.kwargs["target"], start_recording)
        self.assertEqual(notifications, [])

    def test_record_menu_item_requires_api_key(self):
        notifications = []
        app = load_main_module(notifications, initial_api_key=None).VoiceTyper()

        with patch("threading.Thread") as thread:
            app._record_item.callback(app._record_item)

        thread.assert_not_called()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][1], "Setup Required")

    def test_record_menu_item_title_follows_recording_state(self):
        main = load_main_module(
            [], input_stream_factory=lambda **kwargs: FakeStream(**kwargs)
        )
        app = main.VoiceTyper()

        app._start_recording()
        self.assertEqual(app._record_item.title, "Stop Recording")

        app._stop_and_transcribe()  # no frames -> resets immediately
        self.assertEqual(app._record_item.title, "Start Recording")

    def test_record_menu_item_title_resets_when_recording_fails_to_start(self):
        main = load_main_module(
            [],
            input_stream_factory=lambda **kwargs: (_ for _ in ()).throw(OSError("no mic")),
        )
        app = main.VoiceTyper()

        app._start_recording()

        self.assertEqual(app._record_item.title, "Start Recording")


class StatusItemVisibilityTests(unittest.TestCase):
    def test_run_pins_status_item_with_stable_autosave_name_and_visible(self):
        main = load_main_module([])
        app = main.VoiceTyper()

        app.run()

        status_item = app._nsapp.nsstatusitem
        self.assertEqual(status_item.autosave_name, "VoiceTyper")
        self.assertTrue(status_item.visible)


class FloatingRecordButtonTests(unittest.TestCase):
    def setUp(self):
        FakeRecordPanel.instances.clear()

    def _run_app(self, **kwargs):
        main = load_main_module([], **kwargs)
        app = main.VoiceTyper()
        app.run()
        return main, app

    def test_panel_is_created_on_run_and_shown_by_default(self):
        _main, app = self._run_app()

        self.assertEqual(len(FakeRecordPanel.instances), 1)
        panel = FakeRecordPanel.instances[0]
        self.assertIs(app._record_panel, panel)
        self.assertTrue(panel.visible)
        self.assertEqual(panel.states, [("🎙️ Record", True)])

    def test_panel_gets_the_app_menu_as_its_context_menu(self):
        # With the menu bar icon missing, right-clicking the button is the
        # only way to reach Microphone / languages / Quit.
        _main, app = self._run_app()
        panel = FakeRecordPanel.instances[0]

        self.assertIs(panel.context_menu, app.menu._menu)

    def test_panel_click_toggles_recording(self):
        _main, app = self._run_app()
        panel = FakeRecordPanel.instances[0]

        with patch.object(app, "_start_recording") as start_recording:
            with patch("threading.Thread") as thread:
                panel.on_toggle()

        self.assertEqual(thread.call_args.kwargs["target"], start_recording)
        thread.return_value.start.assert_called_once()

    def test_panel_title_follows_recording_state(self):
        _main, app = self._run_app(
            input_stream_factory=lambda **kwargs: FakeStream(**kwargs)
        )
        panel = FakeRecordPanel.instances[0]
        panel.states.clear()

        app._start_recording()
        self.assertEqual(panel.states[-1], ("🔴 Stop", True))

        with patch.object(_main.threading, "Timer"):
            app._stop_and_transcribe()  # no frames -> resets immediately
        # The mic stays warm after a recording, so the idle button is green.
        self.assertEqual(
            panel.states,
            [("🔴 Stop", True), ("⏳ Transcribing…", False), ("🟢 Record", True)],
        )

    def test_status_updates_before_run_do_not_require_panel(self):
        main = load_main_module([])
        app = main.VoiceTyper()  # _reset_status runs during __init__

        self.assertIsNone(app._record_panel)
        app._reset_status()  # must not raise

    def test_menu_item_reflects_setting_and_toggles_visibility(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            _main, app = self._run_app(migrated_settings_path=settings_path)
            panel = FakeRecordPanel.instances[0]

            self.assertIs(app.menu[2], app._record_button_item)
            self.assertEqual(app._record_button_item.title, "Floating Record Button")
            self.assertEqual(app._record_button_item.state, 1)

            app._record_button_item.callback(app._record_button_item)

            self.assertFalse(panel.visible)
            self.assertEqual(app._record_button_item.state, 0)
            self.assertFalse(app.settings.show_record_button)
            self.assertFalse(
                json.loads(settings_path.read_text(encoding="utf-8"))["show_record_button"]
            )

            app._record_button_item.callback(app._record_button_item)

            self.assertTrue(panel.visible)
            self.assertEqual(app._record_button_item.state, 1)

    def test_panel_stays_hidden_when_setting_is_off(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(
                json.dumps({
                    "context_language": "en",
                    "output_language": "en",
                    "show_record_button": False,
                }),
                encoding="utf-8",
            )

            _main, app = self._run_app(migrated_settings_path=settings_path)

        panel = FakeRecordPanel.instances[0]
        self.assertFalse(panel.visible)
        self.assertEqual(app._record_button_item.state, 0)

    def test_hiding_panel_is_not_applied_when_save_fails(self):
        _main, app = self._run_app()
        panel = FakeRecordPanel.instances[0]

        with patch.object(app, "_save_and_apply_settings", return_value=False):
            app._record_button_item.callback(app._record_button_item)

        self.assertTrue(panel.visible)
        self.assertTrue(app.settings.show_record_button)


class MicWarmSettingsTests(unittest.TestCase):
    def _load(self, payload):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text(json.dumps(payload), encoding="utf-8")
            return load_settings(settings_path)

    def test_defaults_to_three_minutes(self):
        settings = self._load({"context_language": "en", "output_language": "en"})
        self.assertEqual(settings.mic_warm_seconds, 180)

    def test_accepts_off_custom_and_always(self):
        self.assertEqual(self._load({"mic_warm_seconds": 0}).mic_warm_seconds, 0)
        self.assertEqual(self._load({"mic_warm_seconds": 45}).mic_warm_seconds, 45)
        self.assertEqual(
            self._load({"mic_warm_seconds": MIC_WARM_ALWAYS}).mic_warm_seconds,
            MIC_WARM_ALWAYS,
        )

    def test_rejects_invalid_values(self):
        for bad in ("60", True, -5, 1.5, None):
            self.assertEqual(self._load({"mic_warm_seconds": bad}).mic_warm_seconds, 180)

    def test_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            expected = AppSettings("en", "en", mic_warm_seconds=600)
            save_settings(settings_path, expected)
            self.assertEqual(load_settings(settings_path), expected)


class MicStreamTestCase(unittest.TestCase):
    """Helpers for tests that drive the real stream lifecycle with fakes."""

    def setUp(self):
        self.streams = []
        self.timers = []
        FakeStream.deliver_audio_on_start = True

    def tearDown(self):
        FakeStream.deliver_audio_on_start = True

    def _factory(self, **kwargs):
        stream = FakeStream(**kwargs)
        self.streams.append(stream)
        return stream

    def _app(self, tmpdir, settings=None, **kwargs):
        settings_path = Path(tmpdir) / "settings.json"
        if settings is not None:
            save_settings(settings_path, settings)
        main = load_main_module(
            [],
            migrated_settings_path=settings_path,
            input_stream_factory=self._factory,
            **kwargs,
        )
        app = main.VoiceTyper()
        return main, app

    def _fake_timer(self, interval, function):
        timer = types.SimpleNamespace(
            interval=interval,
            function=function,
            daemon=False,
            started=False,
            cancelled=False,
        )
        timer.start = lambda: setattr(timer, "started", True)
        timer.cancel = lambda: setattr(timer, "cancelled", True)
        self.timers.append(timer)
        return timer


class MicWarmupTests(MicStreamTestCase):
    """Bluetooth mics send digital silence for seconds after the stream opens."""

    def test_silence_is_dropped_and_ui_waits_until_mic_is_live(self):
        FakeStream.deliver_audio_on_start = False
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            titles = []

            def wait(timeout=None):
                # Runs where _start_recording blocks: the mic is still silent.
                titles.append((app.title, app._status_item.title))
                self.streams[0].feed(FakeBlock(live=False))
                self.streams[0].feed(FakeBlock(live=True))
                return True

            with patch.object(app._mic_live, "wait", side_effect=wait):
                app._start_recording()

        self.assertEqual(titles, [("🟡", "Status: Connecting mic…")])
        self.assertEqual(app.title, "🔴")
        self.assertEqual(app._status_item.title, "Status: Recording…")
        self.assertEqual(len(app.frames), 1)
        self.assertTrue(app.frames[0].live)

    def test_times_out_and_records_anyway_when_mic_stays_silent(self):
        FakeStream.deliver_audio_on_start = False
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(app._mic_live, "wait", return_value=False):
                app._start_recording()

        self.assertTrue(app.recording)
        self.assertEqual(app.title, "🔴")

    def test_stopping_while_connecting_does_not_show_recording(self):
        FakeStream.deliver_audio_on_start = False
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)

            def wait(timeout=None):
                with patch.object(main.threading, "Timer", self._fake_timer):
                    app._stop_and_transcribe()
                return False

            with patch.object(app._mic_live, "wait", side_effect=wait):
                app._start_recording()

        self.assertFalse(app.recording)
        self.assertEqual(app.title, "🎙️")
        self.assertEqual(app._record_item.title, "Start Recording")

    def test_stream_stays_open_after_stop_and_is_reused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
                app._start_recording()

        self.assertEqual(len(self.streams), 1)
        self.assertFalse(self.streams[0].closed)
        self.assertEqual(self.timers[0].interval, 180)
        self.assertTrue(self.timers[0].started)
        self.assertTrue(self.timers[0].cancelled)
        self.assertEqual(app.title, "🔴")

    def test_warm_timer_closes_stream(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            self.timers[0].function()

        self.assertTrue(self.streams[0].closed)
        self.assertIsNone(app._stream)

    def test_off_closes_stream_immediately(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir, AppSettings("en", "en", mic_warm_seconds=0))
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()

        self.assertTrue(self.streams[0].closed)
        self.assertEqual(self.timers, [])

    def test_always_never_schedules_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(
                tmpdir, AppSettings("en", "en", mic_warm_seconds=MIC_WARM_ALWAYS)
            )
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()

        self.assertFalse(self.streams[0].closed)
        self.assertEqual(self.timers, [])

    def test_dead_warm_stream_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
                self.streams[0].active = False  # e.g. the mic was switched off
                app._start_recording()

        self.assertEqual(len(self.streams), 2)
        self.assertTrue(self.streams[0].closed)

    def test_changing_microphone_closes_warm_stream(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(
                tmpdir,
                available_devices=[{"name": "External Microphone", "max_input_channels": 1}],
            )
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            app._set_microphone(app._microphone_items["External Microphone"])

        self.assertTrue(self.streams[0].closed)
        self.assertIsNone(app._stream)

    def test_refreshing_devices_closes_warm_stream_before_portaudio_reinit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            closed_at_terminate = []
            main.sd._terminate = lambda: closed_at_terminate.append(self.streams[0].closed)
            app._refresh_microphone_devices(None)

        self.assertEqual(closed_at_terminate, [True])

    def test_menu_selects_and_persists_warm_window(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            self.assertEqual(app._mic_warm_items[180].state, 1)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._set_mic_warm_seconds(app._mic_warm_items[600])
            payload = json.loads((Path(tmpdir) / "settings.json").read_text(encoding="utf-8"))

        self.assertEqual(app.settings.mic_warm_seconds, 600)
        self.assertEqual(payload["mic_warm_seconds"], 600)
        self.assertEqual(app._mic_warm_items[600].state, 1)
        self.assertEqual(app._mic_warm_items[180].state, 0)

    def test_switching_to_off_closes_idle_warm_stream(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
                app._set_mic_warm_seconds(app._mic_warm_items[0])

        self.assertTrue(self.streams[0].closed)

    def test_changing_language_keeps_other_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(
                tmpdir,
                AppSettings("en", "en", show_record_button=False, mic_warm_seconds=600),
            )
            app._set_context_language(app._context_language_items["hi"])
            app._set_output_language(app._output_language_items["hi"])

        self.assertFalse(app.settings.show_record_button)
        self.assertEqual(app.settings.mic_warm_seconds, 600)


class ReadyIndicatorTests(MicStreamTestCase):
    """The floating button shows 🟢 while the mic is warm, 🎙️ once it is closed."""

    def _run(self, tmpdir, settings=None):
        FakeRecordPanel.instances.clear()
        main, app = self._app(tmpdir, settings)
        app.run()
        return main, app, FakeRecordPanel.instances[0]

    def test_green_after_recording_then_mic_icon_when_window_ends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app, panel = self._run(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            self.assertEqual(panel.states[-1], ("🟢 Record", True))

            self.timers[0].function()  # warm window ends

        self.assertEqual(panel.states[-1], ("🎙️ Record", True))

    def test_off_goes_straight_back_to_mic_icon(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app, panel = self._run(tmpdir, AppSettings("en", "en", mic_warm_seconds=0))
            app._start_recording()
            app._stop_and_transcribe()

        self.assertEqual(panel.states[-1], ("🎙️ Record", True))

    def test_dead_warm_stream_is_not_shown_as_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app, panel = self._run(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            self.streams[0].active = False  # mic switched off while warm
            app._reset_status()  # what the 2-second health check does

        self.assertEqual(panel.states[-1], ("🎙️ Record", True))

    def test_closing_warm_stream_during_transcription_keeps_busy_button(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app, panel = self._run(tmpdir)
            app._start_recording()
            app.recording = False
            app._status_item.title = "Status: Transcribing…"
            panel.states.clear()
            app._close_input_stream()

        self.assertEqual(panel.states, [])

    def test_always_turns_green_once_mic_is_live_at_launch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app, panel = self._run(
                tmpdir, AppSettings("en", "en", mic_warm_seconds=MIC_WARM_ALWAYS)
            )
            app._warm_up_mic()

        self.assertEqual(panel.states[-1], ("🟢 Record", True))


class MenuBarReadyIndicatorTests(MicStreamTestCase):
    """The menu bar icon and status line mirror the floating button's warm state."""

    def test_menu_bar_shows_warm_mic_then_returns_to_mic_icon(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            self.assertEqual(app.title, "🟢")
            self.assertEqual(app._status_item.title, "Status: Ready (mic warm)")

            self.timers[0].function()  # warm window ends

        self.assertEqual(app.title, "🎙️")
        self.assertEqual(app._status_item.title, "Status: Ready")

    def test_problem_status_wins_over_warm_mic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            with patch.object(main.threading, "Timer", self._fake_timer):
                app._start_recording()
                app._stop_and_transcribe()
            app._hotkey_enabled = False
            app._hotkey_permission_granted = False
            app._reset_status()

        self.assertEqual(app._status_item.title, "Status: Hotkey permission required")

    def test_window_ending_mid_transcription_keeps_busy_menu_bar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main, app = self._app(tmpdir)
            app._start_recording()
            app.recording = False
            app.title = "⏳"
            app._status_item.title = "Status: Transcribing…"
            app._close_input_stream()

        self.assertEqual(app.title, "⏳")
        self.assertEqual(app._status_item.title, "Status: Transcribing…")
