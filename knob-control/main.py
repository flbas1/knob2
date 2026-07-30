"""
Smart Knob Controller — Entry Point

Boots MicroPython, initializes hardware, loads launcher.
This file runs automatically at boot (after boot.py).
"""
import gc
import sys
import os

gc.collect()

# Add lib/ to path
sys.path.insert(0, '/lib')

# Import and run launcher
from launcher import Launcher

gc.collect()
launcher = Launcher()
launcher.run()
