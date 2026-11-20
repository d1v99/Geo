import json
import math
import random
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from wifi_guard import config as config_module
from wifi_guard import detector as det
from wifi_guard import web
from wifi_guard.alerts import Notifier
from wifi_guard.config import Config
from wifi_guard.hub import Hub, Probe, Sample
from wifi_guard.sensors import rssi
from wifi_guard.sensors.esp32 import Esp32Listener, parse_line


def csi_signal(seconds, motion=(), rate=20, seed=1):
    """Fake ESP32 turbulence stream. `motion` is a list of (start, end) seconds."""
    rng = random.Random(seed)
    for i in range(int(seconds * rate)):
        t = i / rate
        value = 0.30 + rng.gauss(0, 0.004)
        if any(a <= t < b for a, b in motion):
            value += 0.06 * math.sin(t * 7) + rng.gauss(0, 0.02)
        yield t, value


def run_detector(detector, signal):
    return [(t, e) for t, v in signal if (e := detector.add(t, v))]


class DetectorTest(unittest.TestCase):
    def test_quiet_room_never_triggers(self):
        for seed in range(8):
            events = run_detector(det.MotionDetector(Config().csi_detector), csi_signal(900, seed=seed))
            self.assertEqual([e for _, e in events], [det.CALIBRATED], f"seed {seed}")

    def test_motion_triggers_quickly_and_clears(self):
        events = run_detector(det.MotionDetector(Config().csi_detector), csi_signal(120, motion=[(60, 70)]))
        self.assertEqual([e for _, e in events], [det.CALIBRATED, det.MOTION_START, det.MOTION_END])
        start, end = events[1][0], events[2][0]
        self.assertLess(start - 60, 4.0)
        self.assertGreater(end, 70)
        self.assertLess(end - 70, 15.0)

    def test_brief_blip_is_ignored(self):
        events = run_detector(det.MotionDetector(Config().csi_detector), csi_signal(120, motion=[(60, 60.3)]))
        self.assertEqual([e for _, e in events], [det.CALIBRATED])

    def test_no_detection_while_calibrating(self):
        events = run_detector(det.MotionDetector(Config().csi_detector), csi_signal(25, motion=[(5, 20)]))
        self.assertEqual(events, [])

    def test_slow_drift_does_not_trigger(self):
        detector = det.MotionDetector(Config().csi_detector)
        signal = ((t, v + t * 0.0001) for t, v in csi_signal(1200))
        self.assertEqual([e for _, e in run_detector(detector, signal)], [det.CALIBRATED])

    def test_rssi_flat_then_wobble(self):
        rng = random.Random(3)
        detector = det.MotionDetector(Config().rssi_detector)
        events = []
        for t in range(600):
            value = -52.0 if rng.random() < 0.9 else -53.0
            if 300 <= t < 330:
                value += rng.choice([-6, -4, -2, 0, 3])
            if event := detector.add(float(t), value):
                events.append((t, event))
        self.assertEqual([e for _, e in events], [det.CALIBRATED, det.MOTION_START, det.MOTION_END])
        self.assertLess(events[1][0] - 300, 15)


class ParserTest(unittest.TestCase):
    def test_proc_wireless(self):
        text = (
            "Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
            " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
            "wlp3s0: 0000   54.  -56.  -256        0      0      0      0     12        0\n"
        )
        self.assertEqual(rssi.parse_proc_wireless(text), -56.0)
        self.assertEqual(rssi.parse_proc_wireless(text, "wlp3s0"), -56.0)
        self.assertIsNone(rssi.parse_proc_wireless(text, "wlan9"))

    def test_other_platforms(self):
        self.assertEqual(rssi.parse_iw_link("Connected to aa:bb\n\tsignal: -47 dBm\n"), -47.0)
        self.assertEqual(rssi.parse_netsh("    State   : connected\n    Signal  : 86%\n"), 86.0)
        self.assertEqual(rssi.parse_airport("     agrCtlRSSI: -55\n     agrCtlNoise: -92\n"), -55.0)
        self.assertEqual(rssi.parse_system_profiler("  Signal / Noise: -61 dBm / -93 dBm\n"), -61.0)
        self.assertIsNone(rssi.parse_netsh("There is no wireless interface on the system."))

    def test_esp32_lines(self):
        sample = parse_line("C,hallway,17,-48,0.31250\n", 5.0)
        self.assertEqual(sample, Sample("esp32:hallway", "csi", 5.0, 0.3125))
        probe = parse_line("P,hallway,AA:bb:cc:dd:ee:ff,-51", 5.0)
        self.assertEqual(probe, Probe("esp32:hallway", "aa:bb:cc:dd:ee:ff", -51, 5.0))
        for bad in ["", "C,hallway,1,-48", "C,bad id!,1,-48,0.3", "C,x,1,-48,nan", "C,x,1,-48,abc", "P,x,nope,-50", "Z,1,2,3"]:
            self.assertIsNone(parse_line(bad, 5.0), bad)


