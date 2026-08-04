"""
WiFi + link detection for the Smart Knob firmware.

The knob talks to the PC server either over a wired USB (CDC-ECM) link or,
standalone, over wifi. This module connects STA_IF to a {ssid, password} pair
and reports which transport is up so the launcher can pick the right server
URI. Credentials come from the location the knob chose in bootstrap.py, not
from settings.json.

Designed for MicroPython on ESP32-S3. Every function is defensive: on the
browser sim (no `network` module) they degrade to None/False without raising.
"""
import time


def connect(ssid, password, timeout_ms=15000):
    """Join the SSID as a wifi station.

    Returns the interface config tuple (ip, netmask, gateway, dns) once
    connected, or None on failure / missing `network` module. Never raises.
    """
    try:
        import network
    except ImportError:
        return None
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            if not ssid:
                return None
            wlan.connect(ssid, password)
            deadline = time.ticks_ms() + timeout_ms
            while not wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), deadline) > 0:
                    return None
                time.sleep_ms(100)
        return wlan.ifconfig()
    except Exception:
        return None


def is_connected():
    """True when STA_IF is active and joined to a network."""
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        return bool(wlan.active() and wlan.isconnected())
    except Exception:
        return False


def on_usb_link():
    """True when the knob's USB CDC-ECM gadget link is up.

    The PC server listens on the static pc IP (10.10.10.2) on that link; when
    it's up the knob should reach the server over USB so the server injects
    the machine guid (preselected location). Standalone on wifi this is False.
    """
    try:
        import network
    except ImportError:
        return False
    try:
        usb = network.CDC()
        return bool(usb.active())
    except Exception:
        return False
