#!/usr/bin/env python3
"""
voice-typer-mac
---------------
Hold Ctrl+Space to record your voice.
Release to transcribe and type the text wherever your cursor is.

Setup:
    1. Add your OpenAI API key to config.py (copy from config.example.py)
    2. Run: pip install -r requirements.txt
    3. Run: python main.py
    4. Allow Accessibility access when macOS prompts you
"""

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
from language_preferences import (
    LANGUAGE_LABELS,
    LanguageSettings,
    load_settings,
    save_settings,
)
from language_processing import convert_transcript

# ── Config ────────────────────────────────────────────────────────────────────
try:
    from config import GROQ_API_KEY
except ImportError:
    raise SystemExit("❌ config.py not found. Copy config.example.py → config.py and add your API key.")

SAMPLE_RATE = 16000   # Hz — Whisper works best at 16kHz
CHANNELS    = 1
HOTKEY      = "<ctrl>+<space>"   # Change this if you prefer a different combo
SETTINGS_PATH = Path(__file__).with_name("settings.json")


# ── App ───────────────────────────────────────────────────────────────────────
class VoiceTyper(rumps.App):
    def __init__(self):
        super().__init__("VoiceTyper", icon=None, quit_button="Quit")
        self.settings = load_settings(SETTINGS_PATH)
        self.title = "🎙️"
        self._status_item = rumps.MenuItem("Status: Ready")
        self._context_language_items = {}
        self._output_language_items = {}
        self.menu = [
            self._status_item,
            None,
            *self._build_language_menu(),
        ]
        self._refresh_language_menu()

        self.client    = Groq(api_key=GROQ_API_KEY)
        self.recording = False
        self.frames    = []
        self._stream   = None

        # Start the global hotkey listener in a background thread
        self._hotkey_listener = keyboard.GlobalHotKeys({
            HOTKEY: self._on_hotkey
        })
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

        print(f"✅ VoiceTyper running. Hold {HOTKEY} to record.")

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
            save_settings(SETTINGS_PATH, updated_settings)
        except OSError as error:
            self._refresh_language_menu()
            print(f"❌ Failed to save settings: {error}")
            rumps.notification("VoiceTyper", "Error", str(error))
            return False

        self.settings = updated_settings
        self._refresh_language_menu()
        return True

    def _set_context_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.context_language:
            return

        updated_settings = LanguageSettings(
            context_language=language_code,
            output_language=self.settings.output_language,
        )
        self._save_and_apply_settings(updated_settings)

    def _set_output_language(self, sender):
        language_code = sender.language_code
        if language_code == self.settings.output_language:
            return

        updated_settings = LanguageSettings(
            context_language=self.settings.context_language,
            output_language=language_code,
        )
        self._save_and_apply_settings(updated_settings)

    # ── Hotkey handler ────────────────────────────────────────────────────────
    def _on_hotkey(self):
        """Called every time the hotkey fires (press = toggle)."""
        if not self.recording:
            threading.Thread(target=self._start_recording, daemon=True).start()
        else:
            threading.Thread(target=self._stop_and_transcribe, daemon=True).start()

    # ── Recording ─────────────────────────────────────────────────────────────
    def _start_recording(self):
        self.recording = True
        self.frames    = []
        self.title     = "🔴"  # Red dot in menubar while recording
        self._status_item.title = "Status: Recording…"

        def callback(indata, frame_count, time_info, status):
            if self.recording:
                self.frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def _stop_and_transcribe(self):
        # Stop the stream
        self.recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self.title = "⏳"  # Hourglass while transcribing
        self._status_item.title = "Status: Transcribing…"

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
                )
            transcript = result.text.strip()
            final_text = convert_transcript(
                client=self.client,
                transcript=transcript,
                context_language=selected_settings.context_language,
                output_language=selected_settings.output_language,
            )
            if final_text:
                self._type_text(final_text)
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
        time.sleep(0.15)             # Small pause so the clipboard settles
        pyautogui.hotkey("command", "v")
        print(f"✅ Typed: {text}")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _reset_status(self):
        self.title = "🎙️"
        self._status_item.title = "Status: Ready"


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    VoiceTyper().run()
