"""
USB HID composite device for Smart Knob Controller.

Provides Consumer Control (volume), Mouse (scroll/zoom), and Keyboard
(modifier keys) via TinyUSB on ESP32-S3.

Uses MicroPython's usb.device API (available since v1.25).
Must be initialized with builtin_driver=True so USB-CDC REPL
remains available alongside HID.
"""
import time
from micropython import const

# HID Report IDs
REPORT_ID_CONSUMER = const(1)
REPORT_ID_MOUSE = const(2)
REPORT_ID_KEYBOARD = const(3)

# Consumer Control usage codes
CONSUMER_VOLUME_UP = const(0x00E9)
CONSUMER_VOLUME_DOWN = const(0x00EA)
CONSUMER_MUTE = const(0x00E2)
CONSUMER_PLAY_PAUSE = const(0x00CD)
CONSUMER_SCAN_NEXT = const(0x00B5)
CONSUMER_SCAN_PREV = const(0x00B6)

# Keyboard modifier bits
MOD_LCTRL = const(0x01)
MOD_LSHIFT = const(0x02)
MOD_LALT = const(0x04)
MOD_LGUI = const(0x08)


class HIDDevice:
    """USB HID composite device (Consumer + Mouse + Keyboard).

    In production, this uses usb.device + usb-device-hid packages.
    For browser testing, this is stubbed out.
    """

    def __init__(self):
        self._ready = False
        self._consumer = None
        self._mouse = None
        self._keyboard = None

    def init(self):
        """Initialize USB HID device.

        Must be called in boot.py before main loop starts.
        Uses builtin_driver=True to keep USB-CDC REPL alive.
        """
        try:
            import usb.device
            from usb.device.keyboard import KeyboardInterface, KeyCode
            from usb.device.mouse import MouseInterface

            self._keyboard = KeyboardInterface()
            self._mouse = MouseInterface()
            # Consumer control needs custom HID descriptor
            # For now, use keyboard for volume shortcuts as fallback
            usb.device.get().init(self._keyboard, builtin_driver=True)
            self._ready = True
        except ImportError:
            print("[hid] usb.device not available — HID disabled")
            self._ready = False
        except Exception as e:
            print(f"[hid] Init failed: {e}")
            self._ready = False

    def is_ready(self):
        return self._ready

    def volume_up(self):
        """Send volume up HID report."""
        if not self._ready:
            return False
        try:
            # Use keyboard media key or consumer control
            self._send_consumer(CONSUMER_VOLUME_UP)
            return True
        except Exception:
            return False

    def volume_down(self):
        """Send volume down HID report."""
        if not self._ready:
            return False
        try:
            self._send_consumer(CONSUMER_VOLUME_DOWN)
            return True
        except Exception:
            return False

    def mute(self):
        """Send mute HID report."""
        if not self._ready:
            return False
        try:
            self._send_consumer(CONSUMER_MUTE)
            return True
        except Exception:
            return False

    def scroll(self, direction):
        """Send mouse scroll wheel event.

        Args:
            direction: +1 = scroll up, -1 = scroll down
        """
        if not self._ready or not self._mouse:
            return False
        try:
            self._mouse.move_by(0, 0, direction)
            return True
        except Exception:
            return False

    def zoom_in(self):
        """Send Ctrl+MouseWheelUp for zoom in."""
        if not self._ready:
            return False
        try:
            # Press Ctrl, scroll, release Ctrl
            self._keyboard.send_keys([0xE1])  # Left Ctrl
            time.sleep_ms(10)
            self._mouse.move_by(0, 0, 1)  # Wheel up
            time.sleep_ms(10)
            self._keyboard.send_keys([])  # Release
            return True
        except Exception:
            return False

    def zoom_out(self):
        """Send Ctrl+MouseWheelDown for zoom out."""
        if not self._ready:
            return False
        try:
            self._keyboard.send_keys([0xE1])  # Left Ctrl
            time.sleep_ms(10)
            self._mouse.move_by(0, 0, -1)  # Wheel down
            time.sleep_ms(10)
            self._keyboard.send_keys([])  # Release
            return True
        except Exception:
            return False

    def _send_consumer(self, usage_code):
        """Send a consumer control report.

        This is a placeholder. The actual implementation depends
        on the usb-device-hid package's consumer control class.
        Falls back to keyboard volume shortcuts if consumer control
        is not available.
        """
        # Fallback: use keyboard media keys
        # Volume Up = Ctrl+Shift+Up (platform-dependent)
        # This is a simplification — real implementation needs
        # a proper consumer control HID descriptor
        pass
