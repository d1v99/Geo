# WiFi Guard

A home intruder detector that uses your WiFi instead of cameras or motion sensors.

WiFi signals fill your house. When a person moves, their body changes how those signals travel between your router and anything listening. WiFi Guard watches for that change and sends a push notification to your phone.

## Words used here, in plain English

* **Router.** The box from your internet provider that creates your home WiFi.
* **ESP32.** A tiny, cheap computer on a circuit board, about the size of a stick of gum, with WiFi built in. It is powered by a phone charger over USB.
* **Dev board (dev kit).** An ESP32 sold ready to use, with a USB socket already attached. This is the kind to buy.
* **Firmware.** The program that runs on the ESP32. It lives in the `firmware` folder.
* **Flashing (uploading).** Copying the firmware onto the ESP32 through a USB cable.
* **PlatformIO.** A free tool that turns the firmware code into something the ESP32 can run, and flashes it for you. `pio` is its command.
* **Hub.** The main program of this project. It runs on a normal computer, receives readings from the sensors, and decides when to alert you.
* **Python.** The programming language the hub is written in. Most computers can run it; Windows users download it free from python.org.
* **Terminal (command line).** The text window where you type commands such as `python -m wifi_guard run`. On Windows it is called PowerShell or Command Prompt.
* **Ping.** A tiny "are you there?" message. The router answers every one, and the sensor studies each answer.
* **Signal strength (RSSI).** How loud the WiFi is at one spot, the same thing as the bars on your phone. Measured in dBm: -40 is very strong, -80 is weak.
* **Channel reading (CSI).** A much more detailed measurement than signal strength. WiFi is sent as dozens of slightly different radio tones at once, and this records how loud each one arrived. Bodies moving in the room change that pattern, which is what the sensor watches.
* **Probe request.** A short broadcast a phone sends out asking "is there any WiFi here?". Phones do this even when they are not connected to anything, which is how the sensor can hear them.
* **MAC address.** An ID number every WiFi device has. Phones now send a fake, changing one in probe requests, so a phone can be counted but not identified.
* **2.4 GHz and 5 GHz.** The two radio bands WiFi uses. Most routers broadcast both. The ESP32 only understands 2.4 GHz.
* **ntfy.** A free service and phone app (pronounced "notify") that delivers push notifications. The hub sends the alert to ntfy and ntfy makes your phone buzz.
* **Topic.** The name of your private alert channel in ntfy. Your phone subscribes to it and the hub posts to it.
* **Push notification.** A pop-up alert on your phone, like a text message from an app.
* **Dashboard.** A small web page the hub serves, showing what the sensors see, with the arm and disarm button.
* **IP address.** A device's number on your home network, such as 192.168.1.50. The sensor needs the hub computer's one. You can find it in the computer's WiFi settings.
* **127.0.0.1.** A special address meaning "this same computer". A page at that address can only be opened on the computer running the hub.
* **Port.** A numbered door on a computer that a program listens at. The dashboard uses 8080 and the sensors report to 5005.
* **UDP.** A simple way of sending small messages across a network. The sensors use it to report to the hub.
* **Firewall.** Security software on a computer that blocks incoming messages unless you allow them. It may need to be told to let the sensor's messages in.
* **Config file.** A text file of settings. `config.toml` holds the hub's settings and `config.h` holds the sensor's (your WiFi name and password).
* **Armed and disarmed.** Armed means alerts will be sent. Disarmed means the system still watches but stays silent, for when you are home.
* **Calibration.** The first 30 to 60 seconds after starting, when a sensor learns what your house looks like with nobody moving.
* **Threshold.** How big a disturbance has to be before it counts as motion. Higher means fewer false alarms but easier to miss someone.
* **PIN.** A short password you choose, needed to arm or disarm from the dashboard.

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