class FakeNotifier:
    dry_run = False

    def __init__(self):
        self.sent = []

    def send(self, title, message, priority="high", tags=""):
        self.sent.append((title, message))


class HubTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 0.0
        self.cfg = Config(state_file=str(Path(self.tmp.name) / "state.json"))
        self.notifier = FakeNotifier()
        self.hub = Hub(self.cfg, self.notifier, clock=lambda: self.now)

    def feed(self, signal, sensor="esp32:hall", offset=0.0):
        for t, value in signal:
            self.now = t + offset
            self.hub.handle(Sample(sensor, "csi", self.now, value))

    def test_disarmed_records_but_does_not_alert(self):
        self.feed(csi_signal(100, motion=[(60, 70)]))
        self.assertEqual(self.notifier.sent, [])
        self.assertIn("motion", [e["kind"] for e in self.hub.events])

    def test_armed_alerts_once_per_cooldown(self):
        self.hub.arm(delay_s=0)
        self.feed(csi_signal(140, motion=[(60, 70), (90, 100)]))
        self.assertEqual([title for title, _ in self.notifier.sent], ["Motion detected"])
        self.feed(csi_signal(100, motion=[(60, 70)], seed=2), offset=200)
        self.assertEqual(len(self.notifier.sent), 2)

    def test_exit_delay_suppresses_alert(self):
        self.feed(csi_signal(50))
        self.hub.arm(delay_s=60)
        self.feed(((t + 50, v) for t, v in csi_signal(40, motion=[(5, 15)], seed=4)))
        self.assertEqual(self.notifier.sent, [])
        self.assertTrue(self.hub.armed)
        self.assertFalse(self.hub.active)
        self.now = 111
        self.assertTrue(self.hub.active)

    def test_phones_are_mentioned_in_motion_alert(self):
        self.hub.arm(delay_s=0)
        self.feed(csi_signal(55))
        self.hub.handle(Probe("esp32:hall", "aa:aa:aa:aa:aa:aa", -45, self.now))
        self.hub.handle(Probe("esp32:hall", "bb:bb:bb:bb:bb:bb", -90, self.now))  # too weak, ignored
        self.assertEqual(self.notifier.sent, [])
        self.feed(((t + 55, v) for t, v in csi_signal(20, motion=[(2, 12)], seed=5)))
        self.assertEqual(len(self.notifier.sent), 1)
        self.assertIn("1 unknown phone(s)", self.notifier.sent[0][1])

    def test_phone_alone_alert_is_opt_in(self):
        self.cfg.probe_alert_alone = True
        self.hub.arm(delay_s=0)
        self.hub.handle(Probe("esp32:hall", "aa:aa:aa:aa:aa:aa", -45, 0))
        self.hub.handle(Probe("esp32:hall", "aa:aa:aa:aa:aa:aa", -44, 0))
        self.assertEqual([title for title, _ in self.notifier.sent], ["Unknown phone nearby"])

    def test_offline_sensor_alerts_and_recovers(self):
        self.hub.arm(delay_s=0)
        self.feed(csi_signal(40))
        self.now += 31
        self.hub.check_sensors()
        self.hub.check_sensors()
        self.assertEqual([title for title, _ in self.notifier.sent], ["Sensor offline"])
        self.assertEqual(self.hub.status()["sensors"][0]["state"], "offline")
        self.hub.handle(Sample("esp32:hall", "csi", self.now, 0.3))
        self.assertNotEqual(self.hub.status()["sensors"][0]["state"], "offline")

    def test_armed_state_survives_restart(self):
        self.hub.arm(delay_s=0)
        self.assertTrue(Hub(self.cfg, self.notifier, clock=lambda: self.now).armed)
        self.hub.disarm()
        self.assertFalse(Hub(self.cfg, self.notifier, clock=lambda: self.now).armed)


