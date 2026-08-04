#!/usr/bin/env bash
# Build the knob firmware on macOS.
#
# Needs:   Xcode Command Line Tools, Homebrew, Python 3.10+.
# Usage:
#   ./setup-mac.sh                                          # hardware/lv_micropython already present
#   ./setup-mac.sh /path/to/knob-lv-micropython.tar.gz      # extract the exact SDK snapshot first
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # repo root (fs2/..)
HARDWARE="$ROOT/hardware"
IDF_PATH="$HARDWARE/esp-idf"
LVM="$HARDWARE/lv_micropython"
IDF_BRANCH="v5.3.0"
BOARD="WAVESHARE_ESP32_S3_KNOB"
# macOS uses a distinct build dir: this folder is shared with the Linux dev
# container, and CMake caches absolute paths per host. Sharing one build dir
# makes the other host error with "configured for project ... not ...".
BUILD="build-$BOARD-mac"

# --- 1. lv_micropython source (exact snapshot that produced the working build) ---
if [ ! -d "$LVM/ports/esp32/boards/$BOARD" ]; then
  if [ "${1:-}" ] && [ -f "$1" ]; then
    echo ">> Extracting lv_micropython SDK: $1"
    mkdir -p "$HARDWARE"
    tar -xzf "$1" -C "$HARDWARE"
  else
    echo "ERROR: hardware/lv_micropython is missing." >&2
    echo "Get the exact SDK tarball (~96MB) and re-run:" >&2
    echo "  $0 /path/to/knob-lv-micropython.tar.gz" >&2
    exit 1
  fi
fi

# --- 1b. macOS/Apple-Clang fix for the host mpy-cross build (idempotent) ---
# New Xcode clangs flag the VLA in py/misc.h MP_STATIC_ASSERT as
# -Wgnu-folding-constant, and mpy-cross compiles with -Werror. Suppress that
# one warning; gcc accepts the flag as a no-op.
MPYCROSS_MK="$LVM/mpy-cross/Makefile"
grep -q "gnu-folding-constant" "$MPYCROSS_MK" || \
  sed -i '' 's/^CWARN = -Wall -Werror/CWARN = -Wall -Werror -Wno-gnu-folding-constant/' "$MPYCROSS_MK"

# --- 2. ESP-IDF v5.3.0 (stock, from Espressif) ---
if [ ! -d "$IDF_PATH" ]; then
  echo ">> Cloning ESP-IDF $IDF_BRANCH (with submodules — ~1GB, one-time)..."
  git clone -b "$IDF_BRANCH" --recurse-submodules --depth 1 https://github.com/espressif/esp-idf.git "$IDF_PATH"
fi

# --- 3. Host build tools (macOS / Homebrew) ---
command -v cmake >/dev/null || brew install cmake
command -v ninja >/dev/null || brew install ninja
brew list libusb >/dev/null 2>&1 || brew install libusb

# --- 4. ESP-IDF toolchains + Python env (one-time) ---
if [ ! -d "$HOME/.espressif/tools" ] || [ ! -d "$HOME/.espressif/python_env" ]; then
  echo ">> Installing ESP-IDF toolchains for esp32s3 (downloads ~1GB)..."
  "$IDF_PATH/install.sh" esp32s3
fi

# --- 5. Build ---
cd "$LVM/ports/esp32"
. "$IDF_PATH/export.sh"
# Cap parallelism: `idf.py build` runs ninja on all cores, which can exhaust
# host memory (symptom: "Broken pipe" from killed compilers). Configure with
# idf.py, then drive ninja directly with a job cap. Override with JOBS=N.
JOBS="${JOBS:-6}"
idf.py -B "$BUILD" -D MICROPY_BOARD="$BOARD" reconfigure
ninja -C "$BUILD" -j "$JOBS"

echo
echo "=================================================================="
echo "Build complete. Artifacts in ports/esp32/$BUILD/:"
echo "  bootloader/bootloader.bin         @ 0x0"
echo "  partition_table/partition-table.bin @ 0x8000"
echo "  micropython.bin                   @ 0x310000"
echo
echo "Flash (board plugged into the edge USB-C):"
echo "  cd $LVM/ports/esp32"
echo "  idf.py -B $BUILD -p /dev/cu.usbmodem* flash monitor"
echo
echo "First boot: populate /fs1 (see fs2/README.md)."
echo "=================================================================="
