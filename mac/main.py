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

import rumps
import sounddevice as sd
import numpy as np
import pyperclip
import pyautogui
from pynput import keyboard
from groq import Groq

# ── Config ────────────────────────────────────────────────────────────────────
try:
    from config import GROQ_API_KEY
except ImportError:
    raise SystemExit("❌ config.py not found. Copy config.example.py → config.py and add your API key.")

SAMPLE_RATE = 16000   # Hz — Whisper works best at 16kHz
CHANNELS    = 1
HOTKEY      = "<ctrl>+<space>"   # Change this if you prefer a different combo


# ── App ───────────────────────────────────────────────────────────────────────
class VoiceTyper(rumps.App):
    def __init__(self):
        super().__init__("VoiceTyper", icon=None, quit_button="Quit")
        self.title = "🎙️"
        self._status_item = rumps.MenuItem("Status: Ready")
        self.menu = [self._status_item, None]  # None adds a separator

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

        # Save recorded audio to a temp WAV file
        audio = np.concatenate(self.frames, axis=0)
        tmp   = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)          # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        # Send to Whisper
        try:
            with open(tmp.name, "rb") as f:
                result = self.client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f,
                    language="en",      # Remove this line if you speak other languages
                )
            text = result.text.strip()
            if text:
                self._type_text(text)
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            rumps.notification("VoiceTyper", "Error", str(e))
        finally:
            os.unlink(tmp.name)
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
