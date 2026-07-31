"""
CST816 capacitive touch driver for Waveshare ESP32-S3-Knob.

I2C address: 0x15
Requires RST pulse before I2C works.
Must run at 100kHz (not 400kHz).
"""
from machine import Pin
from time import sleep_ms

CST816_ADDR = 0x15

# Gesture constants
GESTURE_NONE = 0x00
GESTURE_SLIDE_DOWN = 0x01
GESTURE_SLIDE_UP = 0x02
GESTURE_SLIDE_LEFT = 0x03
GESTURE_SLIDE_RIGHT = 0x04
GESTURE_SINGLE_TAP = 0x05
GESTURE_DOUBLE_TAP = 0x0B
GESTURE_LONG_PRESS = 0x0C


class CST816:
    def __init__(self, i2c, rst_pin, int_pin):
        self.i2c = i2c
        self.rst_pin = Pin(rst_pin, Pin.OUT)
        self.int_pin = Pin(int_pin, Pin.IN, Pin.PULL_UP)

    def init(self):
        """Hardware reset sequence — mandatory before I2C works."""
        # RST pulse: LOW 10ms, HIGH, wait 300ms
        self.rst_pin.value(0)
        sleep_ms(10)
        self.rst_pin.value(1)
        sleep_ms(300)

        # Wake up CST816 (write 0xFF to register 0xFE)
        try:
            self.i2c.writeto_mem(CST816_ADDR, 0xFE, b'\xff')
        except OSError:
            pass  # May not ACK on first try — that's OK

    def read(self):
        """Read touch state. Returns (pressed, x, y, gesture)."""
        try:
            data = self.i2c.readfrom_mem(CST816_ADDR, 0x00, 7)
        except OSError:
            return False, 0, 0, GESTURE_NONE

        gesture = data[0]
        fingers = data[1]  # 0x01 = finger down
        x = ((data[2] & 0x0F) << 8) | data[3]
        y = ((data[4] & 0x0F) << 8) | data[5]

        pressed = (fingers == 0x01)
        return pressed, x, y, gesture

    def is_tapped(self):
        """Check for single tap gesture."""
        pressed, x, y, gesture = self.read()
        return pressed and gesture == GESTURE_SINGLE_TAP

    def scan(self):
        """Verify CST816 is present on I2C bus."""
        return CST816_ADDR in self.i2c.scan()
