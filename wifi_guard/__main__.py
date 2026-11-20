"""Command line entry point: python -m wifi_guard <command>."""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import config as config_module
from . import detector as det
from .alerts import Notifier
from .hub import Hub


def _load(args) -> config_module.Config:
    path = args.config
    if path is None and Path("config.toml").exists():
        path = "config.toml"
    try:
        return config_module.load(path)
    except (OSError, ValueError) as exc:
        sys.exit(f"config error: {exc}")


def cmd_run(args) -> None:
    from . import web
    from .sensors.esp32 import Esp32Listener
    from .sensors.rssi import RssiSensor

    cfg = _load(args)
    notifier = Notifier(cfg.ntfy_server, cfg.ntfy_topic, dry_run=args.dry_run)
    hub = Hub(cfg, notifier)
    if cfg.rssi_enabled:
        RssiSensor(hub.inbox, cfg.rssi_interface, cfg.rssi_interval_s).start()
    if cfg.esp32_enabled:
        Esp32Listener(hub.inbox, cfg.esp32_port).start()
    web.serve(hub, cfg.web_host, cfg.web_port, cfg.web_pin)
    logging.info("dashboard: http://%s:%d", cfg.web_host, cfg.web_port)
    if notifier.dry_run:
        logging.warning("no ntfy topic configured (or dry run): alerts are only logged")
    if args.armed:
        hub.arm()
    try:
        hub.run()
    except KeyboardInterrupt:
        pass


def cmd_test_alert(args) -> None:
    cfg = _load(args)
    if not cfg.ntfy_topic:
        sys.exit("set ntfy_topic in config.toml first")
    ok = Notifier(cfg.ntfy_server, cfg.ntfy_topic).send_now("WiFi Guard test", "Alerts are working.", "default", "white_check_mark")
    sys.exit(0 if ok else 1)


def _post(args, action: str) -> None:
    cfg = _load(args)
    request = urllib.request.Request(
        f"http://127.0.0.1:{cfg.web_port}/api/{action}", method="POST", headers={"X-Pin": cfg.web_pin}
    )
    try:
        urllib.request.urlopen(request, timeout=5).read()
    except (urllib.error.URLError, OSError) as exc:
        sys.exit(f"could not reach the running hub: {exc}")
    print(f"{action}ed")


def cmd_simulate(args) -> None:
    """Feed the detector a fake signal: quiet room, someone walks through, quiet again."""
    rng = random.Random(args.seed)
    detector = det.MotionDetector(config_module.Config().csi_detector)
    print("simulated ESP32 signal at 20 samples per second")
    for i in range(20 * 90):
        t = i / 20
        walking = 50 <= t < 62
        value = 0.30 + rng.gauss(0, 0.004)
        if walking:
            value += 0.06 * math.sin(t * 7) + rng.gauss(0, 0.02)
        event = detector.add(t, value)
        if event:
            print(f"  t={t:5.1f}s  {event:<13} (person walking: {'yes' if walking else 'no'})")
    print("done")


def main() -> None:
    parser = argparse.ArgumentParser(prog="wifi_guard", description="Home intruder detection from WiFi signals.")
    parser.add_argument("-c", "--config", help="path to config.toml (default: ./config.toml if present)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="start the hub")
    run.add_argument("--armed", action="store_true", help="arm on start")
    run.add_argument("--dry-run", action="store_true", help="log alerts instead of sending them")
    run.set_defaults(func=cmd_run)
    sub.add_parser("arm", help="arm a running hub").set_defaults(func=lambda a: _post(a, "arm"))
    sub.add_parser("disarm", help="disarm a running hub").set_defaults(func=lambda a: _post(a, "disarm"))
    sub.add_parser("test-alert", help="send a test push notification").set_defaults(func=cmd_test_alert)
    simulate = sub.add_parser("simulate", help="demo the detector on a fake signal")
    simulate.add_argument("--seed", type=int, default=1)
    simulate.set_defaults(func=cmd_simulate)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
    )
    args.func(args)


if __name__ == "__main__":
    main()
