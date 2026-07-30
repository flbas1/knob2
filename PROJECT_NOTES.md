# Smart Knob Controller — Project Notes

## Overview
Cross-platform smart knob controller system. The ESP32-S3 knob is the **host** (runs apps, LVGL UI, makes decisions). The PC/phone is a **client** (provides data, HID output). USB is primary transport; WiFi is fallback.

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

## File Structure
```
knob-control/                    # Root project directory
├── CMakeLists.txt
├── sdkconfig.defaults
├── partitions.csv
├── main/
│   ├── CMakeLists.txt
│   ├── Kconfig.projbuild
│   ├── idf_component.yml
│   ├── main.c                   # Entry point, boot sequence, main loop
│   ├── pins.h                   # GPIO mappings (verified from 3rd party repos)
│   ├── hardware_init.c/.h       # I2C, CST816, DRV2605, encoder ISR, button
│   ├── hid.c/.h                 # USB HID composite (Consumer+Mouse+Keyboard)
│   ├── knob_ui.c/.h             # LVGL v8 UI, SH8601 QSPI driver, PSRAM buffers
│   ├── websocket_client.c/.h    # WiFi STA + WebSocket client
│   ├── machine_detect.c/.h      # FAT32 FS1 mount, machine config detection
│   └── app_manager.c/.h         # App switching logic
├── fs1/
│   ├── machines/
│   │   ├── home.json
│   │   └── work.json
│   ├── settings.json
│   ├── pc/knob_client/          # Python PC client
│   ├── iphone/KnobApp/          # iOS Swift client
│   ├── android/KnobApp/         # Android Kotlin client
│   └── test-env/                # LVGL browser simulator test environment
│       ├── server.py            # Python WebSocket bridge (stdlib only, no pip)
│       ├── index.html           # Modified LVGL simulator with WS injection
│       ├── README.md
│       └── static/              # LVGL MicroPython simulator (from sim.lvgl.io v8.3)
│           ├── index.html
│           ├── app.js           # Monaco editor + MicroPython WASM bundle (3MB)
│           ├── main.css
│           ├── lvgl.html
│           ├── micropython.js
│           ├── micropython.wasm
│           ├── firmware.wasm    # MicroPython + LVGL WASM (6MB)
│           └── wasm_file_api.js
└── README.md
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

### Machine Detection
- Mounts FS1 FAT32 at boot
- Scans `machines/*.json`, loads first config found
- If no match, all apps enabled by default (setup mode)
- Uses `esp_vfs_fat_spiflash_mount_rw_wl()` with partition label `"fs1"`

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

## Build Instructions
```bash
cd knob-control
idf.py set-target esp32s3
idf.py menuconfig    # Set WiFi SSID + Password
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

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

## Current State
- All source files created and consistent (verified, no missing symbols)
- No ESP-IDF in current environment to do build test
- PC client, iOS client, Android client all complete
- Test environment server verified working (HTTP + WebSocket)
- Project ready for `idf.py build` on a machine with ESP-IDF v5.4+

## Next Steps (on new machine)
1. `idf.py set-target esp32s3 && idf.py build` — catch any compile errors
2. Flash FS1 FAT32 partition — populate `machines/*.json` configs
3. Test WiFi + WS flow with real credentials
4. Verify USB HID composite device enumerates on host
5. Test encoder ISR with physical device
6. Verify display init sequence (SH8601 QSPI)
