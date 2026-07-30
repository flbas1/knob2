# Knob Control

A portable smart knob that adapts to whatever computer it's plugged into.

The knob is the host. The PC is a client. You take the knob from home to work, and it automatically loads the right configuration.

## Architecture

```
┌──────────────────────────────────────┐
│           THE KNOB (Host)            │
│                                      │
│  FS1 (FAT32, user-accessible):      │
│  ┌────────────────────────────────┐  │
│  │ machines/                      │  │
│  │   ├─ home.json                 │  │
│  │   ├─ work.json                 │  │
│  │   └─ laptop.json               │  │
│  │ plugins/                       │  │
│  │   └─ timer.py                  │  │
│  │ pc/                            │  │
│  │   └─ knob_client/              │  │
│  │ iphone/KnobApp/                │  │
│  │ android/KnobApp/               │  │
│  │ settings.json                  │  │
│  └────────────────────────────────┘  │
│                                      │
│  FS2 (ESP-IDF firmware, internal):  │
│  ┌────────────────────────────────┐  │
│  │ main/                          │  │
│  │   ├─ main.c        (boot+loop)│  │
│  │   ├─ hardware_init.c (I2C,touch│  │
│  │   │   encoder,haptic)         │  │
│  │   ├─ app_manager.c  (app switch)│  │
│  │   ├─ hid.c          (USB HID) │  │
│  │   ├─ knob_ui.c      (LVGL UI) │  │
│  │   ├─ websocket_client.c       │  │
│  │   └─ pins.h (Waveshare GPIO)  │  │
│  └────────────────────────────────┘  │
│                                      │
│  Input: EC11 rotary encoder + CST816 │
│  Output: SH8601 AMOLED QSPI 360x360│
│  Haptic: DRV2605 LRA               │
│  HID: USB TinyUSB (knob IS keyboard)│
└────────────┬─────────────────────────┘
             │ USB CDC-Ether / WiFi
             ▼
┌──────────────────────────────────────┐
│        PC (Client - lightweight)     │
│                                      │
│  - Discovers knob via USB/WiFi       │
│  - Provides optional data:           │
│    * Music info (Spotify/playerctl)  │
│    * HA lights (REST API)            │
│    * Weather (Open-Meteo)            │
│  - Executes HID from knob            │
│                                      │
│  No apps run on the PC.              │
│  The knob tells the PC what to do.   │
└──────────────────────────────────────┘
```

## Hardware

**Waveshare ESP32-S3-Knob-Touch-LCD-1.8**
https://www.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8

Dual MCU: ESP32-S3R8 (main, 16MB Flash / 8MB PSRAM) + ESP32-U4WDH (companion, 4MB Flash). Connected via CH334 USB hub — the USB-C port switches between ESP32-S3 native USB-OTG and CH343 UART bridge depending on plug orientation.

### Pin Map (Verified)

| Function | GPIO | Notes |
|----------|------|-------|
| **Display (SH8601 AMOLED, QSPI, 360×360)** | | |
| LCD_CS | 14 | Chip select |
| LCD_SCLK | 13 | Clock |
| LCD_D0 (MOSI) | 15 | SDIO0 |
| LCD_D1 (MISO) | 16 | SDIO1 |
| LCD_D2 | 17 | SDIO2 |
| LCD_D3 | 18 | SDIO3 |
| LCD_RST | 21 | Hardware reset (active LOW) |
| LCD_BL | 47 | Backlight (HIGH = on) |
| **Touch (CST816, I2C 0x15)** | | |
| TOUCH_SDA | 11 | I2C data |
| TOUCH_SCL | 12 | I2C clock |
| TOUCH_RST | 10 | Hardware reset (pulse LOW→HIGH) |
| TOUCH_INT | 9 | Interrupt, open-drain active LOW, INPUT_PULLUP |
| **Encoder (two independent micro-switches)** | | |
| ENCODER_A | 8 | CW switch — goes LOW while turning CW |
| ENCODER_B | 7 | CCW switch — goes LOW while turning CCW |
| **Haptic (DRV2605, I2C 0x5A)** | | |
| DRV2605 SDA | 11 | Shared I2C bus |
| DRV2605 SCL | 12 | Shared I2C bus |
| **Audio (PCM5100A DAC)** | | |
| PCM5100A Enable | 0 | HIGH = DAC active, LOW = mute (NOT encoder button!) |
| I2S BCLK | 39 | Bit clock |
| I2S WS | 40 | Word select |
| I2S DOUT | 41 | Data out → 3.5mm jack |
| **PDM Microphone** | | |
| PDM_CLK | 45 | |
| PDM_DATA | 46 | |
| **Battery** | | |
| BAT_ADC | 1 | Factor ×2, full ≈ 4.3V |

### Important Hardware Notes

1. **Encoder is NOT quadrature** — The rotary knob uses two independent micro-switches, not a standard quadrature encoder. Switch A goes LOW while turning CW, switch B goes LOW while turning CCW. Standard quadrature decoding will not work.

