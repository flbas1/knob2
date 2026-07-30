"""
Smart Knob Controller — boot.py

Runs at every boot, before main.py.
Initialize hardware and USB HID early so it's ready before REPL.
"""
import gc
import sys
import os

gc.collect()

# Ensure lib/ is on path
if '/lib' not in sys.path:
    sys.path.insert(0, '/lib')

# Try to load settings for early config
_settings = {}
try:
    with open('/fs1/settings.json', 'r') as f:
        import json
        _settings = json.load(f)
except:
    pass

gc.collect()

# Initialize USB HID early (before main.py)
# This ensures the HID device enumerates when USB starts
try:
    from hid import HIDDevice
    _hid = HIDDevice()
    _hid.init()
    del _hid
except Exception as e:
    print(f"[boot] HID init: {e}")

gc.collect()

# Set default backlight if configured
try:
    _bl = _settings.get('defaults', {}).get('backlight', 0)
    if _bl > 0:
        from machine import Pin, PWM
        _bl_pin = PWM(Pin(47), freq=5000, duty=_bl)
        del _bl_pin
except:
    pass

del _settings
gc.collect()
