# WiFiSense ESP32-CAM CSI Receiver Firmware

This module implements the ESP-IDF firmware for capturing Wi-Fi Channel State Information (CSI) and sending it over UDP to a host.

## Network & Hardware Assumptions

- **Target Hardware**: ESP32-CAM (AI Thinker board). Note: The camera module is physically present but is **never initialized** in code (no `esp_camera_init` call is linked or made).
- **Communication Protocol**: IEEE 802.11n 20 MHz HT.
- **Baud Rate**: 115200 (programming & serial monitoring).

## Project Structure

- `CMakeLists.txt` - Project-level build script.
- `sdkconfig.defaults` - Default ESP-IDF configuration rules.
- `main/`
  - `CMakeLists.txt` - Main application component.
  - `Kconfig.projbuild` - Configuration variables for Wi-Fi credentials and target host endpoints.
  - `main.c` - Wi-Fi connection, CSI callback registration, UDP transmission, and reconnect logic.

## Configuration

You can configure the SSID, password, host IP, and ports via ESP-IDF's menuconfig utility:
```bash
idf.py menuconfig
```

Configurable options under the `WiFiSense Configuration` menu:
- `CONFIG_WIFISENSE_WIFI_SSID`: Wi-Fi SSID to connect to.
- `CONFIG_WIFISENSE_WIFI_PASSWORD`: Wi-Fi Password.
- `CONFIG_WIFISENSE_HOST_IP`: Target receiver host IP address (default: `192.168.4.10`).
- `CONFIG_WIFISENSE_CSI_PORT`: Target UDP port for CSI packets (default: `5566`).
- `CONFIG_WIFISENSE_CONTROL_PORT`: Target UDP port for JSON control events (default: `5567`).

## Binary Packet Format

Each CSI packet is sent as a single UDP datagram with the following layout matching the C struct:

| Offset (Bytes) | Type | Field Name | Description |
|---|---|---|---|
| 0 | `uint32_t` | `seq_no` | Monotonic sequence number |
| 4 | `uint64_t` | `timestamp_us` | Microsecond timestamp since boot |
| 12 | `uint8_t[6]` | `mac` | Source MAC address of the AP |
| 18 | `int8_t` | `rssi` | Signal strength indicator (RSSI) |
| 19 | `uint8_t` | `channel` | Channel number (1-14) |
| 20 | `uint8_t` | `bandwidth` | Bandwidth (0 = 20 MHz, 1 = 40 MHz) |
| 21 | `uint16_t` | `csi_len` | Number of I/Q byte pairs (subcarriers) |
| 23 | `int8_t[128]` | `csi_data` | Interleaved raw I/Q pairs `[I0, Q0, I1, Q1, ...]` |

Total structure size is 151 bytes for 20 MHz HT, which easily fits in a standard Ethernet/Wi-Fi MTU (1500 bytes).

## Build and Flash

1. Configure the project:
   ```bash
   idf.py menuconfig
   ```
2. Build the project:
   ```bash
   idf.py build
   ```
3. Flash the firmware and monitor:
   ```bash
   idf.py -p <PORT> flash monitor
   ```
