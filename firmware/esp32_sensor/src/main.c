/*
 * WiFi Guard sensor for ESP32.
 *
 * Joins the home WiFi, pings the router many times a second, and for every
 * reply reads the channel state information (CSI): how strongly each of the
 * WiFi subcarriers arrived. A body moving through the room changes that shape.
 * Each reading is boiled down to one "turbulence" number and sent to the hub.
 *
 * It also listens for probe requests, the "any WiFi here?" broadcasts phones
 * make even when they are not connected to anything, and reports strong ones.
 */

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "nvs_flash.h"
#include "ping/ping_sock.h"

#include "config.h"

static const char *TAG = "wifi_guard";

typedef enum { MSG_CSI, MSG_PROBE } msg_type_t;

typedef struct {
    msg_type_t type;
    int8_t rssi;
    float turbulence;
    uint8_t mac[6];
} msg_t;

static QueueHandle_t s_queue;
static uint8_t s_bssid[6];
static volatile bool s_connected;
static esp_ping_handle_t s_ping;

/* Recently reported phones, so one chatty phone cannot flood the hub. */
#define PROBE_SLOTS 16
static struct {
    uint8_t mac[6];
    TickType_t sent;
} s_probes[PROBE_SLOTS];
static int s_probe_next;

static void csi_cb(void *ctx, wifi_csi_info_t *info)
{
    /* Only packets from our own router, and only the plain 64 subcarrier form,
       so every reading is comparable with the last. */
    if (!s_connected || !info || !info->buf || info->len != 128) return;
    if (memcmp(info->mac, s_bssid, 6) != 0) return;

    float sum = 0, sum_sq = 0;
    int used = 0;
    for (int i = info->first_word_invalid ? 2 : 0; i < 64; i++) {
        float im = info->buf[2 * i], re = info->buf[2 * i + 1];
        if (im == 0 && re == 0) continue; /* unused guard subcarrier */
        float amplitude = sqrtf(im * im + re * re);
        sum += amplitude;
        sum_sq += amplitude * amplitude;
        used++;
    }
    if (used < 16 || sum <= 0) return;

    float mean = sum / used;
    float variance = sum_sq / used - mean * mean;
    msg_t msg = {
        .type = MSG_CSI,
        .rssi = info->rx_ctrl.rssi,
        /* Spread across subcarriers relative to their mean: ignores overall
           signal strength and receiver gain, keeps the shape. */
        .turbulence = sqrtf(variance > 0 ? variance : 0) / mean,
    };
    xQueueSend(s_queue, &msg, 0);
}

static void promiscuous_cb(void *buf, wifi_promiscuous_pkt_type_t type)
{
    if (type != WIFI_PKT_MGMT) return;
    const wifi_promiscuous_pkt_t *pkt = buf;
    if (pkt->rx_ctrl.sig_len < 24 || pkt->rx_ctrl.rssi < PROBE_MIN_RSSI) return;
    const uint8_t *frame = pkt->payload;
    if ((frame[0] & 0xFC) != 0x40) return; /* management frame, subtype probe request */
    const uint8_t *src = frame + 10;

    TickType_t now = xTaskGetTickCount();
    for (int i = 0; i < PROBE_SLOTS; i++) {
        if (memcmp(s_probes[i].mac, src, 6) == 0) {
            if (now - s_probes[i].sent < pdMS_TO_TICKS(5000)) return;
            s_probes[i].sent = now;
            goto report;
        }
    }
    memcpy(s_probes[s_probe_next].mac, src, 6);
    s_probes[s_probe_next].sent = now;
    s_probe_next = (s_probe_next + 1) % PROBE_SLOTS;

report:;
    msg_t msg = {.type = MSG_PROBE, .rssi = pkt->rx_ctrl.rssi};
    memcpy(msg.mac, src, 6);
    xQueueSend(s_queue, &msg, 0);
}

static void start_ping(const esp_ip4_addr_t *gateway)
{
    if (s_ping) {
        esp_ping_stop(s_ping);
        esp_ping_delete_session(s_ping);
        s_ping = NULL;
    }
    char text[16];
    esp_ip4addr_ntoa(gateway, text, sizeof(text));

    esp_ping_config_t config = ESP_PING_DEFAULT_CONFIG();
    ipaddr_aton(text, &config.target_addr);
    config.count = ESP_PING_COUNT_INFINITE;
    config.interval_ms = 1000 / SAMPLE_RATE_HZ;
    config.timeout_ms = 500;
    config.data_size = 8;

    esp_ping_callbacks_t callbacks = {0};
    if (esp_ping_new_session(&config, &callbacks, &s_ping) == ESP_OK) {
        esp_ping_start(s_ping);
        ESP_LOGI(TAG, "pinging router %s at %d Hz", text, SAMPLE_RATE_HZ);
    } else {
        ESP_LOGE(TAG, "could not start ping session");
    }
}

static void event_handler(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_CONNECTED) {
        memcpy(s_bssid, ((wifi_event_sta_connected_t *)data)->bssid, 6);
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        s_connected = false;
        ESP_LOGW(TAG, "WiFi lost, reconnecting");
        vTaskDelay(pdMS_TO_TICKS(1000));
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *event = data;
        ESP_LOGI(TAG, "connected, ip " IPSTR, IP2STR(&event->ip_info.ip));
        s_connected = true;
        start_ping(&event->ip_info.gw);
    }
}

static void sender_task(void *arg)
{
    struct sockaddr_in hub = {
        .sin_family = AF_INET,
        .sin_port = htons(HUB_PORT),
        .sin_addr.s_addr = inet_addr(HUB_IP),
    };
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    uint32_t sequence = 0;
    char line[64];
    msg_t msg;

    for (;;) {
        if (xQueueReceive(s_queue, &msg, portMAX_DELAY) != pdTRUE || !s_connected) continue;
        int length;
        if (msg.type == MSG_CSI) {
            length = snprintf(line, sizeof(line), "C,%s,%u,%d,%.5f\n", SENSOR_ID, (unsigned)sequence++, msg.rssi,
                              msg.turbulence);
        } else {
            length = snprintf(line, sizeof(line), "P,%s,%02x:%02x:%02x:%02x:%02x:%02x,%d\n", SENSOR_ID, msg.mac[0],
                              msg.mac[1], msg.mac[2], msg.mac[3], msg.mac[4], msg.mac[5], msg.rssi);
        }
        if (sock >= 0) sendto(sock, line, length, 0, (struct sockaddr *)&hub, sizeof(hub));
    }
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    s_queue = xQueueCreate(64, sizeof(msg_t));

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, event_handler, NULL));

    wifi_config_t wifi = {0};
    strlcpy((char *)wifi.sta.ssid, WIFI_SSID, sizeof(wifi.sta.ssid));
    strlcpy((char *)wifi.sta.password, WIFI_PASSWORD, sizeof(wifi.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE)); /* stay awake so no reply is missed */

    wifi_csi_config_t csi = {
        .lltf_en = true,
        .htltf_en = false,
        .stbc_htltf2_en = false,
        .ltf_merge_en = false,
        .channel_filter_en = false,
        .manu_scale = false,
    };
    ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi));
    ESP_ERROR_CHECK(esp_wifi_set_csi_rx_cb(csi_cb, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_csi(true));

    wifi_promiscuous_filter_t filter = {.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT};
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_filter(&filter));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous_rx_cb(promiscuous_cb));
    ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

    xTaskCreate(sender_task, "sender", 4096, NULL, 5, NULL);
    ESP_LOGI(TAG, "sensor '%s' started, reporting to %s:%d", SENSOR_ID, HUB_IP, HUB_PORT);
}
