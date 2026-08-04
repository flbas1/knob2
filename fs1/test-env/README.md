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
cd ../                           # back to fs1/
python3 server.py &               # Real PC server (WS :8765)
cd test-env
python3 testKnob.py               # Test bridge (HTTP :8080, WS :8766)
```

Open http://localhost:8080 in your browser.

## Testing the Full Flow

1. Start both services (above)
2. Open http://localhost:8080
3. Watch the WebSocket log in the side panel:
   - `{"type":"identify",...}` — server identifies itself (machine guid on the USB link)
   - `{"type":"execute","code":"..."}` — bootstrap sent by server (sim-only; the real knob reads its own /fs1)
   - `{"type":"bootstrap_response",...}` — knob reports GUID + chosen **location**
   - `{"type":"config","config":{...}}` — server sends config matched by location
   - `{"type":"config_ack","status":"ok"}` — knob accepts
   - `{"type":"execute","code":"..."}` — launcher sent
   - `{"type":"launcher_ready",...}` — UI is live
4. Use arrow keys / buttons to navigate and select apps

The location picker lives in `bootstrap.py` and renders on the knob display —
the **Machine dropdown is gone**. The picker behaves like the real knob:

- **Default** — shows every location; rotate/press/tap to choose.
- **Machine GUID filled in** (the optional text field above) — mimics the USB
  path (the server's `identify` message on real hardware): that machine's
  location(s) are preselected, auto-confirmed when unique.
- The simulator has no wifi, so the wifi-filter path (`bootstrap.py` scanning
  `network.WLAN`) never triggers in the browser — it only runs on the ESP32.
- The sim has no /fs1, so bootstrap uses the **server-injected location list**
  (`_AVAILABLE_MACHINES`). The real knob reads `/fs1/locations` directly — the
  injected list is a sim-only fallback.

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

(bootstrap.py, launcher.py, and locations/ — location-named .json files — live in fs1/ alongside server.py)
