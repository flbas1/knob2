# Smart Knob Test Environment

Browser-based simulator for testing Smart Knob plugins without physical hardware.

## Quick Start

```bash
cd fs1/test-env
python server.py
```

Open http://localhost:8080 in your browser.

## Features

- **LVGL MicroPython Simulator**: Runs MicroPython + LVGL in the browser via WebAssembly (from sim.lvgl.io)
- **Virtual Encoder**: Drag the knob visual, use arrow keys, or click CCW/CW buttons
- **Touch Simulation**: Click on the circular display area to simulate touch
- **WebSocket Bridge**: Connects browser simulator to PC client for end-to-end testing
- **Code Editor**: Write and run MicroPython + LVGL code directly in the browser
- **Console**: Shows debug output from MicroPython and WebSocket messages

## Architecture

```
Browser (index.html)
  ├── MicroPython WASM (sim.lvgl.io)  → LVGL rendering
  ├── Virtual Encoder Controls          → Encoder events
  ├── Code Editor                       → Execute Python code
  └── WebSocket Client ──────────────→ Bridge Server (port 8765)
                                           │
PC Client (knob_client) ←─────────────────┘
  ├── System Volume Control
  ├── Home Assistant API
  └── Mouse/Keyboard HID
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ← / ↓ | Rotate encoder CCW |
| → / ↑ | Rotate encoder CW |
| Ctrl+Enter | Run code in editor |

## Testing a Plugin

1. Open the simulator in your browser
2. Click "Load Plugin" or paste plugin code into the editor
3. Use the virtual encoder to interact with the plugin
4. Check the WebSocket log to verify messages are sent to the PC client

## Connecting to PC Client

Start the PC client on your computer:

```bash
cd fs1/pc
python -m knob_client.main --port 8765
```

The bridge server will automatically forward messages between the browser and PC client.

## File Structure

```
test-env/
├── server.py          # Python WebSocket bridge + HTTP server
├── index.html         # Browser simulator with LVGL + controls
├── README.md          # This file
└── static/            # (Optional) Static LVGL MicroPython files
```
