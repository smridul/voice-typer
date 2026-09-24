#!/usr/bin/env python3
"""
voice-typer-mac
---------------
Press Ctrl+Space to start recording your voice.
Press it again to transcribe and type the text wherever your cursor is.

Setup:
    1. Run: python3 -m pip install -r requirements.txt
    2. Run: python3 main.py
    3. Use "Set API Key…" in the menu bar app to save your Groq API key
    4. Allow Accessibility access when macOS prompts you
"""

import contextlib
import threading
import tempfile
import wave
import time
import os
import subprocess
import sys
import ctypes
from dataclasses import replace
from pathlib import Path

import rumps
import sounddevice as sd
import numpy as np
import pyperclip
from pynput import keyboard
from groq import AuthenticationError, Groq
from app_settings import (
    LANGUAGE_LABELS,
    MIC_WARM_ALWAYS,
    MIC_WARM_LABELS,
    AppSettings,
    load_settings,
    save_settings,
)
from language_processing import convert_transcript
from app_paths import migrate_legacy_settings_if_needed
from keychain import KeychainError, load_api_key, save_api_key
from mic_warmup import LiveAudioDetector
from record_panel import RecordButtonPanel

SAMPLE_RATE = 16000   # Hz — Whisper works best at 16kHz
CHANNELS    = 1
HOTKEY      = "<ctrl>+<space>"   # Change this if you prefer a different combo
MIC_PERMISSION_HELPER = "VoiceTyperMicPermission"
GROQ_REQUEST_TIMEOUT_SECONDS = 30.0
SYSTEM_DEFAULT_MIC_LABEL = "System Default"
REFRESH_MIC_DEVICES_LABEL = "Refresh devices"
RECORD_START_LABEL = "Start Recording"
RECORD_STOP_LABEL = "Stop Recording"
SHOW_RECORD_BUTTON_LABEL = "Floating Record Button"
RECORD_BUTTON_IDLE_TITLE = "🎙️ Record"
# Idle, but the mic is still open from "Keep Mic Ready": recording starts instantly.
RECORD_BUTTON_READY_TITLE = "🟢 Record"
RECORD_BUTTON_RECORDING_TITLE = "🔴 Stop"
RECORD_BUTTON_BUSY_TITLE = "⏳ Transcribing…"
RECORD_BUTTON_CONNECTING_TITLE = "🟡 Connecting…"
MIC_WARM_MENU_LABEL = "Keep Mic Ready"
# Bluetooth mics (DJI, AirPods) deliver junk for ~3-5s after the stream opens
# while macOS switches them to the hands-free profile (see mic_warmup.py). Give up waiting
# after this long and record anyway, so a mic that is genuinely muted still
# ends in "No Speech Detected" rather than hanging.
MIC_CONNECT_TIMEOUT_SECONDS = 8
STATUS_ITEM_AUTOSAVE_NAME = "VoiceTyper"


def _load_pynput_darwin_modules():
    if sys.platform != "darwin":
        return None, None
    try:
        from pynput._util import darwin as pynput_util_darwin
        from pynput.keyboard import _darwin as pynput_keyboard_darwin
    except ImportError:
        return None, None
    return pynput_util_darwin, pynput_keyboard_darwin


_PYNPUT_UTIL_DARWIN, _PYNPUT_KEYBOARD_DARWIN = _load_pynput_darwin_modules()
_keyboard_layout_context = {"value": None, "loaded": False}


def refresh_keyboard_layout_context():
    """Load the keyboard layout on the main thread for pynput's listener.

    macOS 26 asserts that Text Input Source lookups run on the main queue.
    pynput's keyboard Listener performs them on its own thread when it starts,
    which kills the whole process (SIGTRAP in dispatch_assert_queue_fail)
    whenever the input-source cache is stale, e.g. right after Accessibility
    permission changes. Load the layout here instead and let the listener reuse
    it through install_cached_keycode_context().
    """
    if _PYNPUT_UTIL_DARWIN is None:
        return False
    if threading.current_thread() is not threading.main_thread():
        return _keyboard_layout_context["loaded"]
    try:
        with _PYNPUT_UTIL_DARWIN.keycode_context() as context:
            _keyboard_layout_context["value"] = context
            _keyboard_layout_context["loaded"] = True
    except Exception as error:
        print(f"⚠️ Unable to load keyboard layout for hotkey listener: {error}", flush=True)
    return _keyboard_layout_context["loaded"]


