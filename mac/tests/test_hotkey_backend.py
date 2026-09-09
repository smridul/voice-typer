"""Exercise the actual macOS backend without posting events or recording audio."""

import sys
import types
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "darwin", "macOS keyboard backend")
class MediaKeyRegressionTests(unittest.TestCase):
    def test_media_keys_do_not_break_control_space(self):
        from pynput import keyboard
        from pynput.keyboard import _darwin as backend

        activated = []
        listener = keyboard.GlobalHotKeys({
            "<ctrl>+<space>": lambda: activated.append(True),
        })
        # 1.8.1 omitted 'injected' for these events, killing GlobalHotKeys.
        for key in (keyboard.Key.media_volume_up, keyboard.Key.media_play_pause):
            for flags in (0x0A00, 0x0B00):
                event = types.SimpleNamespace(
                    subtype=lambda: backend.kSystemDefinedEventMediaKeysSubtype,
                    data1=lambda: (key.value.vk << 16) | flags,
                )
                with self.subTest(key=key, flags=flags):
                    with patch.object(backend, "NSEvent") as ns_event, \
                         patch.object(backend, "CGEventGetFlags", return_value=0), \
                         patch.object(listener, "_event_to_key", return_value=key):
                        ns_event.eventWithCGEvent_.return_value = event
                        listener._handle_message(None, backend.NSSystemDefined, event, None, False)

        # The same listener must still recognize the recording shortcut.
        for key in (keyboard.Key.ctrl, keyboard.Key.space):
            listener.on_press(key, False)
        for key in (keyboard.Key.space, keyboard.Key.ctrl):
            listener.on_release(key, False)
        self.assertEqual(activated, [True])
