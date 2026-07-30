include("$(PORT_DIR)/boards/manifest.py")
include("$(MPY_DIR)/user_modules/lv_binding_micropython/ports/esp32/manifest.py")

# Freeze specific app files individually
freeze("$(MPY_DIR)/../knob-control/lib")
freeze("$(MPY_DIR)/../knob-control/protocol")

# Main entry points (only .py files from knob-control root)
module("boot.py", base_path="$(MPY_DIR)/../knob-control")
module("main.py", base_path="$(MPY_DIR)/../knob-control")
module("launcher.py", base_path="$(MPY_DIR)/../knob-control")
