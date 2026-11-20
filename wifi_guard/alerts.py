"""Push notifications through ntfy (https://ntfy.sh)."""

from __future__ import annotations

import logging
import threading
import urllib.request

log = logging.getLogger("wifi_guard.alerts")


class Notifier:
    def __init__(self, server: str, topic: str, dry_run: bool = False):
        self.server = server.rstrip("/")
        self.topic = topic
        self.dry_run = dry_run or not topic

    def send(self, title: str, message: str, priority: str = "high", tags: str = "rotating_light") -> threading.Thread | None:
        """Send without blocking the detector. Returns the sending thread, if any."""
        if self.dry_run:
            log.warning("ALERT (not sent, no ntfy topic or dry run): %s: %s", title, message)
            return None
        thread = threading.Thread(target=self.send_now, args=(title, message, priority, tags), daemon=True)
        thread.start()
        return thread

    def send_now(self, title: str, message: str, priority: str = "high", tags: str = "rotating_light") -> bool:
        request = urllib.request.Request(
            f"{self.server}/{self.topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": tags},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
            log.info("alert sent: %s", title)
            return True
        except OSError as exc:
            log.error("could not send alert %r: %s", title, exc)
            return False
