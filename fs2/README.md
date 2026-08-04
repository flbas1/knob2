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
| `main.py` | MicroPython entry point — runs `/fs1/bootstrap.py` first (feeds it encoder/touch), saves the choice to `/fs1/.state.json`, then constructs and runs `Launcher` |
| `boot.py` | Runs before `main.py` — initializes USB HID + backlight, loads `/fs1/settings.json` |
| `lib/` | Frozen MicroPython hardware drivers (see below) |
| `main/` | **Legacy** — ESP-IDF component from the pre-restructure C project (kept for reference) |
| `CMakeLists.txt` | **Legacy** — `project(knob-control)` from the C project; the firmware is built via lv_micropython, not here |
| `sdkconfig.defaults` | **Legacy** — superseded by the board's `sdkconfig.board` in lv_micropython |
| `partitions.csv` | `nvs`, `phy_init`, `fs1` FAT partition (3MB @ 0x10000), factory app — mirrors the board table that ships in the firmware |
| `protocol/messages.py` | Shared JSON message types (knob ↔ PC) — frozen into the firmware |
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
| `wifi_connect.py` | STA_IF wifi connect + USB-link detection (on-device wifi from the chosen location config) |
| `plugin_manager.py` | Runtime plugin loading from machine configs |

## Runtime Flow

```
boot.py ──► main.py ──► read /fs1 (settings, locations) → run bootstrap.py
                            │
                  knob picks a location on-screen (preselected when
                  USB-plugged via the server's identify, wifi-filtered
                  when standalone) → join that location's wifi
                            │
                  connect to PC server (USB link or wifi) → app UI
```

The physical knob is self-contained: `bootstrap.py`, the location configs, and
`launcher.py` all live in its own `/fs1` FAT partition (`partitions.csv`), so it
can pick a location and join that room's wifi with no server round-trip. The PC
server is only needed for the ongoing control channel — app selections become
`action` messages the server routes to platform handlers.

### Location selection

`bootstrap.py` reads `/fs1/locations/*.json` (the browser sim falls back to the
server-injected list — it has no `/fs1` yet). Which locations it shows:

- **USB-plugged into a PC** — the PC's server sends an `identify` message with
  its own OS machine id (Windows `SOFTWARE\Microsoft\Cryptography\MachineGuid`,
  macOS hardware UUID, Linux `/etc/machine-id`). If it matches a location, that
  location is preselected (auto-confirmed when unique).
- **Standalone on wifi** — no machine guid; bootstrap scans `network.WLAN` and
  shows only locations whose `wifi.ssid` is reachable.
- **Otherwise** — all locations are shown.

The chosen `location` is reported in `bootstrap_response`. Each location config
carries its own `wifi` credentials, so a wifi-only knob can pick a room and join
that room's wifi without a server. `main.py` runs bootstrap first (it execs
`/fs1/bootstrap.py`, feeds it encoder/touch input, and saves the choice to
`/fs1/.state.json`), then the launcher loads the chosen location's config.

### Wifi (bedroom / living room)

The knob prefers the wired **USB link** for the server connection (the server
identifies itself → preselected location). Standalone, `bootstrap.py` joins the
wifi from the **chosen location's config** right after you pick it — not from
settings.json:

- `lib/wifi_connect.py` connects STA_IF to a `{ssid, password}` pair and detects
  the USB link (`on_usb_link`). `bootstrap._wifi_join()` skips the join when the
  USB link is up, and the browser sim is a no-op (no `network` module).
- `boot.py` sets the `boot_backlight` from `/fs1/settings.json` so the location
  picker is visible in the dark; per-location backlight applies after selection.
