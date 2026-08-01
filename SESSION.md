# Session Summary — Smart Knob Controller

Saved session state for continuity between work sessions.

## Objective
- Finish the Smart Knob system: PC server (`fs1/server.py`) drives bootstrap → config → launcher with literal-GUID machine configs; browser sim bridged via `testKnob.py`.
- Latest task: make the LVGL WASM sim (`lvgl.html` iframe) actually run `bootstrap.py` and `launcher.py` end-to-end (bootstrap → config_ack → launcher home screen → command loop).

## Important Details
- Knob-as-host framing (user): "the knob is the host — it controls the pc. the pc is the client… a very symbiotic relationship."
- Design rule: server holds no app logic; machine list is not a separate protocol message. `server.py` reads `fs1/machines/*.json`, injects `_AVAILABLE_MACHINES`, `_SERVER_VERSION`, and (per active work) `_MACHINE_GUID` into the bootstrap preamble.
- Machine configs = literal GUID filenames (`sim-dev-001.json`, `pc-abcd1234.json`, `mac-m1-max.json`); schema includes `location` (Simulator/Office/Home).
- `SERVER_VERSION = "0.1.0"` at top of `server.py`; bootstrap reports it as `server_version` and resolves the selected machine's `location` from `_AVAILABLE_MACHINES`.
- The code editor textarea in `index.html` is a manual editor. Server-pushed code now populates it too (`codeEditor.value = code`) so it mirrors what runs in the sim.
- The sim runs bootstrap/launcher inside the `lvgl.html` iframe; the bottom `current-file` bar shows `bootstrap.py` / `config — Home Mac` / `launcher.py`.
- Bridge root cause (FIXED): `testKnob.py` `_connect_to_server` left `s.settimeout(5)` after handshake → blocking reads in S→B pipe timed out → teardown. Fix: `s.settimeout(None)` after handshake.
- `_recv_ws_frame` broad `except Exception: return None` treated bridge timeout as connection dead → disconnect. Now answers pings (0x09→0x8A), skips other non-text frames, returns None only on close/error.
- lvgl.html races (FIXED):
  1. Message gate used `typeof mp_js_do_str !== 'undefined'` — true before `mp_js_init` ran → early code fed to uninitialized interpreter and lost. Fix: `mp_interp_ready` flag set only after interpreter init promise completes, then flush queue.
  2. Parent WS connects faster than the iframe loads → `postMessage` into not-yet-loaded iframe silently dropped. Fix: parent stores latest execute code when iframe not ready (`_lastServerCode`), resends on `mp_ready`; iframe ACKs with `{type:'code_received'}` to clear it (avoids duplicates). Cache-buster bumped to `lvgl.html?v=6` (was v=5).
