"""The hub: takes sensor readings, runs the detectors, raises alerts."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from . import detector as det
from .alerts import Notifier
from .config import Config

log = logging.getLogger("wifi_guard.hub")

PROBE_MEMORY_S = 300.0  # how long a heard phone stays on the "nearby" list


@dataclass
class Sample:
    sensor: str  # e.g. "rssi" or "esp32:hallway"
    kind: str  # "rssi" or "csi"
    t: float
    value: float


@dataclass
class Probe:
    sensor: str
    mac: str
    rssi: int
    t: float


class Hub:
    def __init__(self, config: Config, notifier: Notifier, clock=time.time):
        self.cfg = config
        self.notifier = notifier
        self.clock = clock
        self.inbox: queue.Queue = queue.Queue(maxsize=10000)
        self.events: deque[dict] = deque(maxlen=100)
        self._lock = threading.RLock()
        self._detectors: dict[str, det.MotionDetector] = {}
        self._last_seen: dict[str, float] = {}
        self._offline: set[str] = set()
        self._phones: dict[str, dict] = {}
        self._last_alert: dict[str, float] = {}
        self._armed = False
        self._active_from = 0.0
        self._stop = threading.Event()
        self._load_state()

    # arming

    def arm(self, delay_s: float | None = None) -> None:
        with self._lock:
            delay = self.cfg.arm_delay_s if delay_s is None else delay_s
            self._armed = True
            self._active_from = self.clock() + delay
            self._record("armed", f"Armed, active in {int(delay)} s" if delay else "Armed")
            self._save_state()

    def disarm(self) -> None:
        with self._lock:
            self._armed = False
            self._record("disarmed", "Disarmed")
            self._save_state()

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def active(self) -> bool:
        """Armed and past the exit delay, so alerts will be sent."""
        return self._armed and self.clock() >= self._active_from

    # main loop

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self.inbox.get(timeout=1.0)
            except queue.Empty:
                item = None
            if item is not None:
                self.handle(item)
            self.check_sensors()

    def stop(self) -> None:
        self._stop.set()

    def handle(self, item) -> None:
        with self._lock:
            if isinstance(item, Sample):
                self._handle_sample(item)
            elif isinstance(item, Probe):
                self._handle_probe(item)

    def _handle_sample(self, s: Sample) -> None:
        detector = self._detectors.get(s.sensor)
        if detector is None:
            tuning = self.cfg.csi_detector if s.kind == "csi" else self.cfg.rssi_detector
            detector = self._detectors[s.sensor] = det.MotionDetector(tuning)
            self._record("sensor", f"Sensor {s.sensor} connected, calibrating. Keep the area still.")
        self._last_seen[s.sensor] = self.clock()
        if s.sensor in self._offline:
            self._offline.discard(s.sensor)
            self._record("sensor", f"Sensor {s.sensor} is back online")

        event = detector.add(s.t, s.value)
        if event == det.CALIBRATED:
            self._record("sensor", f"Sensor {s.sensor} calibrated and watching")
        elif event == det.MOTION_START:
            self._record("motion", f"Motion detected by {s.sensor}")
            if self.active:
                phones = self.phones_nearby()
                extra = f" {len(phones)} unknown phone(s) heard nearby." if phones else ""
                self._alert(f"motion:{s.sensor}", "Motion detected", f"Movement picked up by sensor {s.sensor}.{extra}")
        elif event == det.MOTION_END:
            self._record("clear", f"Motion ended at {s.sensor}")

    def _handle_probe(self, p: Probe) -> None:
        if p.rssi < self.cfg.probe_min_rssi:
            return
        now = self.clock()
        for mac in [m for m, seen in self._phones.items() if now - seen["last"] > PROBE_MEMORY_S]:
            del self._phones[mac]
        seen = self._phones.get(p.mac)
        if seen is None:
            if len(self._phones) >= 500:
                return
            self._phones[p.mac] = {"first": now, "last": now, "rssi": p.rssi}
            self._record("phone", f"Phone heard nearby ({p.rssi} dBm) by {p.sensor}")
            if self.active and self.cfg.probe_alert_alone:
                self._alert(
                    "phone", "Unknown phone nearby", f"A phone was heard close to sensor {p.sensor} ({p.rssi} dBm).", "default", "iphone"
                )
        else:
            seen["last"] = now
            seen["rssi"] = max(seen["rssi"], p.rssi)

    def phones_nearby(self) -> list[dict]:
        now = self.clock()
        return [dict(seen, mac=mac) for mac, seen in self._phones.items() if now - seen["last"] <= PROBE_MEMORY_S]

    def check_sensors(self) -> None:
        """Flag ESP32 sensors that stopped reporting. A dead sensor is itself suspicious."""
        with self._lock:
            now = self.clock()
            for sensor, seen in self._last_seen.items():
                if not sensor.startswith("esp32:") or sensor in self._offline:
                    continue
                if now - seen > self.cfg.offline_after_s:
                    self._offline.add(sensor)
                    self._record("offline", f"Sensor {sensor} went offline")
                    if self.active:
                        self._alert(
                            f"offline:{sensor}",
                            "Sensor offline",
                            f"Sensor {sensor} stopped reporting. Check power and WiFi.",
                            "high",
                            "warning",
                        )

    # helpers

    def _alert(self, key: str, title: str, message: str, priority: str = "urgent", tags: str = "rotating_light") -> None:
        now = self.clock()
        if now - self._last_alert.get(key, float("-inf")) < self.cfg.cooldown_s:
            return
        self._last_alert[key] = now
        self._record("alert", f"Alert sent: {title}")
        self.notifier.send(title, message, priority, tags)

    def _record(self, kind: str, text: str) -> None:
        self.events.appendleft({"t": self.clock(), "kind": kind, "text": text})
        log.info(text)

    def status(self) -> dict:
        with self._lock:
            now = self.clock()
            return {
                "armed": self._armed,
                "active": self.active,
                "active_in_s": max(0, round(self._active_from - now)) if self._armed else 0,
                "sensors": [
                    {
                        "name": name,
                        "state": "offline" if name in self._offline else d.state,
                        "level": round(d.level, 2),
                        "threshold": d.cfg.threshold,
                    }
                    for name, d in sorted(self._detectors.items())
                ],
                "phones_nearby": len(self.phones_nearby()),
                "events": list(self.events)[:30],
                "alerts_configured": not self.notifier.dry_run,
            }

    def _load_state(self) -> None:
        try:
            state = json.loads(Path(self.cfg.state_file).read_text())
        except (OSError, ValueError):
            return
        # Restart while armed: stay armed, with no fresh exit delay.
        self._armed = bool(state.get("armed"))

    def _save_state(self) -> None:
        try:
            Path(self.cfg.state_file).write_text(json.dumps({"armed": self._armed}))
        except OSError as exc:
            log.error("could not save state: %s", exc)
