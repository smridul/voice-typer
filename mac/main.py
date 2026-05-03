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

import threading
import tempfile
import wave
import time
import os
import subprocess
import sys
import ctypes
from pathlib import Path

import rumps
import sounddevice as sd
import numpy as np
import pyperclip
from pynput import keyboard
from groq import AuthenticationError, Groq
from app_settings import (
    LANGUAGE_LABELS,
    AppSettings,
    load_settings,
    save_settings,
)
from language_processing import convert_transcript
from app_paths import migrate_legacy_settings_if_needed
from keychain import KeychainError, load_api_key, save_api_key

SAMPLE_RATE = 16000   # Hz — Whisper works best at 16kHz
CHANNELS    = 1
HOTKEY      = "<ctrl>+<space>"   # Change this if you prefer a different combo
MIC_PERMISSION_HELPER = "VoiceTyperMicPermission"
GROQ_REQUEST_TIMEOUT_SECONDS = 30.0
SYSTEM_DEFAULT_MIC_LABEL = "System Default"
REFRESH_MIC_DEVICES_LABEL = "Refresh devices"


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
        self._set_api_key_item = rumps.MenuItem(
            "Set API Key…",
            callback=self._set_api_key,
        )
        self._microphone_menu = None
        self._microphone_items = {}
        self._context_language_items = {}
        self._output_language_items = {}
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

        self.client    = None
        self._api_key_invalid = False
        self.recording = False
        self.frames    = []
        self._stream   = None
        self._hotkey_listener = None
        self._hotkey_enabled = False
        self._hotkey_permission_timer = rumps.Timer(self._refresh_hotkey_permission, 2)
        self._refresh_client_state(notify=False)

        if not self._refresh_hotkey_permission():
            prompt_for_hotkey_permission()
            self._hotkey_permission_timer.start()
            self._status_item.title = "Status: Hotkey permission required"
            rumps.notification(
                "VoiceTyper",
                "Permissions Required",
                "Grant Accessibility and Input Monitoring to VoiceTyper.app. VoiceTyper will start listening automatically once permission is available.",
            )
            print("❌ VoiceTyper hotkey listener not started: waiting for Accessibility/Input Monitoring permission.")

        print(f"✅ VoiceTyper running. Hold {HOTKEY} to record.")

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
        return True

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

    # ── Hotkey handler ────────────────────────────────────────────────────────
    def _on_hotkey(self):
        """Called every time the hotkey fires (press = toggle)."""
        if not self._hotkey_enabled:
            rumps.notification(
                "VoiceTyper",
                "Permissions Required",
                "Grant Accessibility and Input Monitoring to VoiceTyper.app, then restart it.",
            )
            return

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

        self._hotkey_listener = keyboard.GlobalHotKeys({
            HOTKEY: self._on_hotkey
        })
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
        print("✅ VoiceTyper hotkey listener started.")

    def _refresh_hotkey_permission(self, _sender=None):
        if self._hotkey_listener is not None:
            self._hotkey_enabled = True
            if self._hotkey_permission_timer is not None:
                self._hotkey_permission_timer.stop()
            return True

        self._hotkey_enabled = has_hotkey_permission()
        if not self._hotkey_enabled:
            self._status_item.title = self._idle_status_title()
            return False

        self._start_hotkey_listener()
        self._reset_status()
        if self._hotkey_permission_timer is not None:
            self._hotkey_permission_timer.stop()
        return True

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
    def _start_recording(self):
        self.frames = []
        if not request_microphone_permission():
            self.recording = False
            self._stream = None
            self._reset_status()
            rumps.notification(
                "VoiceTyper",
                "Permissions Required",
                "Microphone access is required for VoiceTyper.app.",
            )
            return

        def callback(indata, frame_count, time_info, status):
            if self.recording:
                self.frames.append(indata.copy())

        try:
            stream_kwargs = {
                "samplerate": SAMPLE_RATE,
                "channels": CHANNELS,
                "dtype": "int16",
                "callback": callback,
            }
            input_device = self._resolve_input_device()
            if input_device is not None:
                stream_kwargs["device"] = input_device

            self._stream = sd.InputStream(**stream_kwargs)
            self.recording = True
            self.title = "🔴"  # Red dot in menubar while recording
            self._status_item.title = "Status: Recording…"
            self._stream.start()
        except Exception as error:
            self.recording = False
            self._stream = None
            self._reset_status()
            print(f"❌ Failed to start recording: {error}")
            rumps.notification("VoiceTyper", "Error", f"Failed to start recording: {error}")

    def _stop_and_transcribe(self):
        # Stop the stream
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self.title = "⏳"  # Hourglass while transcribing
        self._status_item.title = "Status: Transcribing…"

        if self.client is None:
            self._reset_status()
            return

        if not self.frames:
            self._reset_status()
            return

        selected_settings = self.settings
        tmp_name = None

        # Send to Whisper
        try:
            # Save recorded audio to a temp WAV file before transcription.
            audio = np.concatenate(self.frames, axis=0)
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
            return "Status: Hotkey permission required"
        if self._api_key_invalid:
            return "Status: API key invalid"
        if self.client is None:
            return "Status: API key required"
        return "Status: Ready"

    def _reset_status(self):
        self.title = "🎙️"
        self._status_item.title = self._idle_status_title()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    VoiceTyper().run()
