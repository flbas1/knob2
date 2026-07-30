from machine import Pin
from time import sleep_ms

DRV2605_ADDR = 0x5A

REG_STATUS = 0x00
REG_MODE = 0x01
REG_RTPIN = 0x02
REG_LIBRARY = 0x03
REG_WAVESEQ1 = 0x04
REG_GO = 0x0C
REG_OVERDRIVE = 0x25
REG_SUSTAINPOS = 0x26
REG_SUSTAINNEG = 0x27
REG_BREAK = 0x28
REG_AUDIOCTRL = 0x29
REG_RATIO = 0x2B

MODE_INTTRIG = 0x00
MODE_EXTTRIG = 0x01
MODE_PWM = 0x03
MODE_AUDIOVIBE = 0x04
MODE_REALTIME = 0x05
MODE_DIAG = 0x06
MODE_AUTOCAL = 0x07

LIBRARY_LRA = 0x06

class DRV2605:
    def __init__(self, i2c, addr=DRV2605_ADDR, enable_pin=None):
        self.i2c = i2c
        self.addr = addr
        self.enable_pin = Pin(enable_pin, Pin.OUT) if enable_pin else None

    def init(self):
        if self.enable_pin:
            self.enable_pin.value(1)
            sleep_ms(5)
        self._write_reg(REG_MODE, MODE_INTTRIG)
        self._write_reg(REG_LIBRARY, LIBRARY_LRA)
        self._write_reg(REG_RTPIN, 0x00)
        self.go()

    def go(self):
        self._write_reg(REG_GO, 0x01)

    def play(self, effect=1):
        self._write_reg(REG_WAVESEQ1, effect)
        self._write_reg(REG_MODE, MODE_INTTRIG)
        self.go()

    def stop(self):
        self._write_reg(REG_MODE, MODE_REALTIME)
        self._write_reg(REG_RTPIN, 0x00)
        self._write_reg(REG_GO, 0x00)

    def set_rtp(self, value):
        self._write_reg(REG_MODE, MODE_REALTIME)
        self._write_reg(REG_RTPIN, max(0, min(255, value)))

    def trigger_autocal(self):
        self._write_reg(REG_MODE, MODE_AUTOCAL)
        self.go()

    def _write_reg(self, reg, value):
        try:
            self.i2c.writeto_mem(self.addr, reg, bytes([value]))
        except OSError:
            pass

    def _read_reg(self, reg):
        try:
            return self.i2c.readfrom_mem(self.addr, reg, 1)[0]
        except OSError:
            return 0
