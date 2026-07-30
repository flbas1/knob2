# Knob Control

A portable smart knob that adapts to whatever computer it's plugged into.

The knob is the host. The PC is a client. You take the knob from home to work, and it automatically loads the right configuration.

## Architecture

```
┌──────────────────────────────────────────┐
│           THE KNOB (Host)                │
│                                          │
│  MicroPython + LVGL Runtime              │
│  ├── launcher.py      (home screen)     │
│  ├── plugin_manager.py (load/switch)    │
│  ├── lib/                                │
│  │   ├── sh8601.py     (QSPI display)   │
│  │   ├── cst816.py     (touch driver)   │
│  │   ├── encoder.py    (GPIO polling)   │
│  │   ├── hid.py        (USB HID)        │
│  │   └── ws_client.py  (WebSocket)      │
│  └── plugins/         (from fs1)        │
│      ├── volume/                       │
│      ├── zoom/                         │
│      ├── scroll/                       │
│      └── brightness/                   │
│                                          │
│  USB HID ──────────────→ Host PC         │
│  WebSocket ────────────→ PC Client       │
└──────────────────────────────────────────┘
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

## Plugin System

Plugins are Python scripts stored on the knob's FAT32 partition (`fs1`). Each plugin defines:

- **manifest.json**: Metadata (name, icon, settings)
- **plugin.py**: LVGL UI and behavior (setup, start, stop, on_encoder, on_button, on_data_update)

### Plugin API

```python
def setup(parent, hardware):
    """Create LVGL widgets. Called once when loaded."""
    pass

def start():
    """Called when plugin becomes active."""
    pass

def stop():
    """Called when plugin is deactivated."""
    pass

def on_encoder(delta):
    """Called on encoder rotation. delta > 0 = CW, < 0 = CCW."""
    pass

def on_button():
    """Called on encoder button press."""
    pass

def on_data_update(data):
    """Called when PC sends data_update."""
    pass
```

## Machine Detection

Each machine (computer) has a config file in `fs1/machines/`:

```json
{
    "name": "Work Laptop",
    "platform": "windows",
    "plugins": ["volume", "zoom", "scroll"]
}
```

When the knob connects to a PC, the PC client identifies itself. The knob loads the matching config and enables only the specified plugins.

## Build & Flash

### Prerequisites

- ESP-IDF v5.4+
- Python 3.10+

### Build

```bash
cd knob-control
idf.py set-target esp32s3
idf.py menuconfig    # Configure WiFi, HID, etc.
idf.py build
```

### Flash

```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

## PC Client

The PC client bridges the knob to system services:

```bash
cd fs1/pc
pip install -e .
knob-client  # Auto-discovers knob via WebSocket
```

### Environment Variables

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_access_token"
```

## Test Environment

Browser-based simulator for testing plugins without hardware:

```bash
cd fs1/test-env
python server.py
# Open http://localhost:8080
```

## Project Structure

```
knob-control/
├── CMakeLists.txt              # ESP-IDF project file
├── sdkconfig.defaults          # Board config (16MB flash, OPI PSRAM)
├── partitions.csv              # Flash partition layout
├── main.py                     # MicroPython entry point
├── launcher.py                 # Home screen + event loop
├── lib/                        # Frozen MicroPython modules
│   ├── hardware.py             # Hardware init
│   ├── encoder.py              # Non-quadrature encoder
│   ├── cst816.py               # Touch driver
│   ├── sh8601.py               # Display driver (stub)
│   ├── hid.py                  # USB HID composite device
│   ├── ws_client.py            # WebSocket client
│   └── plugin_manager.py       # Plugin lifecycle management
├── fs1/                        # FAT32 partition (user-accessible)
│   ├── machines/               # Per-machine configs
│   ├── plugins/                # Python plugin scripts
│   ├── pc/                     # PC client (Python)
│   ├── settings.json           # Global settings
│   └── test-env/               # Browser simulator
├── protocol/
│   └── messages.py             # Shared JSON protocol
└── firmware/
    └── (C extensions if needed)
```

## License

MIT
