# Smart Knob Controller — Project Notes

## Overview
Cross-platform smart knob controller system. The ESP32-S3 knob is the **host** (runs apps, LVGL UI, makes decisions). The PC/phone is a **client** (provides data, HID output). USB is primary transport; WiFi is fallback.

**Current implementation (2026-08):** the knob firmware is **MicroPython + LVGL**,
built with lv_micropython for the `WAVESHARE_ESP32_S3_KNOB` board (ESP-IDF v5.3).
The C ESP-IDF app described in the historical sections below (HID/TinyUSB, LVGL v8,
`sdkconfig.defaults`, `main.c`/`knob_ui.c`) was replaced by the MicroPython firmware
in `../fs2/`; those notes are kept as design reference only. See the root `README.md`
and `../fs2/README.md` for the current build & deploy flow.

## Hardware
- **Board**: Waveshare ESP32-S3-Knob-Touch-LCD-1.8 (dual MCU: ESP32-S3R8 + ESP32-U4WDH)
- **Display**: SH8601 AMOLED QSPI 360x360
- **Touch**: CST816 (I2C 0x15, needs RST pulse before I2C works)
- **Haptic**: DRV2605 (I2C 0x5A, LRA motor)
- **Audio DAC**: PCM5100A (GPIO 0 is enable pin, NOT encoder button)
- **Encoder**: NOT quadrature. Two independent micro-switches (A=CW LOW, B=CCW LOW). Both LOW = button press.
- **USB Hub**: CH334 (USB-C plug orientation matters for UART vs USB-OTG)
- **Onboard Mic**: Digital PDM (GPIO 45/46)
- **16MB Flash** total

## Flash Layout
```
nvs:    0x9000,    24KB
phy:    0xF000,     4KB
fs1:    0x10000,    3MB  (FAT32, user-accessible, machine configs)
factory: 0x310000, ~12.9MB (ESP-IDF app)
```

## File Structure (current)
```
knob-controller/
├── fs1/                       # /fs1 filesystem payload (flashed to the fs1 partition)
│   ├── bootstrap.py           # location picker — exec'd first by main.py
│   ├── launcher.py            # app launcher UI (frozen into firmware from here)
│   ├── server.py              # thin PC server (WS :8765) — identity + command routing
│   ├── settings.json          # boot_backlight / websocket_uri / static_ip
│   ├── locations/*.json       # one per room: name, machine_guid, wifi, defaults, apps
│   ├── plugins/<id>/          # app plugins (manifest.json + plugin.py)
│   ├── pc/  iphone/  android/ # client shells
│   └── test-env/              # browser sim + transparent WS bridge (testKnob.py)
├── fs2/                       # frozen firmware (MicroPython + LVGL)
│   ├── boot.py / main.py      # device entry; main.py runs /fs1/bootstrap.py first
│   ├── lib/                   # hardware drivers: hardware, sh8601, cst816, encoder,
│   │                          #   drv2605, hid, ws_client, wifi_connect, plugin_manager
│   ├── protocol/              # shared JSON message types
│   ├── partitions.csv         # fs1 3MB FAT + factory (mirrors board partition table)
│   └── firmware/              # C-extension notes (none built today)
└── hardware/                  # git-ignored SDKs
    ├── esp-idf/               # ESP-IDF v5.3
    ├── lv_micropython/        # MicroPython + LVGL build (board WAVESHARE_ESP32_S3_KNOB)
    └── CrowPanel-.../         # vendor reference SDK (untracked)
```

## Key Decisions & Gotchas

### GPIO Pin Mappings (pins.h)
Verified correct from two working third-party repos:
- dpenney/waveshare_esp32_knob_touch
- IngoDuesentrieb/esp32-s3-knob-hardware-explorer

### Encoder ISR
Standard quadrature decoding will NOT work. Two independent micro-switches, not quadrature encoders. ISR detects which pin triggered and increments/decrements accordingly. Button = both switches pressed simultaneously.

### I2C
- CST816 needs 100kHz (not 400kHz)
- CST816 needs RST pulse before I2C works
- DRV2605 on same bus at 0x5A

