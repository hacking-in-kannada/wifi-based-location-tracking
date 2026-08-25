/**
 * @file main.c
 * @brief ESP32-CAM CSI Capture and UDP Streaming Firmware
 * @details Captures Wi-Fi Channel State Information (CSI) from packets matching specific criteria
 * and streams the raw data via UDP. Camera hardware is explicitly not initialized.
 *
 * KEY FIX: A keepalive task sends UDP probes to the host at 50Hz.
 * The host's network stack (and AP routing) generates received frames back to
 * the ESP32, which trigger the CSI callback continuously.
 */

#include <string.h>
#include <sys/param.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_timer.h"
#include "esp_task_wdt.h"

#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include <lwip/netdb.h>

/* Logging tags */
static const char *TAG_CSI  = "WIFISENSE_CSI";
static const char *TAG_NET  = "WIFISENSE_NET";
static const char *TAG_KEEP = "WIFISENSE_KA";

/* Wi-Fi configuration and state */
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1
static EventGroupHandle_t s_wifi_event_group;
static bool g_wifi_connected = false;
static uint32_t g_reconnect_delay_ms = 1000;
#define MAX_RECONNECT_DELAY_MS 30000

/* UDP socket details */
static int g_csi_socket  = -1;
static int g_ctrl_socket = -1;
static struct sockaddr_in g_dest_addr_csi;
static struct sockaddr_in g_dest_addr_ctrl;

/* Dedicated keepalive socket — separate from CSI socket */
static int g_ka_socket = -1;
static struct sockaddr_in g_dest_addr_ka;

/* Watchdog & Health tracking */
static uint64_t g_last_csi_time_us = 0;
static uint32_t g_csi_seq_no       = 0;

/* Gateway IP stored at connect time — keepalive pings the phone/AP directly */
static char g_gateway_ip[16] = {0};
static volatile bool g_ka_ready = false;  /* delays keepalive 1s after connect */

/**
 * @brief CSI Packet binary structure (packed).
 * Must match the host-side Python parser definition exactly.
 */
typedef struct __attribute__((packed)) {
    uint32_t seq_no;
    uint64_t timestamp_us;
    uint8_t  mac[6];
    uint8_t  rssi;          /* int8_t stored as uint8_t */
    uint8_t  channel;
    uint8_t  bandwidth;     /* 0=20MHz, 1=40MHz */
    uint16_t csi_len;       /* number of int8 pairs (I,Q) following */
    int8_t   csi_data[128]; /* raw I/Q data */
} csi_packet_t;

/**
 * @brief Send a JSON log line over UDP control port.
 */
static void send_control_log(const char *level, const char *message) {
    if (g_ctrl_socket < 0 || !g_wifi_connected) {
        return;
    }

    char json_buf[256];
    int len = snprintf(json_buf, sizeof(json_buf),
                       "{\"timestamp_us\":%llu,\"level\":\"%s\",\"source\":\"WIFISENSE_NET\",\"message\":\"%s\"}\n",
                       (unsigned long long)esp_timer_get_time(), level, message);

    if (len > 0 && len < sizeof(json_buf)) {
        sendto(g_ctrl_socket, json_buf, len, 0, (struct sockaddr *)&g_dest_addr_ctrl, sizeof(g_dest_addr_ctrl));
    }
}

/**
 * @brief Initialize UDP sockets for CSI, Control, and Keepalive streams.
 */
static void init_udp_sockets(void) {
    /* CSI destination */
    g_dest_addr_csi.sin_addr.s_addr = inet_addr(CONFIG_WIFISENSE_HOST_IP);
    g_dest_addr_csi.sin_family      = AF_INET;
    g_dest_addr_csi.sin_port        = htons(CONFIG_WIFISENSE_CSI_PORT);

    /* Control destination */
    g_dest_addr_ctrl.sin_addr.s_addr = inet_addr(CONFIG_WIFISENSE_HOST_IP);
    g_dest_addr_ctrl.sin_family      = AF_INET;
    g_dest_addr_ctrl.sin_port        = htons(CONFIG_WIFISENSE_CONTROL_PORT);

    /* Keepalive destination: send probe to a high port on the laptop */
    g_dest_addr_ka.sin_addr.s_addr = inet_addr(CONFIG_WIFISENSE_HOST_IP);
    g_dest_addr_ka.sin_family      = AF_INET;
    g_dest_addr_ka.sin_port        = htons(7000); /* simple probe port, no server needed */

    /* Create sockets */
    g_csi_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (g_csi_socket < 0) {
        ESP_LOGE(TAG_NET, "Failed to create CSI socket: errno %d", errno);
    }

    g_ctrl_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (g_ctrl_socket < 0) {
        ESP_LOGE(TAG_NET, "Failed to create Control socket: errno %d", errno);
    }

    g_ka_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (g_ka_socket < 0) {
        ESP_LOGE(TAG_KEEP, "Failed to create keepalive socket: errno %d", errno);
    }
}