- **Build discrepancy (KEY FINDING):** the browser was running a STALE `micropython.js`+`firmware.wasm` (has `os`/`uos`, lacks `time`/`utime`) while disk has the OPPOSITE (`time`/`utime` yes, `os`/`uos`/`machine` NO). Verified with a Node harness that runs the real WASM: `import os`→FAIL, `uos`→FAIL, `machine`→FAIL, `time`/`utime`/`gc`/`json`/`lvgl`→OK on disk build. `strings` presence of qstrs does NOT prove importable modules. Now cache-busted: `micropython.js?v=2`, `firmware.wasm?v=2` via `locateFile`.
- **Node harness (`/tmp/knob-test/`):** `micropython.patched.js` = copy of static/micropython.js with 2 patches (inject `wasmBinary=require("fs").readFileSync(__dirname+"/firmware.wasm")`, drop `setTimeout(()=>window.startRunning(),0)`); `harness.js` requires it with browser-global stubs (screen/window/document/canvas), waits for `Module.asm`, then calls `mp_js_init(1024*1024)` + `mp_js_do_str(py)` — replicates lvgl.html exactly. Usage: `node harness.js run_launcher.py`; MicroPython `print` redirected to stderr via `builtins.print = lambda *a,**k: sys.stderr.write(...)` because default print needs the `micropython-print` event.
- lvgl.html iframe init (unchanged contract): `mp_js_init(1024*1024)`, `lv.sdl_window_create(480,320)`, `mp_ready` postMessage, render timer `mpEnqueue('lv.timer_handler()')` @16ms, canvas touch → `on_touch(x,y,pressed)`.
- launcher.py sim incompatibilities (FIXED, verified by harness):
  - Module-scope `import os`/`import utime` are build-dependent → guarded: `try: import os / except: os=None`; `try: import utime / except: try: import time as utime / except: _SimTime noop`. `sleep_ms` uses `utime.sleep_ms`.
  - `from hardware import Hardware` → try/except with `_SimHardware` stub + `self.sim_mode = True`.
  - `from plugin_manager import PluginManager` → try/except with stub (empty plugin list).
  - Fonts: WASM only ships `font_montserrat_14/16/24` (NOT `28`/`10`) → `FONT_NAME`/`FONT_ICON`/`FONT_SMALL` getattr-fallback constants.
  - Symbols: this binding exposes `lv.SYMBOL.HOME` etc., NOT `lv.SYMBOL_HOME` → `_symbol(*names)` tries `lv.SYMBOL_X` then `lv.SYMBOL.X`; `ICON_SYMBOLS` keys use names known to exist (AUDIO/EDIT/SHUFFLE/SETTINGS/WIFI).
  - `lv.OBJ_FLAG` does NOT exist in the sim binding and `clear_flag`/`add_flag` HANG it → `_clear_flag`/`_add_flag` helpers gate on `hasattr(lv,'OBJ_FLAG')` (skip in sim).
  - LVGL indev API is method-style: `indev.set_type(...)` / `indev.set_read_cb(...)` (NOT `indev.type=`/`indev.read_cb=`).
  - `lv.obj()` crashes without a display — sim always creates the SDL display (lvgl.html) before running launcher.
  - Machine config: in sim, launcher picks up `_MACHINE_CONFIG` injected by the config step → home screen shows "Home Mac".
  - Sim mode skips the blocking `_main_loop` (host JS render timer drives `lv.timer_handler()` every 16ms); real hardware still runs full loop.
  - **`run()` was never invoked anywhere** → added `if __name__ == '__main__': Launcher().run()` (server sends launcher as an executed file, so `__name__=='__main__'`).
- Server logs → `/workspaces/knob-controller/server.log` (git-ignored, cleared on restart via `restart-server.sh`); bridge logs → `/tmp/bridge.log`. Both run `python3 -u`.
- Do NOT `pkill -f` with process path (kills the shell); kill by PID from `ss -ltnp`.
- `testKnob.py` HTTP bind needs `ReuseTCPServer(socketserver.TCPServer)` with `allow_reuse_address = True`.
- Server protocol flow: `execute bootstrap` → `bootstrap_response` (machine/guid/version/location) → match GUID to config → `config` glue (defines `_MACHINE_CONFIG` in sim, prints `config_ack`) → `config_ack` → `execute launcher.py` → command loop. Server also logs `[server] Injected 3 machines (v0.1.0) into bootstrap` and `Knob: machine=... guid=... version=... location=...`.

## Work State
### Completed
- Right panel resizable: `.side-panel` width 520px + drag handle `#resize-handle` (not persisted; 340px min, 85% max).
- Bridge 5s-socket-timeout fix verified on replica stack then applied to real files.
- lvgl.html interpreter-init race fix (`mp_interp_ready` + queue flush).
- lvgl.html dropped-bootstrap race fix (`_lastServerCode` resend on mp_ready + `code_received` ACK + `?v=5`, now `?v=6`).
- Editor now mirrors server-executed code.
- `restart-server.sh` (kills by port-PID, clears server.log on restart) created + executable + verified.
- `bootstrap.py` reports `server_version` + `location`; `server.py` injects `_SERVER_VERSION` and logs version/location.
- `launcher.py` made sim-compatible AND executable: guarded `os`/`utime` imports, `_SimHardware`, stub `_SimPluginManager`, font fallbacks, `_symbol` for `lv.SYMBOL.X`, `_obj_flag`/`_clear_flag`/`_add_flag` gating, method-style indev (`set_type`/`set_read_cb`), `if __name__=='__main__': Launcher().run()`. `py_compile` passes.
- **Node harness built (`/tmp/knob-test/`)** — runs the real firmware.wasm in Node with the browser-init sequence replicated; used to find the exact importable-module set and every LVGL API incompatibility.
- **Harness-verified: launcher runs to completion** with output: `Simulator mode — hardware module not available` → `HID init failed` → `WebSocket init failed` → `Simulator mode — plugin_manager module not available` → `Using config from server: Home Mac` → `Enabled plugins: []` → `Ready. Entering main loop.` → `Simulator mode — host render loop drives LVGL.`
- Cache-busters added so browser uses the disk build: `micropython.js?v=2`, `firmware.wasm?v=2` (locateFile), iframe `lvgl.html?v=6`.
- Last confirmed server run: bootstrap → config (Home Mac) → config_ack → launcher.py sent → "Bootstrap complete — entering command loop".
- Root README.md + `fs2/README.md` rewritten (fs2 = firmware-build-only); `fs1/test-env/README.md` patched.
- `fs2/protocol/messages.py` + `__init__.py` rewritten to real message types; import verified.
- Commit `604bd5e2` pushed. Legacy constants in `fs1/pc/knob_client/main.py` (lines 26–32) removed.