@contextlib.contextmanager
def _cached_keycode_context():
    # GlobalHotKeys never translates keycodes through this context, so an
    # empty value is harmless if nothing has been loaded yet.
    yield _keyboard_layout_context["value"]


def install_cached_keycode_context():
    if _PYNPUT_KEYBOARD_DARWIN is None:
        return False
    _PYNPUT_KEYBOARD_DARWIN.keycode_context = _cached_keycode_context
    return True


install_cached_keycode_context()


def has_hotkey_permission():
    if sys.platform != "darwin":
        return True

    try:
        application_services = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        application_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(application_services.AXIsProcessTrusted())
    except Exception as error:
        print(f"⚠️ Unable to check macOS hotkey permission: {error}")
        return True


def prompt_for_hotkey_permission():
    if sys.platform != "darwin":
        return True

    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            check=False,
        )
    except OSError as error:
        print(f"⚠️ Unable to open Accessibility settings: {error}")

    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'display dialog "Enable VoiceTyper in Accessibility and Input Monitoring, then reopen the app." buttons {"OK"} default button "OK"',
            ],
            check=False,
        )
    except OSError as error:
        print(f"⚠️ Unable to show Accessibility instructions: {error}")

    return has_hotkey_permission()


def prompt_for_api_key():
    script = (
        'display dialog "Enter Groq API key" default answer "" '
        'with hidden answer buttons {"Cancel", "Save"} default button "Save"'
    )

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        print(f"❌ Failed to open API key prompt: {error}")
        return None

    if result.returncode != 0:
        return None

    marker = "text returned:"
    if marker not in result.stdout:
        return None

    value = result.stdout.split(marker, 1)[1].strip()
    return value or None


def _microphone_permission_helper_path():
    executable_dir = Path(sys.executable).resolve().parent
    bundled_helper = executable_dir / MIC_PERMISSION_HELPER
    if bundled_helper.exists():
        return bundled_helper

    repo_helper = Path(__file__).resolve().parent / MIC_PERMISSION_HELPER
    if repo_helper.exists():
        return repo_helper

    return None