### Display (SH8601)
- Official component: `espressif/esp_lcd_sh8601` (v2.0.1~1)
- Uses `SH8601_PANEL_BUS_QSPI_CONFIG` and `SH8601_PANEL_IO_QSPI_CONFIG` macros
- `esp_lcd_new_panel_sh8601()` with `vendor_config.flags.use_qspi_interface = 1`
- Needs `rounder_cb` for even-aligned coordinates
- Display buffers allocated from PSRAM via `heap_caps_malloc(..., MALLOC_CAP_SPIRAM)`
- BL starts OFF during init, turns ON after display fully initialized

### LVGL
- v8 API (`lv_disp_drv_t`, `lv_indev_drv_t`)
- Pointer device steals encoder focus on touch — drive arc value directly in main loop
- `CONFIG_LV_FONT_MONTSERRAT_28=y` in sdkconfig.defaults

### USB HID (TinyUSB)
- Uses `espressif/esp_tinyusb` component (v2.0.1~1) from Component Registry
- NOT the built-in `tinyusb` from IDF
- API: `TINYUSB_DEFAULT_CONFIG()`, `tusb_cfg.descriptor.full_speed_config = hid_configuration_descriptor`
- Composite device: Consumer Control + Mouse + Keyboard
- Uses `TUD_HID_REPORT_DESC_CONSUMER`, `TUD_HID_REPORT_DESC_MOUSE`, `TUD_HID_REPORT_DESC_KEYBOARD` with `HID_REPORT_ID()` inside each
- `tud_hid_descriptor_report_cb` returns `uint8_t const *` (pointer, not size)
- `tud_hid_get_report_cb` returns `uint16_t`
- `tud_hid_set_report_cb` takes `uint8_t const *buffer`

### TinyUSB Callbacks (hid.c)
```c
// Descriptor report — return pointer to report descriptor
uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    return hid_report_descriptor;
}

// Get report — return report length
uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id,
                                uint8_t report_type, uint8_t *buffer, uint16_t reqlen) {
    return 0;
}

// Set report — receive report data
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id,
                            uint8_t report_type, uint8_t const *buffer, uint16_t bufsize) {
    // Handle HID output from host
}
```

### WebSocket
- Uses `espressif/esp_websocket_client` (>=1.1.0) from Component Registry
- Kconfig: `CONFIG_KNOB_WIFI_SSID`, `CONFIG_KNOB_WIFI_PASSWORD`, `CONFIG_KNOB_WEBSOCKET_PORT` (default 8765)
- Empty SSID = USB-HID-only mode (no WiFi, no WS)
- Static IPs: knob=10.10.10.1, PC=10.10.10.2

### Protocol (JSON over WebSocket)
```json
{"type":"discover"}
{"type":"identify","device":"knob-01","version":"1.0.0"}
{"type":"data_update","app":"gauge","data":{"value":50,"label":"Volume"}}
{"type":"data_update","app":"music","data":{"title":"Song","artist":"Artist","progress":45,"duration":200}}
{"type":"data_update","app":"dimmer","data":{"brightness":80,"color_temp":3500}}
{"type":"data_update","app":"weather","data":{"temperature":"22","condition":"Clear","humidity":"45"}}
{"type":"data_request","app":"music"}
{"type":"state_update","state":{"app":"gauge"}}
{"type":"app_switch","app":"music"}
{"type":"encoder","direction":"cw","delta":1}
{"type":"button"}
```

### Location Detection (current)
- `boot.py` mounts the `fs1` FAT partition at `/fs1`; `main.py` runs `/fs1/bootstrap.py` first.
- The PC server sends `identify` (its OS machine id) over the USB link; `bootstrap.py` reads `/fs1/locations/*.json` and preselects the matching `machine_guid`, filters by reachable `wifi.ssid` when standalone, else shows all.
- Choice saved to `/fs1/.state.json`; wifi join for the chosen location happens in bootstrap; then `launcher.py` runs.
- Historical C approach (replaced): `esp_vfs_fat_spiflash_mount_rw_wl()` with partition label `"fs1"`, first-match in `machines/*.json`, all-apps setup mode on no match.

