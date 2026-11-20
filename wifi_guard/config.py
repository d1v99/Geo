"""Configuration loading. Every setting has a default, so the file is optional."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .detector import DetectorConfig


@dataclass
class Config:
    # alerts
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    cooldown_s: float = 60.0
    arm_delay_s: float = 60.0
    # web dashboard
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    web_pin: str = ""
    # sensors
    rssi_enabled: bool = True
    rssi_interface: str = ""
    rssi_interval_s: float = 1.0
    esp32_enabled: bool = True
    esp32_port: int = 5005
    offline_after_s: float = 30.0
    # phones heard nearby
    probe_min_rssi: int = -60
    probe_alert_alone: bool = False
    # detectors, one tuning per sensor type
    rssi_detector: DetectorConfig = field(
        default_factory=lambda: DetectorConfig(
            window_s=6.0, calibrate_s=60.0, threshold=3.0, floor=0.5, rel_floor=0.25, trigger_s=3.0, clear_s=20.0
        )
    )
    csi_detector: DetectorConfig = field(
        default_factory=lambda: DetectorConfig(
            window_s=1.0, calibrate_s=30.0, threshold=4.0, floor=0.0, rel_floor=0.1, trigger_s=1.0, clear_s=10.0
        )
    )
    state_file: str = "state.json"


def _apply(target, values: dict, prefix: str = "") -> None:
    known = {f.name for f in fields(target)}
    for key, value in values.items():
        name = prefix + key
        if name not in known:
            raise ValueError(f"unknown setting: {name}")
        current = getattr(target, name)
        if isinstance(current, bool) != isinstance(value, bool):
            raise ValueError(f"setting {name} has the wrong type")
        setattr(target, name, type(current)(value))


def load(path: str | Path | None) -> Config:
    cfg = Config()
    if path is None:
        return cfg
    data = tomllib.loads(Path(path).read_text())
    _apply(cfg, data.get("alerts", {}))
    _apply(cfg, data.get("web", {}), "web_")
    sensors = data.get("sensors", {})
    _apply(cfg, sensors.get("rssi", {}), "rssi_")
    esp32 = dict(sensors.get("esp32", {}))
    if "offline_after_s" in esp32:
        cfg.offline_after_s = float(esp32.pop("offline_after_s"))
    _apply(cfg, esp32, "esp32_")
    _apply(cfg, data.get("probes", {}), "probe_")
    detectors = data.get("detector", {})
    _apply(cfg.rssi_detector, detectors.get("rssi", {}))
    _apply(cfg.csi_detector, detectors.get("csi", {}))
    if cfg.web_host not in ("127.0.0.1", "localhost", "::1") and not cfg.web_pin:
        raise ValueError("set [web] pin before exposing the dashboard beyond this computer")
    return cfg
