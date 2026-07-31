# fs2 — Knob Firmware Build

This folder holds the code to **build the knob** — MicroPython + LVGL firmware for the Waveshare ESP32-S3-Knob-Touch-LCD-1.8.

The knob is the **host**: it runs this firmware, controls the PC, and gets its commands executed by the PC's server (`../fs1/server.py`). This firmware is the brain of the whole system.

| Folder | Contains |
|--------|----------|
| `fs1/` | Python + JSON the server serves to the knob at runtime (bootstrap, configs, launcher) |
| `fs2/` | **This folder — firmware build code** |
| `hardware/` | Third-party SDKs the build depends on (esp-idf, lv_micropython) |

## What's in here

| Path | Purpose |
|------|---------|
| `main.py` | MicroPython entry point — imports `lib/`, constructs and runs `Launcher` |
| `boot.py` | Runs before `main.py` — initializes USB HID + backlight, loads `/fs1/settings.json` |
| `lib/` | Frozen MicroPython hardware drivers (see below) |
| `main/` | ESP-IDF component — `pins.h` (GPIO map), `idf_component.yml` (TinyUSB, SH8601, LVGL, WS client), `Kconfig.projbuild` |
| `CMakeLists.txt` | ESP-IDF project file (`project(knob-control)`) |
| `sdkconfig.defaults` | Board config — 16MB QIO flash, OPI PSRAM 80MHz, LVGL fonts, FATFS, TinyUSB HID, CDC logging |
| `partitions.csv` | `nvs`, `phy_init`, `fs1` FAT partition (3MB), factory app |
| `protocol/messages.py` | Shared JSON message types (knob ↔ PC) |
| `firmware/` | C-extension notes for the lv_micropython build system (see its README) |

## Hardware Drivers (`lib/`)

Frozen into the firmware — the knob's peripherals:

| Module | Peripheral |
|--------|------------|
| `hardware.py` | Board-level init: pins, I2C, shared buses, constants |
| `sh8601.py` | SH8601 AMOLED QSPI display (360×360) |
| `cst816.py` | CST816 capacitive touch (I2C 0x15) |
| `encoder.py` | Dual micro-switch rotary encoder (NOT quadrature) |
| `drv2605.py` | DRV2605 haptic LRA driver (I2C 0x5A) |
| `hid.py` | USB HID device (the knob IS a keyboard) |
| `ws_client.py` | WebSocket client — connects to the PC server |
| `plugin_manager.py` | Runtime plugin loading from machine configs |

## Runtime Flow

```
boot.py ──► main.py ──► Launcher
                           │
                           ▼
              ws_client connects to server.py (WS :8765)
                           │
              server serves bootstrap.py ──► reports machine GUID
                           │
              server sends config, then launcher.py ──► app UI
```

The physical knob boots, connects to the PC server, and is served `bootstrap.py`, its machine config, and `launcher.py` — exactly like the browser simulator (`../fs1/test-env/`). It then drives the PC: app selections become `action` messages the server routes to platform handlers.

## Build & Flash

### Prerequisites

- ESP-IDF v5.4+ (cloned into `../hardware/esp-idf/`)
- lv_micropython (in `../hardware/lv_micropython/`) — the MicroPython + LVGL build system; C extensions for it live in `firmware/`
- Python 3.10+

### Build

```bash
cd fs2
idf.py set-target esp32s3
idf.py menuconfig
idf.py build
```

### Flash

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

If flashing fails with "This chip is ESP32, not ESP32-S3", **flip the USB-C plug 180°** — the CH334 hub switches between the CH343 UART bridge and native USB-OTG depending on plug orientation.

### Settings

Wi-Fi credentials and the WebSocket URI live in `../fs1/settings.json`:

```json
{
    "wifi": {"ssid": "", "password": ""},
    "websocket_uri": "ws://10.10.10.2:8765",
    "static_ip": {"knob": "10.10.10.1", "pc": "10.10.10.2"}
}
```

## Pin Map (Summary)

| Function | GPIO |
|----------|------|
| Display SH8601 QSPI | CS 14, SCLK 13, D0–D3 15–18, RST 21, BL 47 |
| Touch CST816 (I2C) | SDA 11, SCL 12, RST 10, INT 9 |
| Encoder switches | A 8 (CW), B 7 (CCW) |
| Haptic DRV2605 (I2C) | SDA 11, SCL 12, addr 0x5A |
| DAC PCM5100A | Enable 0, BCLK 39, WS 40, DOUT 41 |
| PDM mic | CLK 45, DATA 46 |
| Battery ADC | 1 (×2, full ≈ 4.3V) |

The full annotated pin map lives in the root `README.md` and in `main/pins.h`.

## License

MIT
