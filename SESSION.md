# Session Summary — Smart Knob Controller

Saved session state for continuity between work sessions.

## Objective
- Finish the Smart Knob system: PC server (`fs1/server.py`) drives bootstrap → config → launcher with literal-GUID machine configs; browser sim bridged via `testKnob.py`.
- **Current milestone: apps load + execute on select, with visible proof on the page.** Selecting Volume in the sim runs its `plugin.py` (harness + browser console verify `[volume] Active`). User complained the page gave no visual proof ("bottom left says launcher — not volume; apps look visually similar") → added `app_loaded`/`app_closed` JSON messages from the launcher that drive the `#current-file` bar to `volume.py — running` and log "App loaded: Volume".

## Latest milestone — apps in a clock formation (verified in harness)
- App source of truth = the machine config's `apps` list (from `_MACHINE_CONFIG`), merged with `/fs1/plugins/*/manifest.json` metadata. Server injects the merged list into the launcher as `_SERVER_APPS` (server.py `_build_app_list` reads machine `apps` + `_load_plugin_manifests` from disk); launcher prefers `_SERVER_APPS`, falls back to `_MACHINE_CONFIG['apps']`, then to scanning `/fs1/plugins`.
- Home screen: apps placed by `_clock_positions(n)` — radius 110, start at 12 o'clock, clockwise: 4 apps → (0,-110),(110,0),(0,110),(-110,0); 6 apps → (0,-110),(95,-55),(95,55),(0,110),(-95,55),(-95,-55). Machine name ("Home Mac") stays centered. Temp icon = first letter (e.g. V, M, B, S) in a 72px circle; name below.
- Sim input routing: launcher now defines module-level `on_encoder(delta)`, `on_button()`, `on_touch(x,y,pressed)` that dispatch to the singleton via `_launcher_instance` (set in `run()`). Browser's existing `sendEncoder`/`sendButton`/canvas-touch call these directly — no bridge/HTML changes needed.
- Encoder on home = `home_selected = (home_selected + delta) % len(apps)` (wraps). Tap icon = select + `_enter_plugin`. In sim, `_enter_plugin` shows a placeholder plugin screen (app name + "tap to return"); tapping anywhere or button returns home. On real hardware it still goes through `plugin_mgr.activate`.
- **Display made square: `lv.sdl_window_create(360, 360)`** (was 480×320) so canvas↔LVGL coords are 1:1 and touch hit-testing (center 180,180, radius 36) lines up with the 360×360 round canvas. Verified the square display works in the harness.
- Manifest icon scaffold: `_build_app_list` copies `icon` and `icon_data` (base64 PNG, future) into each app entry; launcher stores them but renders the first letter for now because the sim build has NO `lv.png` decoder (only `lv.image` widget, no runtime PNG decode).
- Harness-verified full interaction: `on_encoder(1)`→1, `+1`→2, `-1`→1; `on_touch(180,70,1)`→"Launching app: Volume"→screen `plugin`; `on_touch(0,0,1)`→`home`; `on_button()`→`plugin`. Also verified `_SERVER_APPS` path with 6 apps.
- iframe cache-buster bumped to `lvgl.html?v=7` (lvgl.html display-size change).
- **Bootstrap now gated on a Start button** (user bug: "once the page renders, bootstrap is done, and I never get a chance to set the location"): server auto-sent bootstrap on connect and the dropdown's first-machine default was applied before the user could interact. Fix in `index.html`: `execute` messages with `file === 'bootstrap.py'` are stored raw in `window._pendingBootstrap` (override NOT baked in), a green `#btn-start` enables, and Start applies the dropdown's `_MACHINE_GUID` override at press time and runs it. Non-bootstrap executes still run immediately. Changing the dropdown after Start requires a page reload (fresh WS → fresh gated bootstrap).
- **Selecting an app loads + executes its code (verified: volume).** Server `_build_app_list` now embeds each plugin's `plugin.py` source as `code` in the app entry (read from `fs1/plugins/<id>/plugin.py`); launcher `_enter_plugin` runs it via `exec(code, plugin_module)` with `_font`/`_symbol` helpers injected, calls `setup(container, {'hid':…, 'ws_client':…})` + `start()`, and routes `on_encoder`/`on_button`/`on_data_update`/`stop()` to the live module. Real-hardware fallback reads `/fs1/plugins/<id>/plugin.py`. Apps with no code (e.g. `music`) still get the placeholder screen.
- **Plugin sim-compat:** all 4 plugins now use `_font('font_montserrat_20','font_montserrat_24','font_montserrat_16')` and `_symbol('SYMBOL_VOLUME_FULL','SYMBOL_AUDIO')` etc. because the sim build lacks `font_montserrat_20/28` and `SYMBOL_VOLUME_FULL`/`SYMBOL_BRIGHTNESS`/`SYMBOL_REFRESH`/`SYMBOL_ZOOM_IN` (only `lv.SYMBOL.AUDIO/SHUFFLE/EDIT/LEFT`…). `arc.clean()` DOES exist in the binding. Helpers are injected by the launcher at exec time, so plugins stay standalone-ish.
- **Bug caught by harness:** `_load_apps` originally copied only id/name/icon/icon_data from the server app entry (dropping `code`, `version`, `settings`) → apps fell back to the placeholder. Now merges all non-null server fields.
- Harness-verified volume flow: tap Volume icon → `[launcher] Launching app: Volume` → `[volume] Active` → encoder +3 → 50→59 → -100 → clamped 0 → tap → `[volume] Stopped` → home. App message size ~37KB (launcher + embedded plugin sources), fine over WS.
- **Running-app visibility (new):** launcher prints `{"type":"app_loaded","app":"volume","name":"Volume"}` after a successful enter (also after the no-code placeholder screen) and `{"type":"app_closed","app":"volume"}` in `_go_home`. `index.html` stdout handler parses these: `app_loaded` sets the `#current-file` bar to `<app>.py — running` + logs "App loaded: <name>" (ok color); `app_closed` resets it to `launcher.py`. They are NOT forwarded to the bridge WS (server.py `_route_message` still handles both for clean logging: "App running: …" / "App stopped: …").
- Harness-verified both messages: enter Volume → `{"app":"volume","name":"Volume","type":"app_loaded"}` → tap return → `[volume] Stopped` + `{"app":"volume","type":"app_closed"}` → home.
- Note: entering an app with an `on_button` (e.g. Volume = mute toggle) means the button does NOT return home; tapping the plugin screen does (`_handle_touch` → `_go_home`).

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
- **Harness-verified: launcher runs to completion** with output: `Simulator mode — hardware module not available` → `HID init failed` → `WebSocket init failed` → `Simulator mode — plugin_manager module not available` → `Using config from server: Home Mac` → `Apps: [...]` → `Ready. N app(s). Entering main loop.` → `Simulator mode — host render loop drives LVGL.`
- Cache-busters added so browser uses the disk build: `micropython.js?v=2`, `firmware.wasm?v=2` (locateFile), iframe `lvgl.html?v=6`.
- Last confirmed server run: bootstrap → config (Home Mac) → config_ack → launcher.py sent → "Bootstrap complete — entering command loop".
- Root README.md + `fs2/README.md` rewritten (fs2 = firmware-build-only); `fs1/test-env/README.md` patched.
- `fs2/protocol/messages.py` + `__init__.py` rewritten to real message types; import verified.
- Commit `604bd5e2` pushed. Legacy constants in `fs1/pc/knob_client/main.py` (lines 26–32) removed.

