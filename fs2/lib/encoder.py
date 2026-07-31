"""
Non-quadrature encoder driver for Waveshare ESP32-S3-Knob.

The encoder uses two independent micro-switches, NOT a standard quadrature encoder.
- Switch A goes LOW while turning CW
- Switch B goes LOW while turning CCW
- Both LOW = button press

Detection: falling edge on A = CW, falling edge on B = CCW.
Debounced with time-based approach.
"""
from machine import Pin
from time import ticks_ms, ticks_diff

# Event constants
ENCODER_NONE = 0
ENCODER_CW = 1
ENCODER_CCW = 2
ENCODER_BUTTON = 3

DEBOUNCE_MS = 30


class Encoder:
    def __init__(self, pin_a, pin_b):
        self.pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self._prev_a = self.pin_a.value()
        self._prev_b = self.pin_b.value()
        self._last_edge_time = 0
        self._button_held = False

    def poll(self):
        """Poll encoder state. Returns one of ENCODER_NONE/CW/CCW/BUTTON.
        Call frequently (every 3-5ms) from main loop."""
        now = ticks_ms()
        a = self.pin_a.value()
        b = self.pin_b.value()

        # Both LOW = button press
        if a == 0 and b == 0:
            if not self._button_held:
                self._button_held = True
                self._last_edge_time = now
                return ENCODER_BUTTON
            return ENCODER_NONE
        else:
            self._button_held = False

        # Debounce check
        if ticks_diff(now, self._last_edge_time) < DEBOUNCE_MS:
            self._prev_a = a
            self._prev_b = b
            return ENCODER_NONE

        result = ENCODER_NONE

        # Falling edge on A = CW
        if self._prev_a == 1 and a == 0:
            result = ENCODER_CW
            self._last_edge_time = now

        # Falling edge on B = CCW
        if self._prev_b == 1 and b == 0:
            result = ENCODER_CCW
            self._last_edge_time = now

        self._prev_a = a
        self._prev_b = b
        return result

    def read_state(self):
        """Read raw encoder state (for diagnostics)."""
        return self.pin_a.value(), self.pin_b.value()
