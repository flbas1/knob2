"""
Smart Knob Controller — pins.h equivalent for MicroPython

GPIO pin assignments for Waveshare ESP32-S3-Knob-Touch-LCD-1.8.
These are defined in lib/hardware.py as Python constants.

This file is provided as reference for C extension development.
"""

# Display SH8601 (QSPI)
PIN_LCD_CS      = 14
PIN_LCD_SCLK    = 13
PIN_LCD_D0      = 15
PIN_LCD_D1      = 16
PIN_LCD_D2      = 17
PIN_LCD_D3      = 18
PIN_LCD_RST     = 21
PIN_LCD_BL      = 47

# Touch CST816 (I2C)
PIN_TOUCH_SDA   = 11
PIN_TOUCH_SCL   = 12
PIN_TOUCH_RST   = 10
PIN_TOUCH_INT   = 9

# Encoder (two independent micro-switches)
PIN_ENCODER_A   = 8
PIN_ENCODER_B   = 7

# Haptic DRV2605 (I2C, same bus as touch)
DRV2605_I2C_ADDR = 0x5A

# Audio DAC PCM5100A
PIN_DAC_ENABLE  = 0   # HIGH = active, LOW = mute

# PDM Microphone
PIN_PDM_CLK     = 45
PIN_PDM_DATA    = 46

# Display dimensions
LCD_WIDTH       = 360
LCD_HEIGHT      = 360
