# Smart Knob Test Environment

Browser-based simulator for testing the Smart Knob bootstrap → config → launcher protocol without physical hardware.

## Architecture

```
Browser ──WS :8766──► testKnob.py ──WS :8765──► server.py
                        (pipe)
```

`testKnob.py` is a **transparent bridge** — it serves the simulator website (HTTP :8080) and forwards all WebSocket messages bidirectionally between the browser and `server.py` (WS :8765). It has **zero logic** — no bootstrap protocol, no config matching, no command routing.

## Quick Start

```bash
cd ../../                        # back to knob-control/
python3 server.py &               # Real PC server (WS :8765)
cd fs1/test-env
python3 testKnob.py               # Test bridge (HTTP :8080, WS :8766)
```

Open http://localhost:8080 in your browser.

## Testing the Full Flow

1. Start both services (above)
2. Open http://localhost:8080
3. Watch the WebSocket log in the side panel:
   - `{"type":"execute","code":"..."}` — bootstrap sent by server
   - `{"type":"bootstrap_response",...}` — knob reports GUID
   - `{"type":"config","config":{...}}` — server sends matched config
   - `{"type":"config_ack","status":"ok"}` — knob accepts
   - `{"type":"execute","code":"..."}` — launcher sent
   - `{"type":"launcher_ready",...}` — UI is live
4. Use arrow keys / buttons to navigate and select apps

The **Machine** dropdown is populated from the `machines` array in the bootstrap `execute` message — it shows each config's name and location (e.g. `Home Mac (Home)`), and its `machine_guid` value (e.g. `mac-m1-max`) is injected as the `_MACHINE_GUID` override.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| ← / ↓ | Rotate encoder CCW |
| → / ↑ | Rotate encoder CW |
| Space | Press encoder button |
| Ctrl+Enter | Run code in editor |

## File Structure

```
test-env/
├── testKnob.py           HTTP :8080 + transparent WS bridge (:8766)
├── index.html            Browser simulator UI
├── static/
│   ├── lvgl.html         LVGL + MicroPython WASM iframe
│   └── micropython.js    MicroPython WASM runtime
├── pc_client_adapter.py  Legacy: standalone WS client tool
└── README.md
```

(bootstrap.py, launcher.py, and machines/ — GUID-named .json files — live in knob-control/ alongside server.py)