def request_microphone_permission():
    if sys.platform != "darwin":
        return True

    helper_path = _microphone_permission_helper_path()
    if helper_path is None:
        return True

    try:
        result = subprocess.run(
            [str(helper_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        print(f"⚠️ Unable to request microphone permission: {error}")
        return True

    if result.returncode == 0:
        return True

    message = result.stderr.strip() or result.stdout.strip() or "Microphone access is required."
    print(f"❌ Microphone permission not granted: {message}")
    return False


# ── App ───────────────────────────────────────────────────────────────────────
class VoiceTyper(rumps.App):
    def __init__(self):
        super().__init__("VoiceTyper", icon=None, quit_button="Quit")
        self._settings_path = migrate_legacy_settings_if_needed(
            repo_dir=Path(__file__).resolve().parent
        )
        self.settings = load_settings(self._settings_path)
        self.title = "🎙️"
        self._status_item = rumps.MenuItem("Status: Ready")
        # Mouse-only alternative to the hotkey; title toggles with recording state.
        self._record_item = rumps.MenuItem(
            RECORD_START_LABEL,
            callback=self._on_record_menu_item,
        )
        # Floating on-screen button: the fallback when macOS refuses to show
        # the menu bar icon at all. Created in _setup_record_button.
        self._record_panel = None
        self._record_button_item = rumps.MenuItem(
            SHOW_RECORD_BUTTON_LABEL,
            callback=self._toggle_record_button,
        )
        self._set_api_key_item = rumps.MenuItem(
            "Set API Key…",
            callback=self._set_api_key,
        )
        self._microphone_menu = None
        self._microphone_items = {}
        self._mic_warm_items = {}
        self._context_language_items = {}
        self._output_language_items = {}
        self.menu = [
            self._status_item,
            self._record_item,
            self._record_button_item,
            self._set_api_key_item,
            None,
            self._build_microphone_menu(),
            self._build_mic_warm_menu(),
            None,
            *self._build_language_menu(),
        ]
        self._refresh_microphone_menu()
        self._refresh_language_menu()
        self._refresh_record_button_menu()
        self._refresh_mic_warm_menu()

        self.client    = None
        self._api_key_invalid = False
        self.recording = False
        self.frames    = []
        # The input stream outlives a single recording (see "Keep Mic Ready").
        # _stream_lock guards _stream, _stream_device and _mic_warm_timer.
        self._stream   = None
        self._stream_device = None
        self._stream_lock = threading.Lock()
        self._mic_warm_timer = None
        # Set once the open stream delivers real audio (LiveAudioDetector).
        self._mic_live = threading.Event()
        self._live_detector = LiveAudioDetector()
        self._hotkey_listener = None
        self._hotkey_enabled = False
        self._hotkey_permission_granted = False
        self._hotkey_permission_timer = rumps.Timer(self._refresh_hotkey_permission, 2)
        self._refresh_client_state(notify=False)

        self._refresh_hotkey_permission()
        # Keep supervising the listener for the entire app lifetime. The menu
        # bar can remain alive even after pynput's background thread crashes.
        self._hotkey_permission_timer.start()
        if not self._hotkey_permission_granted:
            prompt_for_hotkey_permission()
            self._status_item.title = "Status: Hotkey permission required"
            rumps.notification(
                "VoiceTyper",
                "Permissions Required",
                "Grant Accessibility and Input Monitoring to VoiceTyper.app. VoiceTyper will start listening automatically once permission is available.",
            )
            print("❌ VoiceTyper hotkey listener not started: waiting for Accessibility/Input Monitoring permission.")

        print(f"✅ VoiceTyper running. Press {HOTKEY} to toggle recording.", flush=True)

    def run(self, **options):
        # rumps creates the NSStatusItem inside run() and emits before_start
        # right after, which is the earliest point we can reach it.
        rumps.events.before_start.register(self._pin_status_item)
        rumps.events.before_start.register(self._setup_record_button)
        rumps.events.before_start.register(self._warm_up_mic_if_always)
        super().run(**options)

    def _pin_status_item(self):
        """Give the status item a stable identity so macOS 26 keeps it visible.

        Control Center on macOS 26 hosts every status item and tracks its
        visibility by autosave name. rumps never sets one, so the item gets a
        transient "Item-N" identity; once Control Center has recorded that slot
        as hidden, the icon silently never appears again after a relaunch.
        """
        status_item = self._nsapp.nsstatusitem
        status_item.setAutosaveName_(STATUS_ITEM_AUTOSAVE_NAME)
        status_item.setVisible_(True)

    def _setup_record_button(self):
        # AppKit windows need the application to exist, so this waits for
        # before_start like the status item does.
        self._record_panel = RecordButtonPanel(self._toggle_recording)
        # Right-clicking the button opens the same menu the status item has,
        # so Microphone / languages / Quit stay reachable without the icon.
        self._record_panel.set_context_menu(self.menu._menu)
        self._record_panel.set_state(self._idle_record_button_title())
        self._apply_record_button_visibility()

    def _apply_record_button_visibility(self):
        if self._record_panel is None:
            return
        if self.settings.show_record_button:
            self._record_panel.show()
        else:
            self._record_panel.hide()

    def _update_record_button(self, title, enabled=True):
        if self._record_panel is not None:
            self._record_panel.set_state(title, enabled)

    def _refresh_record_button_menu(self):
        self._record_button_item.state = int(self.settings.show_record_button)

    def _toggle_record_button(self, _sender):
        updated_settings = replace(
            self.settings,
            show_record_button=not self.settings.show_record_button,
        )
        if self._save_and_apply_settings(updated_settings):
            self._apply_record_button_visibility()

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

        if self._microphone_items:
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
        # PortAudio caches the device list at init time, so devices paired
        # after app launch (e.g. AirPods) won't appear without re-init.
        # Terminating PortAudio invalidates open streams, so drop the warm one.
        self._close_input_stream()
        try:
            sd._terminate()
            sd._initialize()
        except Exception as error:
            print(f"⚠️ PortAudio re-init failed: {error}")

        self._populate_microphone_devices()
        self._warm_up_mic_if_always()
        if self._microphone_menu is not None:
            refresh_item = rumps.MenuItem(
                REFRESH_MIC_DEVICES_LABEL,
                callback=self._refresh_microphone_devices,
            )
            self._microphone_menu[REFRESH_MIC_DEVICES_LABEL] = refresh_item

    def _refresh_microphone_menu(self):
        selected = self.settings.input_device_name
        for label, item in self._microphone_items.items():
            if selected is None:
                item.state = int(label == SYSTEM_DEFAULT_MIC_LABEL)
            else:
                item.state = int(label == selected)

    def _build_language_menu(self):
        context_menu = rumps.MenuItem("Context Language")
        output_menu = rumps.MenuItem("Output Language")

        for language_code, label in LANGUAGE_LABELS.items():
            context_item = rumps.MenuItem(label, callback=self._set_context_language)
            context_item.language_code = language_code
            self._context_language_items[language_code] = context_item
            context_menu[label] = context_item

            output_item = rumps.MenuItem(label, callback=self._set_output_language)
            output_item.language_code = language_code
            self._output_language_items[language_code] = output_item
            output_menu[label] = output_item

        return [context_menu, output_menu]

    def _refresh_language_menu(self):
        for language_code, item in self._context_language_items.items():
            item.state = int(language_code == self.settings.context_language)
        for language_code, item in self._output_language_items.items():
            item.state = int(language_code == self.settings.output_language)

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
        self._refresh_record_button_menu()
        self._refresh_mic_warm_menu()
        return True

    def _set_context_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.context_language:
            return

        updated_settings = replace(self.settings, context_language=language_code)
        self._save_and_apply_settings(updated_settings)

    def _set_output_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.output_language:
            return

        updated_settings = replace(self.settings, output_language=language_code)
        self._save_and_apply_settings(updated_settings)

    def _set_microphone(self, sender):
        device_name = getattr(sender, "device_name", None)
        if device_name == self.settings.input_device_name:
            return

        updated_settings = replace(self.settings, input_device_name=device_name)
        if self._save_and_apply_settings(updated_settings):
            # Don't keep the previous mic open; the next recording opens the new one.
            self._close_input_stream()
            self._warm_up_mic_if_always()

    def _build_mic_warm_menu(self):
        warm_menu = rumps.MenuItem(MIC_WARM_MENU_LABEL)
        for seconds, label in MIC_WARM_LABELS.items():
            item = rumps.MenuItem(label, callback=self._set_mic_warm_seconds)
            item.warm_seconds = seconds
            self._mic_warm_items[seconds] = item
            warm_menu[label] = item
        return warm_menu

    def _refresh_mic_warm_menu(self):
        for seconds, item in self._mic_warm_items.items():
            item.state = int(seconds == self.settings.mic_warm_seconds)

    def _set_mic_warm_seconds(self, sender):
        seconds = sender.warm_seconds
        if seconds == self.settings.mic_warm_seconds:
            return

        updated_settings = replace(self.settings, mic_warm_seconds=seconds)
        if self._save_and_apply_settings(updated_settings) and not self.recording:
            # Apply the new window to a mic that is already warm.
            self._schedule_mic_cooldown()
            self._warm_up_mic_if_always()

    # ── Hotkey handler ────────────────────────────────────────────────────────
    def _on_hotkey(self):
        """Called every time the hotkey fires (press = toggle)."""
        if not self._hotkey_enabled:
            rumps.notification(
                "VoiceTyper",
                "Hotkey Unavailable",
                "VoiceTyper is reconnecting the shortcut. Check Accessibility and Input Monitoring permissions if it does not recover.",
            )
            return

        self._toggle_recording()

    def _on_record_menu_item(self, _sender):
        """Menu bar Start/Stop Recording item; works even without hotkey permission."""
        self._toggle_recording()

    def _toggle_recording(self):
        if self._api_key_invalid:
            rumps.notification(
                "VoiceTyper",
                "Setup Required",
                "Stored API key is invalid. Use Set API Key… before recording.",
            )
            return

        if self.client is None:
            rumps.notification(
                "VoiceTyper",
                "Setup Required",
                "Set API Key… from the menu before recording.",
            )
            return

        if not self.recording:
            threading.Thread(target=self._start_recording, daemon=True).start()
        else:
            threading.Thread(target=self._stop_and_transcribe, daemon=True).start()

    def _refresh_client_state(self, notify):
        try:
            api_key = load_api_key()
        except KeychainError as error:
            self.client = None
            self._status_item.title = "Status: API key required"
            rumps.notification("VoiceTyper", "Error", str(error))
            return False

        if not api_key:
            self.client = None
            self._api_key_invalid = False
            self._status_item.title = self._idle_status_title()
            if notify:
                rumps.notification(
                    "VoiceTyper",
                    "Setup Required",
                    "Set API Key… from the menu before recording.",
                )
            return False

        self.client = Groq(
            api_key=api_key,
            timeout=GROQ_REQUEST_TIMEOUT_SECONDS,
        )
        self._api_key_invalid = False
        self._status_item.title = self._idle_status_title()
        if notify:
            rumps.notification("VoiceTyper", "Ready", "API key updated.")
        return True

    def _set_api_key(self, _sender):
        api_key = prompt_for_api_key()
        if not api_key:
            return

        try:
            save_api_key(api_key)
        except KeychainError as error:
            rumps.notification("VoiceTyper", "Error", str(error))
            return

        self._refresh_client_state(notify=True)

    def _start_hotkey_listener(self):
        if self._hotkey_listener is not None:
            return

        listener = keyboard.GlobalHotKeys({
            HOTKEY: self._on_hotkey
        })
        listener.daemon = True
        refresh_keyboard_layout_context()
        listener.start()
        self._hotkey_listener = listener
        print("✅ VoiceTyper hotkey listener started.", flush=True)

    def _refresh_hotkey_permission(self, _sender=None):
        self._hotkey_permission_granted = has_hotkey_permission()
        listener = self._hotkey_listener
        if listener is not None and not listener.is_alive():
            print("⚠️ VoiceTyper hotkey listener exited; reconnecting.", flush=True)
            self._hotkey_listener = None

        if not self._hotkey_permission_granted:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
            self._hotkey_enabled = False
        else:
            try:
                self._start_hotkey_listener()
            except Exception as error:
                print(f"⚠️ Unable to start hotkey listener; will retry: {error}", flush=True)
            listener = self._hotkey_listener
            self._hotkey_enabled = bool(
                listener is not None and listener.is_alive() and listener.running
            )

        # A health check must not replace the recording/transcription display.
        if not self.recording and self._status_item.title != "Status: Transcribing…":
            self._reset_status()
        return self._hotkey_enabled

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

    # ── Recording ─────────────────────────────────────────────────────────────
    def _on_audio(self, indata, frame_count, time_info, status):
        if not self._mic_live.is_set():
            # A Bluetooth mic sends silence and replayed stale audio until its
            # voice link is up; none of that is speech, so don't record it.
            if not self._live_detector.feed(indata):
                return
            self._mic_live.set()
        if self.recording:
            self.frames.append(indata.copy())

    def _open_input_stream(self):
        """Start an input stream, or reuse the warm one if it still fits."""
        device = self._resolve_input_device()
        with self._stream_lock:
            self._cancel_mic_warm_timer()
            stream = self._stream
            if stream is not None and (not stream.active or self._stream_device != device):
                self._close_stream_locked()
            if self._stream is not None:
                return

            self._mic_live.clear()
            self._live_detector = LiveAudioDetector()
            stream_kwargs = {
                "samplerate": SAMPLE_RATE,
                "channels": CHANNELS,
                "dtype": "int16",
                "callback": self._on_audio,
            }
            if device is not None:
                stream_kwargs["device"] = device
            stream = sd.InputStream(**stream_kwargs)
            try:
                stream.start()
            except Exception:
                stream.close()
                raise
            self._stream = stream
            self._stream_device = device

    def _close_stream_locked(self):
        stream, self._stream = self._stream, None
        self._stream_device = None
        self._mic_live.clear()
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception as error:
            print(f"⚠️ Error closing input stream: {error}", flush=True)

    def _close_input_stream(self):
        with self._stream_lock:
            self._cancel_mic_warm_timer()
            if not self.recording:
                self._close_stream_locked()
        self._refresh_idle_status()

    def _cancel_mic_warm_timer(self):
        if self._mic_warm_timer is not None:
            self._mic_warm_timer.cancel()
            self._mic_warm_timer = None

    def _schedule_mic_cooldown(self):
        """Keep the idle stream open for the configured "Keep Mic Ready" window."""
        warm_seconds = self.settings.mic_warm_seconds
        if warm_seconds == 0:
            self._close_input_stream()
            return
        with self._stream_lock:
            self._cancel_mic_warm_timer()
            if self._stream is None or warm_seconds == MIC_WARM_ALWAYS:
                return
            timer = threading.Timer(warm_seconds, self._close_input_stream)
            timer.daemon = True
            self._mic_warm_timer = timer
            timer.start()

    def _warm_up_mic_if_always(self):
        if self.settings.mic_warm_seconds != MIC_WARM_ALWAYS or self.recording:
            return
        threading.Thread(target=self._warm_up_mic, daemon=True).start()

    def _warm_up_mic(self):
        if not request_microphone_permission():
            return
        try:
            self._open_input_stream()
        except Exception as error:
            print(f"⚠️ Unable to keep the mic ready: {error}", flush=True)
            return
        # Bluetooth mics take a few seconds to go live; turn 🟢 once they do.
        self._mic_live.wait(MIC_CONNECT_TIMEOUT_SECONDS)
        self._refresh_idle_status()

    def _start_recording(self):
        self.frames = []
        if not request_microphone_permission():
            self.recording = False
            self._reset_status()
            rumps.notification(
                "VoiceTyper",
                "Permissions Required",
                "Microphone access is required for VoiceTyper.app.",
            )
            return

        try:
            self._open_input_stream()
        except Exception as error:
            self.recording = False
            self._reset_status()
            print(f"❌ Failed to start recording: {error}")
            rumps.notification("VoiceTyper", "Error", f"Failed to start recording: {error}")
            return

        self.recording = True
        self._record_item.title = RECORD_STOP_LABEL
        if not self._mic_live.is_set():
            # Don't show 🔴 until the mic actually delivers audio, or the
            # user starts talking into a mic that is still connecting.
            self.title = "🟡"
            self._status_item.title = "Status: Connecting mic…"
            self._update_record_button(RECORD_BUTTON_CONNECTING_TITLE)
            if not self._mic_live.wait(MIC_CONNECT_TIMEOUT_SECONDS):
                print(
                    f"⚠️ Mic sent only silence for {MIC_CONNECT_TIMEOUT_SECONDS}s; "
                    "recording anyway.",
                    flush=True,
                )
                self._mic_live.set()
            if not self.recording:
                return  # Stopped while the mic was still connecting.

        self.title = "🔴"  # Red dot in menubar while recording
        self._status_item.title = "Status: Recording…"
        self._update_record_button(RECORD_BUTTON_RECORDING_TITLE)

    def _stop_and_transcribe(self):
        self.recording = False
        # The stream keeps running while warm, so take the frames out from
        # under the audio callback.
        frames, self.frames = self.frames, []
        self._schedule_mic_cooldown()

        self.title = "⏳"  # Hourglass while transcribing
        self._status_item.title = "Status: Transcribing…"
        self._record_item.title = RECORD_START_LABEL
        # Disabled so a click cannot start a new recording mid-transcription.
        self._update_record_button(RECORD_BUTTON_BUSY_TITLE, enabled=False)

        if self.client is None:
            self._reset_status()
            return

        if not frames:
            self._reset_status()
            return

        selected_settings = self.settings
        tmp_name = None

        # Send to Whisper
        try:
            # Save recorded audio to a temp WAV file before transcription.
            audio = np.concatenate(frames, axis=0)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_name = tmp.name
            tmp.close()
            with wave.open(tmp_name, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)          # int16 = 2 bytes
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio.tobytes())

            with open(tmp_name, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f,
                    language=selected_settings.context_language,
                    timeout=GROQ_REQUEST_TIMEOUT_SECONDS,
                )
            transcript = result.text.strip()
            if not transcript:
                rumps.notification(
                    "VoiceTyper",
                    "No Speech Detected",
                    "VoiceTyper did not detect spoken text. Try speaking louder or for a little longer.",
                )
                return

            final_text = convert_transcript(
                client=self.client,
                transcript=transcript,
                context_language=selected_settings.context_language,
                output_language=selected_settings.output_language,
            )
            if not final_text:
                rumps.notification(
                    "VoiceTyper",
                    "No Output Produced",
                    "VoiceTyper finished processing but did not generate text.",
                )
                return

            self._type_text(final_text)
        except AuthenticationError:
            self.client = None
            self._api_key_invalid = True
            self._reset_status()
            rumps.notification(
                "VoiceTyper",
                "Invalid API Key",
                "The stored Groq API key was rejected. Use Set API Key… and try again.",
            )
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            rumps.notification("VoiceTyper", "Error", str(e))
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
            self._reset_status()

    # ── Typing ────────────────────────────────────────────────────────────────
    def _type_text(self, text: str):
        """Copy text to clipboard and paste it at the cursor position."""
        pyperclip.copy(text)
        time.sleep(0.15)  # Small pause so the clipboard settles

        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(
                "⚠️ Automatic paste failed after copying text to the clipboard: "
                f"{result.stderr.strip() or result.stdout.strip() or 'unknown error'}"
            )
            rumps.notification(
                "VoiceTyper",
                "Copied to Clipboard",
                "Automatic paste was blocked. Press Cmd+V manually.",
            )
            return

        print(f"✅ Typed: {text}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _idle_status_title(self):
        if not self._hotkey_enabled:
            if not self._hotkey_permission_granted:
                return "Status: Hotkey permission required"
            return "Status: Hotkey reconnecting…"
        if self._api_key_invalid:
            return "Status: API key invalid"
        if self.client is None:
            return "Status: API key required"
        if self._mic_is_warm():
            return "Status: Ready (mic warm)"
        return "Status: Ready"

    def _reset_status(self):
        self.title = "🟢" if self._mic_is_warm() else "🎙️"
        self._status_item.title = self._idle_status_title()
        self._record_item.title = RECORD_START_LABEL
        self._update_record_button(self._idle_record_button_title())

    def _mic_is_warm(self):
        """True while "Keep Mic Ready" holds a live stream: recording starts instantly."""
        stream = self._stream
        return stream is not None and stream.active and self._mic_live.is_set()

    def _idle_record_button_title(self):
        if self._mic_is_warm():
            return RECORD_BUTTON_READY_TITLE
        return RECORD_BUTTON_IDLE_TITLE

    def _refresh_idle_status(self):
        # Leave the display alone mid-recording or mid-transcription.
        if not self.recording and self._status_item.title != "Status: Transcribing…":
            self._reset_status()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    VoiceTyper().run()