### Active / Pending
- Server restarted (pid 228377 → restarted with `app_loaded`/`app_closed` handling) and listening on :8765. User hard-refreshes `http://localhost:8080` → pick machine → Start Bootstrap.
- Confirm in browser: tap/click Volume → file bar flips to `volume.py — running`, console logs `App loaded: Volume`; the arc UI shows (that's the proof apps run); spin encoder → % changes; tap canvas → bar back to `launcher.py`, `App closed: volume`.
- Real app icons: source PNGs → base64 into each plugin `manifest.json` `icon_data` field (scaffold reads it). Rendering needs a PNG decode path in the sim build (none today) — alternatives: LVGL C-image `.c` files, or a sprite font.
- Future: re-bootstrap mid-connection (server currently one-shot per connection; changing machine needs a page reload).
- Sim diagnostics still in place (WS close codes, iframe load/unload postMessage events) — removable once testing settles.
- Uncommitted: this milestone's launcher/server/lvgl.html/index.html changes + SESSION.md.

### Blocked
- (none) — apps execute inside the sim and the launcher now reports which app is running; awaiting live-browser confirmation of the file-bar/`App loaded` indicator after a hard refresh.

## Next Move
1. User hard-refreshes the sim and presses Start Bootstrap after picking a machine.
2. Confirm: tap Volume → file bar `volume.py — running` + console `App loaded: Volume` + arc UI appears; encoder changes %, tap canvas → bar `launcher.py` + `App closed: volume`.
3. If clean, commit ("apps load + execute visibly: launcher emits app_loaded/app_closed; page file-bar + log shows the running app").
4. Future: real base64 PNG icons (needs a decode path), mid-connection re-bootstrap, wire plugin.py HID/WS effects (volume actually changing system volume in sim isn't possible — the arc + routing is the deliverable).

## Relevant Files
- `/workspaces/knob-controller/fs1/test-env/static/lvgl.html`: WASM iframe; `mp_interp_ready` gate + queue flush; `code_received` ACK; `micropython.js?v=2` + `locateFile ?v=2`; 16ms `lv.timer_handler()` render pump; `on_touch`; square `lv.sdl_window_create(360, 360)`.
- `/workspaces/knob-controller/fs1/test-env/index.html`: resizable right panel; editor mirrors server code; `_lastServerCode` resend-on-`mp_ready`; `code_received` clears; `#current-file` bar (now also driven by `app_loaded`/`app_closed`); `?v=7` iframe.
- `/workspaces/knob-controller/fs1/test-env/testKnob.py`: transparent bridge (:8080 + :8766 → :8765); `s.settimeout(None)` after handshake; ReuseTCPServer.
- `/workspaces/knob-controller/fs1/server.py`: `SERVER_VERSION = "0.1.0"`; preamble injection; `_build_app_list` merges machine `apps` + plugin manifests → injects `_SERVER_APPS` into launcher; `_route_message` handles `app_loaded`/`app_closed`.
- `/workspaces/knob-controller/fs1/bootstrap.py`: resolves `location` from `_AVAILABLE_MACHINES` by GUID; reports `server_version`.
- `/workspaces/knob-controller/fs1/launcher.py`: sim-compatible + executable launcher; `_load_apps`/`_load_plugin_manifests`; `_clock_positions` clock formation; first-letter temp icons; module-level `on_encoder`/`on_button`/`on_touch` → `_launcher_instance`; `_enter_plugin` execs embedded `code` (+ `_font`/`_symbol` helpers) and emits `app_loaded`; `_go_home` emits `app_closed`; `__main__` run hook.
- `/tmp/knob-test/`: Node harness — `micropython.patched.js`, `harness.js`, `globals.js`, `run_launcher.py`, t*.py probes, `firmware.wasm` copy.
- `restart-server.sh`: kills server by port-PID, restarts with cleared server.log.
- `/workspaces/knob-controller/server.log` (server output), `/tmp/bridge.log` (bridge output).
