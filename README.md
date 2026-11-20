# WiFi Guard

A home intruder detector that uses your WiFi instead of cameras or motion sensors.

WiFi signals fill your house. When a person moves, their body changes how those signals travel between your router and anything listening. WiFi Guard watches for that change and sends a push notification to your phone.

## How it works

```
                 pings, 20 per second
  [ Router ] <-------------------------> [ ESP32 sensor ]
                 WiFi passes through          |
                 the rooms in between         | one number per reply, over your network
                                              v
                                         [ Hub (Python) ] ---> ntfy ---> your phone
```

* **Sensor.** A small ESP32 board (5 to 10 dollars) joins your WiFi and pings the router 20 times a second. For each reply it measures the shape of the radio channel and boils it down to one number. A still room gives a steady number. A moving person makes it jump around.
* **Hub.** A Python program on any always-on computer in the house. It learns what "quiet" looks like, spots movement, and sends the alert. It has a small dashboard to arm and disarm.
* **Phones nearby.** Phones broadcast "any WiFi here?" messages even when they are not connected to anything. The sensor hears those too. This is a bonus clue, not the main alarm: phones hide their identity and go quiet with the screen off, and your neighbours' phones can show up. By default it is only mentioned inside a motion alert.

No ESP32 yet? The hub can also watch the WiFi signal strength of the computer it runs on. That is much less sensitive (it mostly notices someone walking between that computer and the router) but it works today with zero hardware.

## Quick start (no extra hardware)

Needs Python 3.11 or newer. Nothing to install.

```
cp config.example.toml config.toml
python -m wifi_guard simulate      # see the detector work on a fake signal
python -m wifi_guard run           # start the hub
```

Open http://127.0.0.1:8080 for the dashboard. The computer must be on WiFi, not a cable, for the no-hardware mode.

## Phone alerts

1. Install the **ntfy** app (iOS or Android).
2. Invent a long, hard to guess topic name, for example `guard-` followed by random letters. Anyone who knows the name can read your alerts, so treat it like a password.
3. Subscribe to that topic in the app, and put the same name in `config.toml` under `ntfy_topic`.
4. Test it: `python -m wifi_guard test-alert`

## Arming

The hub always watches, but only sends alerts while **armed**. Arm from the dashboard, or with `python -m wifi_guard arm` and `python -m wifi_guard disarm`.

After arming you get 60 seconds to leave (`arm_delay_s`). To arm from your phone, set `host = "0.0.0.0"` and a `pin` under `[web]`, then open `http://<hub computer's IP>:8080` on your home WiFi.

## Adding the ESP32 sensor

Any classic ESP32 dev board works (ESP32-WROOM, "ESP32 DevKit"). Your router must have a 2.4 GHz network, since the ESP32 does not speak 5 GHz.

1. Install [PlatformIO](https://platformio.org/install).
2. In `firmware/esp32_sensor/src`, copy `config.example.h` to `config.h` and fill in your WiFi name, password, and the IP address of the hub computer.
3. Plug in the board and run, from `firmware/esp32_sensor`:
   ```
   pio run -t upload
   pio device monitor
   ```
4. Start the hub. The sensor shows up on the dashboard as `esp32:<name>` and calibrates for 30 seconds. Keep the area still while it does.

**Placement matters most.** Put the sensor so the area you want to guard sits between it and the router, a few metres apart, such as router in the living room and sensor at the far end of the hallway. Keep it away from fans, curtains near open windows, and pets, because all of those move too. You can run several sensors; give each a different `SENSOR_ID`.

If the hub computer has a firewall, allow incoming UDP port 5005.

## Tuning

Watch the level bar on the dashboard while you walk around and while the house is empty. If you get false alarms, raise `threshold` under `[detector.csi]`. If it misses you, lower it. Pets will set it off; this cannot tell a dog from a burglar.

## What to expect

* It is a hobby project, not a certified alarm. Use it alongside locks, not instead of them.
* It detects movement, not stillness. Someone standing motionless is invisible.
* It notices when a sensor goes silent while armed and alerts you, since a cut power line or jammed WiFi looks like that.
* If your internet is down, the push notification cannot reach your phone.

## Tests

```
python -m unittest discover -s tests
```

The tests cover the detector, the parsers, and the full path from a fake ESP32 over UDP through to a fake ntfy server.