### Client Apps
- **PC** (Python): `fs1/pc/knob_client/__init__.py` — WebSocket client with music/weather/HA providers
- **iOS** (Swift): `fs1/iphone/KnobApp/KnobConnection.swift` — NWConnection
- **Android** (Kotlin): `fs1/android/KnobApp/MainActivity.kt` — OkHttp

### Test Environment (fs1/test-env/)
- Python stdlib-only WebSocket bridge server (no pip needed)
- Serves LVGL MicroPython simulator from sim.lvgl.io v8.3 in browser
- Bridges PC client ↔ simulator via WebSocket
- Generates LVGL Python code from data_update messages
- Includes encoder buttons and console panel
- HTTP port 8080, WS port 8765

## Build Instructions (current — MicroPython + LVGL)
```bash
export IDF_PATH=$PWD/hardware/esp-idf            # ESP-IDF v5.3
. $IDF_PATH/export.sh
cd hardware/lv_micropython/ports/esp32
idf.py -B build-WAVESHARE_ESP32_S3_KNOB -D MICROPY_BOARD=WAVESHARE_ESP32_S3_KNOB build

# Flash (USB-capable machine; edge USB-C port)
idf.py -B build-WAVESHARE_ESP32_S3_KNOB -p /dev/ttyUSB0 flash monitor
```
First boot formats an empty `/fs1` — push the payload (`fs1/` → `settings.json`,
`bootstrap.py`, `server.py`, `locations/*.json`, `plugins/*`) with `mpremote`
before first use. Full command list in `../fs2/README.md`.

Historical C build (replaced): `cd knob-control; idf.py set-target esp32s3; idf.py menuconfig; idf.py build; idf.py -p /dev/ttyUSB0 flash monitor`.

## Component Dependencies (idf_component.yml)
```yaml
dependencies:
  espressif/esp_tinyusb: "^2.0.1~1"
  espressif/esp_lcd_sh8601: ">=2.0.0"
  lvgl/lvgl: "^8"
  espressif/esp_websocket_client: ">=1.1.0"
```

## sdkconfig.defaults Key Settings
```
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y
CONFIG_ESPTOOLPY_FLASHMODE_QIO=y
CONFIG_ESP32S3_SPIRAM_SUPPORT=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_TINYUSB=y
CONFIG_TINYUSB_HID=y
CONFIG_LV_FONT_MONTSERRAT_28=y
CONFIG_FATFS_LONG_FILENAME_SUPPORT=y
CONFIG_VFS_LONG_NAMESUPPORT=y
CONFIG_FREERTOS_HZ=1000
```

## Current State (2026-08)
- Firmware **compiled successfully** for `WAVESHARE_ESP32_S3_KNOB` (MicroPython + LVGL, ESP-IDF v5.3):
  `micropython.bin` ≈2.6MB, frozen `boot`/`main`/`launcher` + `lib/*` + `protocol/messages`.
  Partition table verified: `nvs`, `phy_init`, `fs1` FAT 3MB @ 0x10000, `factory` @ 0x310000.
- Location picker + identify + wifi-join flow implemented and py_compile-clean; CPython harness verified
  (USB-link skip, sim no-op, standalone wifi join).
- PC server, PC/iOS/Android clients, and browser sim complete.
- **Not yet done:** flashing + `/fs1` payload push to real hardware (needs a USB-capable machine — this
  container has no USB), real-device display/touch/encoder bring-up, wifi join against a real AP.

## Next Steps
1. Flash `micropython.bin` + bootloader + partition table on a USB-capable machine; push the `/fs1` payload.
2. First-boot check: `/fs1` mounts, location picker renders, `.state.json` written after a pick.
3. Standalone wifi join against a real AP (bedroom/living-room configs).
4. Verify USB link path: knob plugged into a PC → server `identify` preselects the location.
5. Real-device smoke tests: display init (SH8601 QSPI), touch (CST816), encoder, haptic (DRV2605), audio.