/**
 * @brief Clean up UDP sockets.
 */
static void close_udp_sockets(void) {
    if (g_csi_socket >= 0)  { close(g_csi_socket);  g_csi_socket  = -1; }
    if (g_ctrl_socket >= 0) { close(g_ctrl_socket); g_ctrl_socket = -1; }
    if (g_ka_socket >= 0)   { close(g_ka_socket);   g_ka_socket   = -1; }
}

/**
 * @brief Setup CSI Acquisition Config.
 */
static void configure_csi(void) {
    wifi_csi_config_t csi_config = {
        .lltf_en           = true,
        .htltf_en          = true,
        .stbc_htltf2_en    = true,
        .ltf_merge_en      = true,
        .channel_filter_en = true,
        .manu_scale        = false,
        .shift             = 0,
        .dump_ack_en       = true,   /* Capture ACK frames too — more CSI callbacks */
    };

    esp_err_t err = esp_wifi_set_csi(true);
    if (err != ESP_OK) {
        ESP_LOGE(TAG_CSI, "Failed to enable CSI: %s", esp_err_to_name(err));
        return;
    }

    err = esp_wifi_set_csi_config(&csi_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG_CSI, "Failed to set CSI config: %s", esp_err_to_name(err));
        return;
    }

    ESP_LOGI(TAG_CSI, "CSI Configured and Enabled successfully");
}

/**
 * @brief Wi-Fi CSI Callback Handler.
 * Packs and streams the captured data over UDP.
 */
static void wifi_csi_cb(void *ctx, wifi_csi_info_t *info) {
    if (!info) {
        return;
    }

    /* Always update watchdog timestamp — even for beacon/ACK frames with no payload.
     * Without this, the watchdog fires if only control frames are received. */
    g_last_csi_time_us = esp_timer_get_time();

    /* Skip sending if no useful CSI payload */
    if (info->len == 0 || !info->buf) {
        return;
    }

    csi_packet_t packet;
    memset(&packet, 0, sizeof(packet));

    packet.seq_no       = g_csi_seq_no++;
    packet.timestamp_us = g_last_csi_time_us;
    memcpy(packet.mac, info->mac, 6);
    packet.rssi      = (uint8_t)info->rx_ctrl.rssi;
    packet.channel   = info->rx_ctrl.channel;
    packet.bandwidth = info->rx_ctrl.cwb;

    uint16_t data_len = (info->len > 128) ? 128 : info->len;
    packet.csi_len = data_len / 2;
    memcpy(packet.csi_data, info->buf, data_len);

    if (g_wifi_connected && g_csi_socket >= 0) {
        int ret = sendto(g_csi_socket, &packet, sizeof(packet), 0,
                         (struct sockaddr *)&g_dest_addr_csi, sizeof(g_dest_addr_csi));
        if (ret < 0) {
            ESP_LOGW(TAG_CSI, "UDP send failed: errno %d", errno);
        }
    }
}

/**
 * @brief Keepalive Task — pings the gateway (phone/AP) at 5 Hz.
 *
 * WHY GATEWAY, NOT LAPTOP:
 * The phone is the AP. Sending UDP to the phone forces it to send back
 * an ICMP "port unreachable" reply — a full DATA frame received by the
 * ESP32 which reliably triggers CSI callbacks with valid payload.
 * Targeting the laptop at 50Hz caused ENOMEM from LWIP buffer exhaustion.
 */
static void keepalive_task(void *arg) {
    uint32_t ka_seq = 0;

    ESP_LOGI(TAG_KEEP, "Keepalive task started.");

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(200)); /* 5 Hz */

        if (!g_wifi_connected || g_ka_socket < 0 || !g_ka_ready) {
            continue;
        }

        char buf[32];
        int len = snprintf(buf, sizeof(buf), "WIFISENSE_KA:%u", (unsigned int)ka_seq++);
        sendto(g_ka_socket, buf, len, 0,
               (struct sockaddr *)&g_dest_addr_ka, sizeof(g_dest_addr_ka));
    }
}