2. **USB-C plug orientation matters** — Behind the USB-C port is a CH334 USB hub with two devices: CH343 UART bridge (companion ESP32) and native ESP32-S3 USB-OTG. Which one is active depends on the plug orientation. If flashing fails with "This chip is ESP32, not ESP32-S3", flip the plug.

3. **GPIO 0 is PCM5100A enable**, not an encoder button. The encoder has no push button.

4. **I2C bus at 100 kHz** is recommended for CST816 stability (the vendor demo uses 100 kHz, not 400 kHz).

5. **Touch requires hardware reset** — CST816 needs a RST pulse (LOW→HIGH) before I2C will respond. TOUCH_INT must be INPUT_PULLUP.

6. **LVGL encoder coexistence** — LVGL's pointer device steals encoder focus when you touch the screen. Drive the arc value directly in the main loop instead of using LVGL's encoder indev group.

### Resource Links

| Resource | Link |
|----------|------|
| Product page | https://www.waveshare.com/esp32-s3-knob-touch-lcd-1.8.htm |
| Wiki / documentation | https://www.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8 |
| Schematic diagram | https://files.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8/ESP32-S3-Knob-Touch-LCD-1.8-schematic.zip |
| Official demo (Arduino + ESP-IDF) | https://files.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8/ESP32-S3-Knob-Touch-LCD-1.8-Demo.zip |
| Pre-built BIN file | https://files.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8/ESP32-S3-Knob-Touch-LCD-1.8-BIN.zip |
| AIDA64 config (secondary screen) | https://files.waveshare.com/wiki/common/Aida_remote_1.85.zip |
| ESP32-S3 datasheet | https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf |
| ESP32-S3 technical reference | https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf |
| LVGL documentation | https://docs.lvgl.io/master/intro/introduction/index.html |

### Third-Party Projects