### Active / Pending
- Server restarted and listening on :8765; waiting for the user's browser to reconnect. Browser must HARD-REFRESH `http://localhost:8080` (Ctrl+Shift+R) so the iframe + `micropython.js?v=2` + `firmware.wasm?v=2` load fresh (this swaps the stale build for the disk build the harness validated).
- Need to confirm the sim home screen now renders black canvas + "Home Mac" label (launcher sim mode) and no further Tracebacks in browser log.
- Encoder navigation to LVGL not yet wired: parent encoder events currently go WS → server, never into the sim; sim `_SimHardware.encoder = None` so `_main_loop` polling is moot.
- Sim diagnostics still in place (WS close codes, iframe load/unload postMessage events) — removable once testing settles.
- Uncommitted changes pending: `.gitignore` (server.log), `fs1/server.py`, `fs1/test-env/testKnob.py`, `fs1/test-env/index.html`, `fs1/test-env/static/lvgl.html`, `fs1/bootstrap.py`, `fs1/launcher.py`, `restart-server.sh`, plus `SESSION.md`.

### Blocked
- (none) — launcher boots and completes in the harness; awaiting live-browser confirmation after hard refresh.

## Next Move
1. User hard-refreshes sim (in progress). Confirm in browser log: `[launcher] Simulator mode — hardware module not available`, `[launcher] Using config from server: Home Mac`, `[launcher] Ready... Simulator mode — host render loop drives LVGL.` and canvas shows "Home Mac". If any import/API error appears, iterate via the Node harness first (`node /tmp/knob-test/harness.js run_launcher.py`).
2. If clean, commit pending changes (launcher sim-compat, iframe race fixes, cache-busters, harness docs, server_version/location injection, restart script).
3. Future: wire browser encoder → sim (`on_encoder`/LVGL indev) so icon navigation works; sync editor↔server file handling.

## Relevant Files
- `/workspaces/knob-controller/fs1/test-env/static/lvgl.html`: WASM iframe; `mp_interp_ready` gate + queue flush; `code_received` ACK; `micropython.js?v=2` + `locateFile ?v=2`; 16ms `lv.timer_handler()` render pump; `on_touch`.
- `/workspaces/knob-controller/fs1/test-env/index.html`: resizable right panel; editor mirrors server code; `_lastServerCode` resend-on-`mp_ready`; `code_received` clears; `#current-file` bar; `?v=6` iframe.
- `/workspaces/knob-controller/fs1/test-env/testKnob.py`: transparent bridge (:8080 + :8766 → :8765); `s.settimeout(None)` after handshake; ReuseTCPServer.
- `/workspaces/knob-controller/fs1/server.py`: `SERVER_VERSION = "0.1.0"`; preamble injection; logs version + location.
- `/workspaces/knob-controller/fs1/bootstrap.py`: resolves `location` from `_AVAILABLE_MACHINES` by GUID; reports `server_version`.
- `/workspaces/knob-controller/fs1/launcher.py`: sim-compatible + executable launcher (guarded os/utime, hardware/plugin fallbacks, font/symbol/flag fallbacks, method-style indev, `__main__` run hook).
- `/tmp/knob-test/`: Node harness — `micropython.patched.js`, `harness.js`, `globals.js`, `run_launcher.py`, t*.py probes, `firmware.wasm` copy.
- `restart-server.sh`: kills server by port-PID, restarts with cleared server.log.
- `/workspaces/knob-controller/server.log` (server output), `/tmp/bridge.log` (bridge output).
