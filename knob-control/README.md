# Smart Knob Controller

A portable smart knob with a PC server that adapts to whatever computer it's plugged into. The **PC is the server** — it runs the bootstrap protocol, identifies the knob, sends the right config, and routes app commands (volume, brightness, zoom, scroll) to system services.

## Architecture

```
┌─────────────────────┐           ┌──────────────────────────────────┐
│   THE KNOB          │           │      PC SERVER (server.py)       │
│                     │           │                                  │
│  MicroPython + LVGL │           │  Bootstrap protocol:             │
│  ├─ bootstrap.py*   │  WS :8765 │  1. Send bootstrap.py → knob    │
│  ├─ launcher.py*    │◄────────►│  2. Knob responds with GUID      │
│  ├─ plugin_*.py*    │           │  3. Match config → send config   │
│                     │           │  4. Knob acks → send launcher.py │
│  *sent by server    │           │                                  │
│                     │           │  Command routing:                │
│                     │           │  volume, brightness, scroll, zoom│
│                     │           │  → KnobClient platform handlers  │
└─────────────────────┘           └──────────────────────────────────┘
                                           │
                                           │ WS :8766
                                           ▼
                                 ┌─────────────────────┐
                                 │  testKnob.py         │
                                 │  (test bridge only)  │
                                 │  HTTP :8080 + pipe   │
                                 │                      │
                                 │  Serves index.html   │
                                 │  Forwards WS raw     │
                                 │  No logic at all     │
                                 └─────────────────────┘
                                           │
                                           ▼
                                 ┌─────────────────────┐
                                 │  Browser Simulator   │
                                 │  (if needed)         │
                                 └─────────────────────┘
```

### Two-Server Model

| Server | Port | Role |
|--------|------|------|
| `server.py` | 8765 (WS) | **Real PC server** — bootstrap flow, machine configs, command dictionary, platform actions |
| `testKnob.py` | 8080 (HTTP) + 8766 (WS) | **Test bridge only** — serves browser sim, pipes WS messages raw to server.py. Zero logic. |

### Bootstrap Flow (server-driven)

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
   │  (glob pattern: SIM-*, MAC-*, etc)   │
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
   │  {"type":"app_selected","app":"vol"}"│
   │◄─────────────────────────────────────│
   │  {"type":"data_update",              │
   │    "data":{"value":42}}              │
   │─────────────────────────────────────►│
```

## Hardware

**Waveshare ESP32-S3-Knob-Touch-LCD-1.8**

- ESP32-S3R8 (16MB Flash, 8MB PSRAM OPI)
- SH8601 AMOLED QSPI 360x360 display
- CST816 capacitive touch (I2C 0x15)
- Non-quadrature encoder (two micro-switches)
- DRV2605 haptic driver
- PCM5100A audio DAC
- USB-C with CH334 hub

## Quick Start

### Real PC Server

```bash
cd knob-control
python3 server.py
# Listens on WS :8765 for knob connections
```

### Test Simulator (browser-based)

```bash
cd knob-control
python3 server.py &                    # Real server (background)
python3 fs1/test-env/testKnob.py       # Test bridge
# Open http://localhost:8080
```

The browser connects to testKnob.py's WS (:8766), which pipes everything to server.py (:8765). The full bootstrap flow runs transparently.

### Physical Knob

The ESP32-S3 connects to Wi-Fi, then opens a WebSocket to `server.py:8765`. The bootstrap flow starts immediately.

## Machine Configs

Each machine has a config file in `knob-control/machines/` named after its literal GUID:

```json
{
    "name": "Development Sim",
    "machine_guid": "sim-dev-001",
    "location": "Simulator",
    "haptic": false,
    "sound": false,
    "backlight": 100,
    "apps": [
        {"id": "volume",    "name": "Volume"},
        {"id": "brightness","name": "Brightness"}
    ]
}
```

The filename is `{machine_guid}.json` (e.g. `sim-dev-001.json`). The server injects the machine list as `_AVAILABLE_MACHINES` into bootstrap.py before sending, and the test sim populates its Machine dropdown from the `machines` field on the `execute` message.
`location` describes where the machine lives (Simulator, Office, Home, etc.).

## Command Dictionary

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

## Build & Flash

### Prerequisites

- ESP-IDF v5.4+
- Python 3.10+

### Build

```bash
cd knob-control
idf.py set-target esp32s3
idf.py menuconfig
idf.py build
```

### Flash

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

## Environment Variables

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_access_token"
```

## Project Structure

```
knob-control/
├── server.py                PC server (bootstrap + command routing)
├── bootstrap.py             Sent to knob — probes identity, reports GUID
├── launcher.py              Sent to knob — builds app-launcher UI
├── machines/                Per-location config JSON files
│   ├── sim-dev-001.json
│   ├── pc-abcd1234.json
│   └── mac-m1-max.json
├── CMakeLists.txt           ESP-IDF project
├── sdkconfig.defaults       Board config
├── partitions.csv           Flash partitions
├── boot.py                  ESP32 boot
├── main.py                  MicroPython entry point on knob
├── lib/                     Frozen MicroPython modules
│   ├── hardware.py
│   ├── encoder.py
│   ├── cst816.py
│   ├── sh8601.py
│   ├── hid.py
│   ├── ws_client.py
│   └── plugin_manager.py
├── fs1/                     FAT32 partition (user-accessible)
│   ├── machines/            (deprecated — configs live in ../machines/)
│   ├── plugins/             Plugin scripts
│   ├── pc/                  PC-side Python libs
│   │   ├── setup.py
│   │   ├── knob_client/
│   │   │   └── main.py     KnobClient (platform handlers)
│   │   └── ...
│   └── test-env/            Browser-based test simulator
│       ├── testKnob.py      Transparent WS bridge (no logic)
│       ├── index.html       Simulator UI
│       ├── static/
│       │   ├── lvgl.html    LVGL + MicroPython WASM iframe
│       │   └── micropython.js
│       └── pc_client_adapter.py  (legacy: standalone test tool)
└── protocol/
    └── messages.py          Shared message types
```

## License

MIT