- Standalone, the knob doesn't need a PC server at all — after joining the room
  wifi it can talk to home devices (lights, curtains) directly. `launcher.py`
  still picks `websocket_uri` (the PC server's LAN address) when on wifi for the
  PC-app path, and falls back to `ws://10.10.10.2:8765` on the USB link.

## Build & Flash

The firmware is built by **lv_micropython** (`../hardware/lv_micropython/`) for
the `WAVESHARE_ESP32_S3_KNOB` board, using ESP-IDF v5.3 in
`../hardware/esp-idf/`. The board manifest
(`ports/esp32/boards/WAVESHARE_ESP32_S3_KNOB/manifest.py`) freezes this repo's
code into the firmware:

- `lib/` and `protocol/` → `freeze("$(MPY_DIR)/../../fs2/...")`
- `boot.py` and `main.py` → `module(..., base_path="$(MPY_DIR)/../../fs2")`
- `launcher.py` → `module(..., base_path="$(MPY_DIR)/../../fs1")` (it lives in
  the `/fs1` payload tree, and is frozen so the launcher always runs)

The board partition table `ports/esp32/partitions-16MiB.csv` was aligned to
`partitions.csv` above (`fs1` FAT 3MB @ 0x10000, `factory` app @ 0x310000).

### Prerequisites

- ESP-IDF v5.3 cloned into `../hardware/esp-idf/` — plus build tools
  (`cmake`, `ninja`) and IDF toolchains:
  `idf_tools.py install esp-rom-elfs openocd-esp32` then `idf_tools.py install-python-env`.
- lv_micropython in `../hardware/lv_micropython/`.
- Python 3.10+ and `mpremote` (for the `/fs1` payload step).

### macOS quickstart

`hardware/` is git-ignored, so a fresh clone has no SDKs. The **exact** SDK
snapshot that produced the working build is packaged as
`knob-lv-micropython.tar.gz` (~96MB — MicroPython + LVGL 9.3 bindings + custom
board). Get it and run:

```bash
./fs2/setup-mac.sh /path/to/knob-lv-micropython.tar.gz
```

The script extracts the SDK, clones stock ESP-IDF v5.3.0, installs Homebrew
tools + IDF toolchains, and builds. It also applies a macOS-only fix to
`mpy-cross/Makefile` (new Xcode clangs treat the `MP_STATIC_ASSERT` VLA as a
fatal `-Wgnu-folding-constant` warning) and builds into a distinct
`build-WAVESHARE_ESP32_S3_KNOB-mac` dir. Afterwards: flash + push `/fs1`
(below).

> This folder is shared with the Linux dev container, and CMake caches
> absolute paths per host — so Mac and container must use **different** build
> dirs (macOS: `-mac` suffix; container: no suffix). If a build ever fails with
> "configured for project ... not ...", run `idf.py fullclean` for that host.

### Build

```bash
cd ../hardware/lv_micropython/ports/esp32
. $IDF_PATH/export.sh            # set IDF_PATH to ../hardware/esp-idf first
idf.py -B build-WAVESHARE_ESP32_S3_KNOB -D MICROPY_BOARD=WAVESHARE_ESP32_S3_KNOB build
```

On macOS, use the `-mac` build dir (as `setup-mac.sh` does):
`idf.py -B build-WAVESHARE_ESP32_S3_KNOB-mac ...`.

> **Troubleshooting:** if the build fails with `error: redeclaration of
> enumerator 'MP_QSTR_y'` (a `frozen_content.c` qstr collides with
> `genhdr/qstrdefs.generated.h`), the generated `frozen_content.c` is stale —
> it was produced before the qstr table last changed (e.g. the LVGL glue
> `lv_mp.c` regenerated and added shared strings like `y`, `x`, `x_points`).
> `frozen_content.c` is regenerated with dedup against the qstr table, so
> delete it and rebuild (or run `idf.py fullclean`):
> `rm build-WAVESHARE_ESP32_S3_KNOB/frozen_content.c && idf.py build`.

Artifacts land in `build-WAVESHARE_ESP32_S3_KNOB/` (`-mac` on macOS):

| File | Flash offset |
|------|--------------|
| `bootloader/bootloader.bin` | `0x0` |
| `partition_table/partition-table.bin` | `0x8000` |
| `micropython.bin` (≈2.6MB) | `0x310000` |

### Flash

> Canonical board reference: https://www.waveshare.com/wiki/ESP32-S3-Knob-Touch-LCD-1.8
> (dual-MCU diagram, plug-orientation download channels, BOOT button, Arduino setup).

This board has **two MCUs** — the ESP32-S3R8 (target) and an ESP32 co-processor —
and the Type-C plug **orientation selects which chip's download channel** you're
talking to (Waveshare FAQ). Only the **native USB-CDC** (`/dev/cu.usbmodem*`,
`ttyACM0`) is wired to the ESP32-S3. The CH343 UART (`/dev/cu.usbserial-*`,
`ttyUSB0`) connects to the ESP32 co-processor, so esptool reports
"This chip is ESP32, not ESP32-S3" — that error is *correct*; use the CDC port
instead.

Over native USB the chip re-enumerates when it drops into download mode, so the
default reset makes esptool drop the connection ("The chip stopped responding").
Force download mode with the **BOOT button** first, then flash (a manually
entered download mode needs no special `--before` reset):

```bash
# 1. Plug in with the S3-native orientation so /dev/cu.usbmodem* (or ttyACM0) appears.
#    If the port is missing or is /dev/cu.usbserial-*, flip the plug 180° and re-insert.
# 2. There is NO reset button on this board. Enter download mode by holding the
#    ESP32-S3R8 BOOT button, unplugging the USB cable, re-plugging it (still holding
#    BOOT), and releasing only once the serial port appears again — the S3 is now in
#    download mode.
idf.py -B build-WAVESHARE_ESP32_S3_KNOB -p /dev/cu.usbmodem* flash monitor        # macOS
idf.py -B build-WAVESHARE_ESP32_S3_KNOB -p /dev/ttyACM0 flash monitor             # container
```

Use the same `-B build-...` dir you built with (`-mac` suffix when built by
`setup-mac.sh`). If flashing still can't sync, run esptool directly with
`--before=usb_reset` (esptool ≥ 3.3). The CH343 UART and native CDC are both
fine for `mpremote` *after* boot.

If the first boot prints "The filesystem appears to be corrupted" in a loop,
that's `inisetup.check_bootsec()` refusing to format a *non-empty* partition —
esptool only erased the regions it wrote, so the `fs1` area (0x10000–0x300000)
still holds old data. Enter download mode again (BOOT + re-plug USB), erase just
that region, then unplug/re-plug normally to boot — no reflash needed:

```bash
esptool.py --chip esp32s3 -p /dev/cu.usbmodem21201 erase_region 0x10000 0x300000
```

(You're already in download mode, so no `--before` is needed; `--before=usb_reset`
would reset the chip out of download mode and can drop the connection.)

**Faster alternative (no download mode):** while the loop is running you can
interrupt it and format `/fs1` right from the REPL. Connect with
`mpremote connect /dev/cu.usbmodem21201 repl`, press **Ctrl-C** to break the
corrupted loop, then paste:

```python
import vfs
from flashbdev import bdev
vfs.VfsFat.mkfs(bdev)
vfs.mount(vfs.VfsFat(bdev), '/fs1')
```

Press **Ctrl-D** (soft reset) to reboot; it comes back clean and lands at the
REPL. `main.py` tolerates the now-empty `/fs1`, so it will idle until you push
the payload below.

If the CLI keeps losing the port (or a terminal crash kills the session), use
Espressif's browser flasher — https://webflasher.espressif.com/ (Chrome/Edge,
WebSerial): connect, then **Erase Flash** or upload the three `.bin` files at
the offsets in the table above.

