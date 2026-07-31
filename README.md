# Knob Control

A portable smart knob that adapts to whatever computer it's plugged into.

The **knob is the host** — it controls the PC. The **PC is the client** — it gets its commands from the knob. Take the knob from home to work and it automatically loads the right configuration for wherever it lands.

It's a very symbiotic relationship: the knob runs the UI and drives the whole experience, while the PC serves it the code and configs it needs, feeds it data (music, lights, weather), and executes platform actions (volume, brightness, zoom, scroll) on its behalf.

## Repository Layout

```
.
├── fs1/        Knob-side Python + JSON — code the server serves to the knob
├── fs2/        Firmware build code — MicroPython + LVGL + ESP-IDF
├── hardware/   Third-party SDKs + hardware notes (git-ignored)
└── README.md
```

| Folder | Contents | Git |
|--------|----------|-----|
| `fs1/` | `server.py`, `bootstrap.py`, `launcher.py`, machine configs, platform handlers, test simulator, mobile client shells | tracked |
| `fs2/` | Firmware: `boot.py`, `main.py`, frozen drivers (`lib/`), ESP-IDF project, partition table | tracked |
| `hardware/` | ESP-IDF SDK, lv_micropython build, CrowPanel reference SDK, notes | **ignored** |

## Architecture

The PC runs a small server (`fs1/server.py`) that drives a **bootstrap protocol** over WebSocket:

1. It serves `bootstrap.py` to the knob, which probes its identity and reports a machine GUID.
2. The server matches that GUID against a config in `fs1/machines/{machine_guid}.json`.
3. It sends the config, then serves `launcher.py`, which builds the app-launcher UI on the knob.
4. From then on the **knob drives**: app selections and commands (volume up, brightness set, scroll, zoom) flow to the PC, which executes them via `KnobClient` platform handlers.

```
┌─────────────────────┐           ┌──────────────────────────────────┐
│   THE KNOB (host)   │           │      PC SERVER (server.py)       │
│                     │           │                                  │
│  MicroPython + LVGL │           │  Bootstrap protocol:             │
│  ├─ bootstrap.py*   │  WS :8765 │  1. Serve bootstrap.py → knob    │
│  ├─ launcher.py*    │◄────────►│  2. Knob reports machine GUID     │
│  ├─ plugin_*.py*    │           │  3. Match config → send config   │
│                     │           │  4. Knob acks → serve launcher   │
│  *served by server  │           │                                  │
│                     │           │  Command routing:                │
│                     │           │  volume, brightness, scroll, zoom│
│                     │           │  → KnobClient platform handlers  │
└─────────────────────┘           └──────────────────────────────────┘
```

### Bootstrap Flow

```
server.py                          Knob (physical or sim)
   │                                      │
   │  ── Step 1 ──                        │
   │  {"type":"execute","code":"<boot>"}  │
   │─────────────────────────────────────►│
   │                                      │  Runs bootstrap.py
   │  {"type":"bootstrap_response",       │  reports identity
   │    "data":{"machine_guid":"..."}}    │
   │◄─────────────────────────────────────│
   │                                      │
   │  ── Step 2 ──                        │
   │  Match GUID → machine config         │
   │  (literal GUID match, no globs)      │
   │                                      │
   │  {"type":"config","config":{...}}    │
   │─────────────────────────────────────►│
   │                                      │  Stores config
   │  {"type":"config_ack","status":"ok"} │
   │◄─────────────────────────────────────│
   │                                      │
   │  ── Step 3 ──                        │
   │  {"type":"execute","code":"<launch>"}│
   │─────────────────────────────────────►│
   │                                      │  Builds app launcher
   │  {"type":"launcher_ready",           │
   │    "apps":[{"id":"volume",...}]}     │
   │◄─────────────────────────────────────│
   │                                      │
   │  ── Interaction ──                   │
   │  {"type":"app_selected","app":"vol"} │
   │◄─────────────────────────────────────│
   │  {"type":"action",                   │
   │    "app":"volume","cmd":"set",       │
   │    "value":42}                       │
   │─────────────────────────────────────►│
```

The server injects the machine list into bootstrap code as `_AVAILABLE_MACHINES`, and the `execute` message carries a `machines` array so the simulator can populate its Machine dropdown.

### Development Simulator

```
Browser ──WS :8766──► testKnob.py ──WS :8765──► server.py
                        (pipe)
```

`fs1/test-env/testKnob.py` is a **transparent bridge** — it serves the simulator UI (HTTP :8080) and pipes every WebSocket message between the browser and `server.py` unmodified. Zero logic. A browser knob runs the exact same bootstrap → config → launcher flow as the physical device.

## Protocol

| Type | Direction | Purpose |
|------|-----------|---------|
| `execute` | Server → Knob | Run MicroPython code (includes `machines` array for sim dropdown) |
| `bootstrap_response` | Knob → Server | Identity after bootstrap |
| `config` | Server → Knob | Machine config |
| `config_ack` | Knob → Server | Config accepted |
| `launcher_ready` | Knob → Server | Launcher UI live |
| `app_selected` | Knob → Server | User picked an app |
| `action` | Knob → Server | App command (volume up, brightness set, etc) |
| `data_update` | Either | App-specific state push |
| `data_request` | Knob → Server | Request current state |

## Machine Configs

Each machine has a config in `fs1/machines/` named after its literal GUID:

```json
{
    "name": "Development Sim",
    "machine_guid": "sim-dev-001",
    "location": "Simulator",
    "haptic": false,
    "sound": false,
    "backlight": 100,
    "apps": [
        {"id": "volume",     "name": "Volume"},
        {"id": "brightness", "name": "Brightness"}
    ]
}
```

The filename is `{machine_guid}.json` (e.g. `sim-dev-001.json`). `location` describes where the machine lives (Simulator, Office, Home, …).

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
2. **WiFi** (fallback) — `fs1/settings.json` stores SSID/password; the knob opens a WebSocket to `ws://10.10.10.2:8765`

## Machine Detection

When the knob connects to the server:

1. Server serves `bootstrap.py` — the knob probes its identity (USB descriptor, hostname, MAC) and reports a machine GUID
2. Server matches `fs1/machines/{machine_guid}.json`
3. Server sends the matched config, then `launcher.py` — which enables the apps/plugins in that config
4. If no config matches, the knob enters setup mode on the display

## Quick Start

### Run the PC Server + Simulator

```bash
cd fs1
python3 server.py &          # Real PC server (WS :8765)
python3 test-env/testKnob.py # Transparent bridge (HTTP :8080, WS :8766)
# Open http://localhost:8080
```

The full bootstrap → config → launcher flow runs transparently through the bridge. See `fs1/start.txt` for the expected WS log and simulator keyboard shortcuts.

### Build & Flash Firmware

```bash
cd fs2
idf.py set-target esp32s3
idf.py menuconfig
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

See `fs2/README.md` for details.

### Mobile Clients

The protocol is transport-agnostic — `fs1/android/` and `fs1/iphone/` are client shells using the same WebSocket protocol.

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
- **ESP32-S3 knob** — current, runs MicroPython + LVGL
- **40" touchscreen** — Python client with full UI, knob becomes a remote
- **iPhone/Android** — touch dial replaces physical encoder, same WebSocket protocol

The protocol stays the same. Only the transport and UI layer change.

## License

MIT
