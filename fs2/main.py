"""
Smart Knob Controller — Entry Point

Boots MicroPython, runs bootstrap.py (location picker + wifi join) from /fs1,
then loads the launcher for the chosen location.

This file runs automatically at boot (after boot.py).
"""
import gc
import sys

gc.collect()

# Add lib/ to path
sys.path.insert(0, '/lib')


def _run_bootstrap():
    """Run /fs1/bootstrap.py on the real knob. Returns its module namespace,
    or None if it couldn't be read/executed."""
    try:
        with open('/fs1/bootstrap.py', 'r') as f:
            src = f.read()
    except Exception as e:
        print(f"[main] bootstrap read failed: {e}")
        return None
    ns = {}
    try:
        exec(compile(src, '/fs1/bootstrap.py', 'exec'), ns)
    except Exception as e:
        print(f"[main] bootstrap exec failed: {e}")
        return None
    return ns


def _bootstrap_poll(ns, hardware):
    """Drive bootstrap's on_encoder/on_button/on_touch until it confirms.

    Exits early on timeout so a broken picker never hangs the boot."""
    from time import sleep_ms, ticks_ms, ticks_diff
    from encoder import ENCODER_CW, ENCODER_CCW, ENCODER_BUTTON

    timeout_ms = 60000
    start = ticks_ms()
    while not ns.get('_done'):
        if ticks_diff(ticks_ms(), start) > timeout_ms:
            print("[main] bootstrap picker timed out")
            return
        sleep_ms(5)
        if hardware and hardware.encoder:
            ev = hardware.encoder.poll()
            if ev == ENCODER_CW:
                ns.get('on_encoder', lambda d: None)(1)
            elif ev == ENCODER_CCW:
                ns.get('on_encoder', lambda d: None)(-1)
            elif ev == ENCODER_BUTTON:
                ns.get('on_button', lambda: None)()
        if hardware and hardware.touch:
            pressed, x, y, gesture = hardware.touch.read()
            if pressed and gesture == 0x05:
                ns.get('on_touch', lambda x, y, p: None)(x, y, True)
        try:
            import lvgl as lv
            lv.timer_handler()
        except Exception:
            pass


def _save_chosen_location(location):
    """Persist the bootstrap-chosen location so the launcher picks the same
    config from /fs1/locations. Falls back silently — sim never gets here."""
    if not location:
        return
    try:
        import json
        with open('/fs1/.state.json', 'w') as f:
            json.dump({'location': location}, f)
    except Exception as e:
        print(f"[main] save location failed: {e}")


def main():
    # Initialize LVGL + display + input FIRST so bootstrap's picker can draw
    # (bootstrap.py builds its UI at exec time).
    hw = None
    try:
        import lvgl as lv
        lv.init()
    except Exception as e:
        print(f"[main] lvgl init failed: {e}")

    try:
        from hardware import Hardware
        hw = Hardware()
        hw.init_display()
        hw.init_touch()
        hw.init_encoder()
    except Exception as e:
        print(f"[main] hardware init failed: {e}")
        hw = None

    # Bootstrap next: pick a location (and join its wifi when standalone).
    ns = _run_bootstrap()
    if ns:
        _bootstrap_poll(ns, hw)
        _save_chosen_location(ns.get('info', {}).get('location'))

    # Import and run launcher, reusing the initialized hardware/display.
    from launcher import Launcher

    gc.collect()
    launcher = Launcher(hardware=hw)
    launcher.run()


if __name__ == '__main__':
    main()
