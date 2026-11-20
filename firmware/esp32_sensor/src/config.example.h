/* Copy this file to config.h and fill it in. config.h is not committed. */
#pragma once

#define WIFI_SSID "your-wifi-name" /* must be the 2.4 GHz network */
#define WIFI_PASSWORD "your-wifi-password"

#define HUB_IP "192.168.1.50" /* the computer running the hub */
#define HUB_PORT 5005

#define SENSOR_ID "hallway" /* letters, digits, dash, underscore; unique per sensor */

#define SAMPLE_RATE_HZ 20   /* channel readings per second */
#define PROBE_MIN_RSSI (-75) /* ignore phones weaker than this; the hub filters further */