/**
 * @brief Wi-Fi and System Event Handler.
 */
static void event_handler(void* arg, esp_event_base_t event_base,
                           int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();

    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        g_wifi_connected = false;
        close_udp_sockets();
        ESP_LOGW(TAG_NET, "Disconnected from AP. Retrying in %u ms...",
                 (unsigned int)g_reconnect_delay_ms);

        vTaskDelay(pdMS_TO_TICKS(g_reconnect_delay_ms));
        g_reconnect_delay_ms = MIN(g_reconnect_delay_ms * 2, MAX_RECONNECT_DELAY_MS);
        esp_wifi_connect();

    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG_NET, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));

        /* Store gateway IP — keepalive pings the phone/AP for CSI traffic */
        snprintf(g_gateway_ip, sizeof(g_gateway_ip), IPSTR,
                 IP2STR(&event->ip_info.gw));
        ESP_LOGI(TAG_KEEP, "Gateway IP stored: %s", g_gateway_ip);

        g_wifi_connected       = true;
        g_reconnect_delay_ms   = 1000;

        /* Reset watchdog timer */
        g_last_csi_time_us = esp_timer_get_time();
        g_ka_ready = false; /* will be set true after 1s delay below */

        init_udp_sockets();

        /* Update keepalive destination to GATEWAY (phone/AP) on port 50000.
         * Phone sends back ICMP unreachable → real DATA frame → CSI fires. */
        g_dest_addr_ka.sin_addr.s_addr = inet_addr(g_gateway_ip);
        g_dest_addr_ka.sin_family      = AF_INET;
        g_dest_addr_ka.sin_port        = htons(50000);

        send_control_log("INFO", "Wi-Fi Connected and IP obtained");

        configure_csi();
        esp_err_t err = esp_wifi_set_csi_rx_cb(&wifi_csi_cb, NULL);
        if (err == ESP_OK) {
            ESP_LOGI(TAG_CSI, "CSI Callback registered successfully");
            send_control_log("INFO", "CSI Callback registered");
        } else {
            ESP_LOGE(TAG_CSI, "Failed to register CSI Callback: %s", esp_err_to_name(err));
        }

        /* Delay keepalive by 1 second to let LWIP settle after reconnect */
        vTaskDelay(pdMS_TO_TICKS(1000));
        g_ka_ready = true;
        ESP_LOGI(TAG_KEEP, "Keepalive armed. Probing gateway %s at 5 Hz", g_gateway_ip);

        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

/**
 * @brief Initialize Wi-Fi Station Mode.
 */
static void wifi_init_sta(void) {
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid     = CONFIG_WIFISENSE_WIFI_SSID,
            .password = CONFIG_WIFISENSE_WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG_NET, "wifi_init_sta completed. SSID: %s", CONFIG_WIFISENSE_WIFI_SSID);
}

/**
 * @brief Application Entry Point.
 */
void app_main(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG_NET, "Starting WiFiSense CSI Firmware (Camera disabled)");

    /* Initialize Wi-Fi */
    wifi_init_sta();

    /* Spawn keepalive task immediately — it guards internally with g_wifi_connected
     * so it will start sending probes as soon as Wi-Fi connects. */
    xTaskCreate(keepalive_task, "wifisense_ka", 2048, NULL, 5, NULL);
    ESP_LOGI(TAG_KEEP, "Keepalive task spawned.");

    g_last_csi_time_us = esp_timer_get_time();

#if CONFIG_ESP_TASK_WDT
    esp_task_wdt_add(NULL);
#endif

    while (1) {
#if CONFIG_ESP_TASK_WDT
        esp_task_wdt_reset();
#endif
        vTaskDelay(pdMS_TO_TICKS(1000));

        /* Health Watchdog */
        if (g_wifi_connected) {
            uint64_t now = esp_timer_get_time();
            if (now - g_last_csi_time_us > 10000000ULL) {
                ESP_LOGE(TAG_CSI, "Watchdog: No CSI for >10s. Restarting Wi-Fi...");
                send_control_log("WARNING", "No CSI for 10s. Reconnecting...");
                esp_wifi_disconnect();
                g_last_csi_time_us = now;
            }
        }
    }
}
