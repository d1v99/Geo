"""Receives readings from ESP32 sensors over UDP on the home network.

Each datagram is one or more text lines:

    C,<sensor id>,<sequence>,<rssi>,<turbulence>   one WiFi channel reading
    P,<sensor id>,<mac>,<rssi>                     a phone heard searching for WiFi
"""

from __future__ import annotations

import logging
import math
import queue
import re
import socket
import threading
import time

from ..hub import Probe, Sample

log = logging.getLogger("wifi_guard.esp32")

_ID = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def parse_line(line: str, now: float):
    """Turn one protocol line into a Sample or Probe. Bad input returns None."""
    parts = line.strip().split(",")
    try:
        if parts[0] == "C" and len(parts) == 5 and _ID.match(parts[1]):
            value = float(parts[4])
            if math.isfinite(value):
                return Sample(f"esp32:{parts[1]}", "csi", now, value)
        elif parts[0] == "P" and len(parts) == 4 and _ID.match(parts[1]):
            mac = parts[2].lower()
            if _MAC.match(mac):
                return Probe(f"esp32:{parts[1]}", mac, int(parts[3]), now)
    except ValueError:
        pass
    return None


class Esp32Listener(threading.Thread):
    def __init__(self, inbox, port: int = 5005, host: str = "0.0.0.0"):
        super().__init__(daemon=True, name="esp32-listener")
        self.inbox = inbox
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.port = self.sock.getsockname()[1]

    def run(self) -> None:
        log.info("listening for ESP32 sensors on UDP port %d", self.port)
        while True:
            try:
                data, _ = self.sock.recvfrom(2048)
            except OSError:
                return
            now = time.time()
            for line in data.decode("ascii", "replace").splitlines():
                item = parse_line(line, now)
                if item is not None:
                    try:
                        self.inbox.put_nowait(item)
                    except queue.Full:
                        pass