class EndToEndTest(unittest.TestCase):
    """Fake ESP32 over real UDP, through the hub, to a fake ntfy server over real HTTP."""

    def test_udp_to_push_notification(self):
        received = []

        class Ntfy(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode()
                received.append((self.path, self.headers["Title"], self.headers["Priority"], body))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        ntfy = HTTPServer(("127.0.0.1", 0), Ntfy)
        threading.Thread(target=ntfy.serve_forever, daemon=True).start()
        self.addCleanup(ntfy.server_close)
        self.addCleanup(ntfy.shutdown)

        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = Config(state_file=str(Path(tmp.name) / "state.json"))
        # Shrink the timings so the test takes a few seconds of real time.
        cfg.csi_detector = det.DetectorConfig(window_s=0.3, calibrate_s=1.5, threshold=4.0, trigger_s=0.2, clear_s=1.0)
        hub = Hub(cfg, Notifier(f"http://127.0.0.1:{ntfy.server_port}", "my-topic"))
        listener = Esp32Listener(hub.inbox, port=0, host="127.0.0.1")
        self.addCleanup(listener.sock.close)
        listener.start()
        threading.Thread(target=hub.run, daemon=True).start()
        self.addCleanup(hub.stop)
        hub.arm(delay_s=0)

        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sender.close)
        for i, (t, value) in enumerate(csi_signal(4.5, motion=[(3.0, 4.5)], rate=50)):
            sender.sendto(f"C,hall,{i},-50,{value:.5f}\n".encode(), ("127.0.0.1", listener.port))
            time.sleep(1 / 50)

        deadline = time.time() + 5
        while not received and time.time() < deadline:
            time.sleep(0.05)
        self.assertEqual(len(received), 1)
        path, title, priority, body = received[0]
        self.assertEqual((path, title, priority), ("/my-topic", "Motion detected", "urgent"))
        self.assertIn("esp32:hall", body)


class WebTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.hub = Hub(Config(state_file=str(Path(tmp.name) / "state.json")), FakeNotifier())
        server = web.serve(self.hub, "127.0.0.1", 0, pin="1234")
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.base = f"http://127.0.0.1:{server.server_port}"

    def post(self, path, pin=None):
        request = urllib.request.Request(self.base + path, method="POST", headers={"X-Pin": pin} if pin else {})
        try:
            return urllib.request.urlopen(request, timeout=5).status
        except urllib.error.HTTPError as exc:
            return exc.code

    def test_status_and_pin(self):
        status = json.load(urllib.request.urlopen(self.base + "/api/status", timeout=5))
        self.assertFalse(status["armed"])
        self.assertIn("WiFi Guard", urllib.request.urlopen(self.base + "/", timeout=5).read().decode())
        self.assertEqual(self.post("/api/arm"), 403)
        self.assertEqual(self.post("/api/arm", "0000"), 403)
        self.assertFalse(self.hub.armed)
        self.assertEqual(self.post("/api/arm", "1234"), 200)
        self.assertTrue(self.hub.armed)
        self.assertEqual(self.post("/api/disarm", "1234"), 200)
        self.assertFalse(self.hub.armed)


class ConfigTest(unittest.TestCase):
    def load(self, text):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(text)
            return config_module.load(path)

    def test_example_file_loads_as_defaults(self):
        example = Path(__file__).parent.parent / "config.example.toml"
        self.assertEqual(config_module.load(example), Config())

    def test_overrides_and_validation(self):
        cfg = self.load('[alerts]\nntfy_topic = "abc"\n[detector.csi]\nthreshold = 6\n[sensors.esp32]\nport = 6000\n')
        self.assertEqual((cfg.ntfy_topic, cfg.csi_detector.threshold, cfg.esp32_port), ("abc", 6.0, 6000))
        with self.assertRaises(ValueError):
            self.load("[alerts]\nntfy_topik = 1\n")
        with self.assertRaises(ValueError):
            self.load('[web]\nhost = "0.0.0.0"\n')
        self.assertEqual(self.load('[web]\nhost = "0.0.0.0"\npin = "42"\n').web_host, "0.0.0.0")


if __name__ == "__main__":
    unittest.main()
