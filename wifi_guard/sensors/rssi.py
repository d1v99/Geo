"""No-hardware sensor: the hub computer's own WiFi signal strength.

A person walking between this computer and the router makes the reading
wobble. It is coarse (whole dB, about once a second) so treat it as a starter
mode; the ESP32 sensor is far more sensitive.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import threading
import time
from pathlib import Path

from ..hub import Sample

log = logging.getLogger("wifi_guard.rssi")

AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"


def parse_proc_wireless(text: str, interface: str = "") -> float | None:
    """Linux /proc/net/wireless: 'wlan0: 0000   54.  -56.  -256 ...' gives -56."""
    for line in text.splitlines()[2:]:
        name, _, rest = line.partition(":")
        parts = rest.split()
        if len(parts) < 3 or (interface and name.strip() != interface):
            continue
        try:
            return float(parts[2].rstrip("."))
        except ValueError:
            continue
    return None


def parse_iw_link(text: str) -> float | None:
    """Linux 'iw dev wlan0 link': 'signal: -52 dBm'."""
    match = re.search(r"signal:\s*(-?\d+)", text)
    return float(match.group(1)) if match else None


def parse_netsh(text: str) -> float | None:
    """Windows 'netsh wlan show interfaces': 'Signal : 86%'. Returned as percent."""
    match = re.search(r"^\s*Signal\s*:\s*(\d+)\s*%", text, re.MULTILINE)
    return float(match.group(1)) if match else None


def parse_airport(text: str) -> float | None:
    """macOS 'airport -I': 'agrCtlRSSI: -55'."""
    match = re.search(r"agrCtlRSSI:\s*(-?\d+)", text)
    return float(match.group(1)) if match else None


def parse_system_profiler(text: str) -> float | None:
    """macOS 'system_profiler SPAirPortDataType': 'Signal / Noise: -55 dBm / -92 dBm'."""
    match = re.search(r"Signal / Noise:\s*(-?\d+)\s*dBm", text)
    return float(match.group(1)) if match else None


def _run(*command: str) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def read_rssi(interface: str = "") -> float | None:
    """Current WiFi signal of this computer, or None when it cannot be read."""
    system = platform.system()
    if system == "Linux":
        try:
            value = parse_proc_wireless(Path("/proc/net/wireless").read_text(), interface)
        except OSError:
            value = None
        if value is None and interface:
            value = parse_iw_link(_run("iw", "dev", interface, "link"))
        return value
    if system == "Windows":
        return parse_netsh(_run("netsh", "wlan", "show", "interfaces"))
    if system == "Darwin":
        value = parse_airport(_run(AIRPORT, "-I")) if Path(AIRPORT).exists() else None
        if value is None:
            value = parse_system_profiler(_run("system_profiler", "SPAirPortDataType"))
        return value
    return None


class RssiSensor(threading.Thread):
    def __init__(self, inbox, interface: str = "", interval_s: float = 1.0):
        super().__init__(daemon=True, name="rssi-sensor")
        self.inbox = inbox
        self.interface = interface
        self.interval_s = interval_s

    def run(self) -> None:
        if read_rssi(self.interface) is None:
            log.warning("no WiFi signal reading on this computer (wired, or WiFi off); RSSI sensor disabled")
            return
        log.info("RSSI sensor running on this computer's WiFi")
        while True:
            started = time.time()
            value = read_rssi(self.interface)
            if value is not None:
                self.inbox.put(Sample("rssi", "rssi", started, value))
            time.sleep(max(0.0, self.interval_s - (time.time() - started)))
