"""
Hardware initialization for Waveshare ESP32-S3-Knob-Touch-LCD-1.8

Initializes I2C, GPIO, backlight, and provides hardware references
to plugins and the launcher.
"""
from machine import Pin, I2C, PWM
from time import sleep_ms

# Display (SH8601 QSPI)
PIN_LCD_CS = 14
PIN_LCD_SCLK = 13
PIN_LCD_D0 = 15
PIN_LCD_D1 = 16
PIN_LCD_D2 = 17
PIN_LCD_D3 = 18
PIN_LCD_RST = 21
PIN_LCD_BL = 47

# Touch (CST816 I2C)
PIN_TOUCH_SDA = 11
PIN_TOUCH_SCL = 12
PIN_TOUCH_RST = 10
PIN_TOUCH_INT = 9
TOUCH_I2C_ADDR = 0x15

# Encoder (two independent micro-switches)
PIN_ENCODER_A = 8
PIN_ENCODER_B = 7

# Haptic (DRV2605 I2C)
DRV2605_ADDR = 0x5A

# Audio DAC
PIN_DAC_ENABLE = 0

# PDM Mic
PIN_PDM_CLK = 45
PIN_PDM_DATA = 46

# Display dimensions
LCD_WIDTH = 360
LCD_HEIGHT = 360


class Hardware:
    """Central hardware manager. Provides initialized peripheral objects."""

    def __init__(self):
        self.i2c = None
        self.display = None
        self.touch = None
        self.encoder = None
        self.backlight = None
        self.haptic = None
        self._init_i2c()
        self._init_backlight()

    def _init_i2c(self):
        """Initialize I2C bus at 100kHz for CST816 stability."""
        self.i2c = I2C(0, scl=Pin(PIN_TOUCH_SCL), sda=Pin(PIN_TOUCH_SDA), freq=100000)

    def _init_backlight(self):
        """Initialize backlight PWM on GPIO 47."""
        self.backlight = PWM(Pin(PIN_LCD_BL), freq=5000, duty=0)

    def set_backlight(self, brightness):
        """Set backlight brightness (0-255)."""
        self.backlight.duty(brightness & 0xFF)

    def init_display(self):
        """Initialize SH8601 display. Called after LVGL is ready.

        Idempotent — reuses the existing display so the launcher never
        registers a second LVGL display driver."""
        if self.display is not None:
            return self.display
        from sh8601 import SH8601
        self.display = SH8601(
            cs=PIN_LCD_CS, sclk=PIN_LCD_SCLK,
            d0=PIN_LCD_D0, d1=PIN_LCD_D1,
            d2=PIN_LCD_D2, d3=PIN_LCD_D3,
            rst=PIN_LCD_RST,
            width=LCD_WIDTH, height=LCD_HEIGHT
        )
        self.set_backlight(200)
        return self.display

    def init_touch(self):
        """Initialize CST816 touch controller. Idempotent."""
        if self.touch is not None:
            return self.touch
        from cst816 import CST816
        self.touch = CST816(self.i2c, PIN_TOUCH_RST, PIN_TOUCH_INT)
        self.touch.init()
        return self.touch

    def init_encoder(self):
        """Initialize encoder GPIO pins. Idempotent."""
        if self.encoder is not None:
            return self.encoder
        from encoder import Encoder
        self.encoder = Encoder(PIN_ENCODER_A, PIN_ENCODER_B)
        return self.encoder

    def init_haptic(self):
        """Initialize DRV2605 haptic motor driver. Idempotent."""
        if self.haptic is not None:
            return self.haptic
        from drv2605 import DRV2605
        self.haptic = DRV2605(self.i2c, enable_pin=PIN_DAC_ENABLE)
        self.haptic.init()
        return self.haptic

    def scan_i2c(self):
        """Scan I2C bus and return list of found addresses."""
        return self.i2c.scan()
