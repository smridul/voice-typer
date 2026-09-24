import unittest
from pathlib import Path

import numpy as np

from mic_warmup import LiveAudioDetector

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BLOCK_SECONDS = 320 / 16000


def first_live_block(blocks):
    detector = LiveAudioDetector()
    for index, block in enumerate(blocks):
        if detector.feed(block):
            return index
    return None


class RecordedColdStartTests(unittest.TestCase):
    """Real captures of the DJI Mic 2 over Bluetooth, opened from cold.

    Each is 300 blocks of 320 int16 samples (6 s). Real audio begins at block
    188 and 170: before that the stream is exact zeros, then a ~0.3 s chunk of
    stale audio replayed over and over, each block holding a 30-sample run of
    zeros. The first version of the fix treated that replay as a live mic.
    """

    def assert_live_at_real_audio(self, name, real_audio_block):
        blocks = np.load(FIXTURES / name)
        live = first_live_block(blocks)
        self.assertIsNotNone(live)
        # Never before real audio, and at most ~0.1 s after it starts.
        self.assertGreaterEqual(live, real_audio_block)
        self.assertLessEqual((live - real_audio_block) * BLOCK_SECONDS, 0.1)

    def test_first_capture(self):
        self.assert_live_at_real_audio("dji_cold_start_1.npy", 188)

    def test_second_capture(self):
        self.assert_live_at_real_audio("dji_cold_start_2.npy", 170)


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(0)

    def noise(self, n=320, level=80):
        return self.rng.normal(0, level, n).astype(np.int16)

    def test_silence_is_not_live(self):
        self.assertIsNone(first_live_block([np.zeros(320, np.int16)] * 50))

    def test_ordinary_mic_goes_live_within_a_few_blocks(self):
        self.assertLessEqual(first_live_block([self.noise() for _ in range(10)]), 2)

    def test_long_zero_run_blocks_are_not_live(self):
        blocks = []
        for _ in range(20):
            block = self.noise()
            block[100:130] = 0
            blocks.append(block)
        self.assertIsNone(first_live_block(blocks))

    def test_needs_consecutive_real_blocks(self):
        gap = self.noise()
        gap[:40] = 0
        blocks = [self.noise(), self.noise(), gap, self.noise(), self.noise(), self.noise()]
        self.assertEqual(first_live_block(blocks), 5)

    def test_accepts_column_shaped_blocks_from_sounddevice(self):
        blocks = [self.noise().reshape(-1, 1) for _ in range(5)]
        self.assertIsNotNone(first_live_block(blocks))


if __name__ == "__main__":
    unittest.main()
