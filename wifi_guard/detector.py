"""Motion detection from a stream of scalar signal samples.

The same detector handles both sensor types:

* RSSI: one signal strength reading per second from the hub's own WiFi card.
* CSI: 20+ readings per second from an ESP32, each one a "turbulence" number
  describing the shape of the WiFi channel for a single packet.

In both cases a still room gives a steady value and a moving body makes it
jitter. So the score is the standard deviation of the signal over a short
sliding window, compared against a baseline learned while the room is quiet.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import median, pstdev

CALIBRATING = "calibrating"
QUIET = "quiet"
MOTION = "motion"

MOTION_START = "motion_start"
MOTION_END = "motion_end"
CALIBRATED = "calibrated"


@dataclass
class DetectorConfig:
    window_s: float = 2.0  # sliding window the jitter is measured over
    calibrate_s: float = 30.0  # quiet time needed before detection starts
    baseline_s: float = 600.0  # how far back the quiet baseline remembers
    threshold: float = 4.0  # jitter level (in baseline spreads) that counts as motion
    floor: float = 0.0  # smallest absolute spread, guards against a perfectly flat baseline
    rel_floor: float = 0.1  # smallest spread as a fraction of the baseline median
    trigger_s: float = 1.0  # movement must last this long to raise motion
    clear_s: float = 10.0  # jitter must stay low this long to end motion


class MotionDetector:
    def __init__(self, config: DetectorConfig | None = None):
        self.cfg = config or DetectorConfig()
        self.state = CALIBRATING
        self.level = 0.0  # latest jitter level, in baseline spreads
        self.score = 0.0  # latest raw jitter (std dev over the window)
        self._window: deque[tuple[float, float]] = deque()
        self._baseline: deque[tuple[float, float]] = deque()
        self._median = 0.0
        self._spread = 1.0
        self._first_t: float | None = None
        self._last_baseline_t = float("-inf")
        self._over_since: float | None = None
        self._under_since: float | None = None

    def add(self, t: float, value: float) -> str | None:
        """Feed one sample. Returns an event name when the state changes."""
        cfg = self.cfg
        if self._window and t < self._window[-1][0]:
            # Clock went backwards (restart or clock change): start the window over.
            self._window.clear()
        self._window.append((t, value))
        while self._window and t - self._window[0][0] > cfg.window_s:
            self._window.popleft()
        if len(self._window) < 3 or t - self._window[0][0] < 0.5 * cfg.window_s:
            return None

        self.score = pstdev(v for _, v in self._window)
        if self._first_t is None:
            self._first_t = t

        if self.state == CALIBRATING:
            self._remember(t)
            if t - self._first_t >= cfg.calibrate_s and len(self._baseline) >= 5:
                self.state = QUIET
                return CALIBRATED
            return None

        self.level = (self.score - self._median) / self._spread

        if self.state == QUIET:
            if self.level > cfg.threshold:
                if self._over_since is None:
                    self._over_since = t
                # One short blip stays inside the window for window_s, so the level
                # has to stay high for longer than that to prove ongoing movement.
                if t - self._over_since >= cfg.window_s + cfg.trigger_s:
                    self.state = MOTION
                    self._over_since = None
                    self._under_since = None
                    return MOTION_START
            else:
                self._over_since = None
                if self.level < cfg.threshold / 2:
                    self._remember(t)
            return None

        # MOTION
        if self.level < cfg.threshold / 2:
            if self._under_since is None:
                self._under_since = t
            if t - self._under_since >= cfg.clear_s:
                self.state = QUIET
                self._under_since = None
                return MOTION_END
        else:
            self._under_since = None
        return None

    def _remember(self, t: float) -> None:
        """Add the current score to the quiet baseline, at most twice per window."""
        cfg = self.cfg
        if t - self._last_baseline_t < cfg.window_s / 2:
            return
        self._last_baseline_t = t
        self._baseline.append((t, self.score))
        while len(self._baseline) > 5 and t - self._baseline[0][0] > cfg.baseline_s:
            self._baseline.popleft()
        scores = [s for _, s in self._baseline]
        self._median = median(scores)
        mad = median(abs(s - self._median) for s in scores)
        self._spread = max(1.4826 * mad, cfg.floor, cfg.rel_floor * self._median, 1e-9)