### First boot — populate `/fs1`

On first boot `inisetup` formats the `fs1` partition as an **empty** FAT volume.
`boot.py`, `main.py`, `launcher.py`, `lib/`, and `protocol/` are already frozen
into the firmware, but `bootstrap.py`, `server.py`, `settings.json`,
`locations/`, and `plugins/` are filesystem payload. Copy them from the repo root
over the native USB CDC REPL (`/dev/cu.usbmodem*` on macOS, `/dev/ttyACM0` on the
container; the UART REPL works too):

```bash
PORT=/dev/cu.usbmodem21201   # your device — `ls /dev/cu.*` to find it (container: /dev/ttyACM0)
mpremote connect "$PORT" mkdir :/fs1
mpremote connect "$PORT" mkdir :/fs1/locations
mpremote connect "$PORT" mkdir :/fs1/plugins
mpremote connect "$PORT" cp fs1/settings.json :/fs1/settings.json
mpremote connect "$PORT" cp fs1/bootstrap.py :/fs1/bootstrap.py
mpremote connect "$PORT" cp fs1/server.py :/fs1/server.py
mpremote connect "$PORT" cp fs1/locations/*.json :/fs1/locations/
for p in fs1/plugins/*; do
  mpremote connect "$PORT" mkdir :/fs1/plugins/$(basename "$p")
  mpremote connect "$PORT" cp "$p/manifest.json" "$p/plugin.py" "/fs1/plugins/$(basename "$p")/"
done
mpremote connect "$PORT" reset
```

Do this before the knob's first real use — `main.py` execs `/fs1/bootstrap.py`
at boot, so without the payload the location picker can't run.

### Settings

`/fs1/settings.json` on the knob is small — transport + boot config only:

```json
{
    "boot_backlight": 200,
    "websocket_uri": "ws://192.168.1.50:8765",
    "static_ip": {"knob": "10.10.10.1", "pc": "10.10.10.2"}
}
```

- `boot_backlight` — fixed level so the location picker is visible in the dark.
- `websocket_uri` — the PC server's LAN address when on wifi (`ws://<pc-lan-ip>:8765`);
  the USB static address is used automatically when the USB link is up.

Wifi credentials and per-location defaults (backlight, haptic, sound) live in
`/fs1/locations/*.json`, not in settings.json — the knob picks a room, then uses
that room's wifi and settings.

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
