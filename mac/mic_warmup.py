"""Tell when a freshly opened input stream is carrying real microphone audio.

A Bluetooth mic in the hands-free profile (measured on a DJI Mic 2) takes
~3.5 s to start sending audio after the stream opens. Meanwhile CoreAudio
delivers exact zeros and then, sometimes, a ~0.3 s chunk of stale audio
replayed over and over, where each block contains a run of ~30 exact zeros.
Neither is speech, so recording must not start on it. Captures of both are in
tests/fixtures/dji_cold_start_*.npy.
"""

import numpy as np

# Real audio at 16 kHz had zero runs of at most 5 samples; every block of the
# replay, including its first pass, has one of 30.
MAX_REAL_ZERO_RUN = 20
# Consecutive real-looking blocks required, so a stray block can't trigger it.
REQUIRED_REAL_BLOCKS = 3


def _longest_zero_run(samples):
    padded = np.concatenate(([0], (samples == 0).astype(np.int8), [0]))
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    if not len(starts):
        return 0
    ends = np.flatnonzero(edges == -1)
    return int((ends - starts).max())


class LiveAudioDetector:
    """Feed blocks in order; `feed` returns True from the first live block on."""

    def __init__(self):
        self._real_streak = 0
        self.live = False

    def feed(self, block):
        if self.live:
            return True

        samples = np.asarray(block).reshape(-1)
        is_real = samples.any() and _longest_zero_run(samples) < MAX_REAL_ZERO_RUN
        self._real_streak = self._real_streak + 1 if is_real else 0
        self.live = self._real_streak >= REQUIRED_REAL_BLOCKS
        return self.live