| Project | Description |
|---------|-------------|
| [dpenney/waveshare_esp32_knob_touch](https://github.com/dpenney/waveshare_esp32_knob_touch) | PlatformIO LVGL demo — touch + encoder, tested working |
| [IngoDuesentrieb/esp32-s3-knob-hardware-explorer](https://github.com/IngoDuesentrieb/esp32-s3-knob-hardware-explorer) | PlatformIO hardware explorer — all peripherals verified |
| [muness/roon-knob](https://github.com/muness/roon-knob) | HiFi controller, dual-chip architecture explained, AVRCP |
| [KrX3D/WaveShare-Knob-Esp32S3](https://github.com/KrX3D/WaveShare-Knob-Esp32S3) | ESPHome config |
| [nkinnan/Waveshare-ESP32-S3-Knob-Touch-LCD-1.8...](https://github.com/nkinnan/Waveshare-ESP32-S3-Knob-Touch-LCD-1.8_and_Guition-K5-Knob-Series-JC3636K518) | Full ESPHome config |
| [VolosR/Knob18Meters](https://github.com/VolosR/Knob18Meters) | Volos Projects demo |
| [ihayri/ESP32-S3-1.8inch-Knob-Display-Development-Board](https://github.com/ihayri/ESP32-S3-1.8inch-Knob-Display-Development-Board) | Combination lock example |
| [0015/lvgl_kawaii_face](https://github.com/0015/lvgl_kawaii_face) | Animated face for ESP32 |
| [knobby-mtg/knobby-mtg-life-counter](https://github.com/knobby-mtg/knobby-mtg-life-counter) | MTG life counter for round displays |
| [Tasmota discussion #23737](https://github.com/arendst/Tasmota/discussions/23737) | ST77916 display init, CST816 touch |

### Board Variants

| Variant | MCU | Flash | PSRAM | Notes |
|---------|-----|-------|-------|-------|
| ESP32-S3-Knob-Touch-LCD-1.8 | ESP32-S3R8 + ESP32-U4WDH | 16MB | 8MB OPI | With battery header, CNC metal case |
| ESP32-S3-Knob-Touch-LCD-1.8-EN | Same | Same | Same | European variant |
| ESP32-S3-Knob-Touch-LCD-1.8B | Same | Same | Same | Alternate model |

### LCD Specifications

| Spec | Value |
|------|-------|
| Panel | IPS |
| Size | 1.8 inch round |
| Resolution | 360 × 360 |
| Color depth | 262K |
| Brightness | 600 cd/m² |
| Contrast ratio | 1200:1 |
| Interface | QSPI |
| Driver IC | SH8601 (some documentation references ST77916) |
| Touch IC | CST816 (capacitive) |

### Onboard Components

| # | Component | Description |
|---|-----------|-------------|
| 1 | ESP32-S3R8 | Wi-Fi/BT SoC, 240MHz, 8MB PSRAM |
| 2 | ESP32-U4WDH | Companion chip, 240MHz, 4MB Flash |
| 3 | PCM5100A | High-performance stereo DAC (I2S) |
| 4 | USB-to-UART | CH343 bridge |
| 5 | 16MB Flash | Extended flash |
| 6 | Dual encoder | Acting on ESP32-S3 and ESP32 respectively |
| 7 | TF card slot | FatFS format |
| 8 | DRV2605 | Vibration motor driver (I2C) |
| 9 | CH445P | 4-pole 2-throw 3.3V analog switch |
| 10 | Digital MIC | PDM microphone |
| 11 | Ceramic antenna | 2.4 GHz |
| 12 | PH1.27 10P SMD header | Expansion |

## Transport

1. **USB CDC-Ether** (primary) — knob appears as network interface, static IPs: knob `10.10.10.1`, PC `10.10.10.2`
2. **WiFi** (fallback) — `settings.json` stores `known_networks`

## Machine Detection

When plugged into a computer:
1. Knob identifies machine (USB descriptor, hostname, MAC)
2. Checks `FS1/machines/<machine_id>.json`
3. Loads plugins enabled for that machine
4. If no config, enters setup mode on display

## Per-Machine Config (`machines/<machine>.json`)

```json
{
    "name": "Work Laptop",
    "platform": "windows",
    "plugins": {
        "hid": {"enabled": true},
        "music": {"enabled": false},
        "ha_dimmer": {"enabled": false},
        "weather": {"enabled": true}
    },
    "settings": {
        "volume_sensitivity": 3,
        "scroll_sensitivity": 2,
        "screen_brightness": 150
    }
}
```

## Dual Filesystem

| Filesystem | Format | Contents | Access |
|-----------|--------|----------|--------|
| **FS1** | FAT32 | Per-machine configs, plugins, PC/phone clients, settings | USB mass storage |
| **FS2** | ESP-IDF firmware | C firmware: LVGL, HID, apps, transport | Internal only |

FS1 mounts as USB drive when knob is plugged in. Edit configs in any text editor, drop plugin `.py` files into `plugins/`.

## Project Structure

```
knob-control/
├── CMakeLists.txt              # ESP-IDF project file
├── sdkconfig.defaults          # ESP32-S3 board config (16MB flash, OPI PSRAM)
│
├── main/                       # ESP-IDF main component (firmware)
│   ├── CMakeLists.txt
│   ├── Kconfig.projbuild       # menuconfig options
│   ├── pins.h                  # GPIO mappings for Waveshare board
│   ├── main.c                  # Entry point + main loop
│   ├── hardware_init.c/.h      # I2C, CST816 touch, DRV2605, encoder ISR
│   ├── app_manager.c/.h        # App switching + input routing
│   ├── hid.c/.h                # USB HID via TinyUSB
│   ├── knob_ui.c/.h            # LVGL display layer
│   └── websocket_client.c/.h   # WebSocket communication
│
├── fs1/                        # FS1: FAT32 (user-accessible USB drive)
│   ├── machines/               # Per-machine configs
│   │   ├── home.json
│   │   └── work.json
│   ├── plugins/                # User plugins (drop .py files here)
│   │   └─ timer.py
│   ├── pc/                     # PC client (Python)
│   │   └─ knob_client/
│   ├── iphone/KnobApp/         # iOS client (Swift)
│   ├── android/KnobApp/        # Android client (Kotlin)
│   └── settings.json           # Global settings + known WiFi
│
└── protocol/
    └── messages.py             # Shared JSON protocol (knob ↔ clients)
```

## Quick Start

### Build & Flash Firmware (ESP-IDF)
```bash
cd knob-control
idf.py set-target esp32s3
idf.py menuconfig       # Configure WiFi credentials, HID transport, etc.
idf.py build
idf.py flash monitor
```

### PC Client (optional — music/weather/HA data)
```bash
cd fs1/pc
pip install -e .
knob-client  # Auto-discovers knob via USB, provides data
```

## FAQ

### Why can't the program be flashed?

The board has two USB devices behind the CH334 hub: CH343 UART bridge (companion chip) and native ESP32-S3 USB-OTG. Which one is active depends on plug orientation.

- **Wrong orientation** → only `usbserial-*` shows up, esptool says "This chip is ESP32, not ESP32-S3"
- **Right orientation** → `usbmodem` appears, everything works

**Fix:** Disconnect USB-C cable, flip it 180°, re-insert and try again.

### Touch not responding

The CST816 requires a hardware reset (RST pulse LOW→HIGH) before I2C will respond. Ensure `touch_init()` pulses TOUCH_RST.

### Encoder breaks after touching screen

LVGL's pointer device steals group focus. Don't use LVGL's encoder indev — drive the arc value directly in the main loop.

### UI frozen at first frame

`lv_tick_inc()` must be called every loop iteration, or LVGL's internal timer never advances.

## Building for Other Platforms

The architecture supports swapping knob hardware:
- **ESP32-S3 knob** — current, runs LVGL + TinyUSB
- **40" touchscreen** — Python client with full UI, knob becomes a remote
- **iPhone/Android** — touch dial replaces physical encoder, same WebSocket protocol

The protocol stays the same. Only the transport and UI layer change.
