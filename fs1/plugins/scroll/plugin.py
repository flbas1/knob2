"""
Scroll Control Plugin for Smart Knob Controller.

Scrolls the focused window via the PC client (cliclick on macOS, xdotool
on Linux). The knob is a velocity gauge (-10..+10) that eases back to 0.

Scroll has no readable feedback on the PC side (a scrollbar position can't
be queried), so instead of echoing a position the plugin plays an animated
arrow that bounces in the direction of travel.
"""
try:
    import lvgl as lv
except ImportError:
    lv = None

# Plugin state
_arc = None
_value_label = None
_arrow = None
_current_value = 0
_hid = None
_ws_client = None
_app_name = "scroll"
_sensitivity = 1
_arrow_anim = None
_decay_anim = None


def setup(parent, hardware):
    """Create LVGL widgets for scroll control."""
    global _arc, _value_label, _arrow, _hid, _ws_client

    _hid = hardware.get('hid')
    _ws_client = hardware.get('ws_client')

    # App name at top
    name_label = lv.label(parent)
    name_label.set_text("Scroll")
    name_label.set_style_text_color(lv.color_hex(0xAAAAAA), 0)
    name_label.set_style_text_font(_font('font_montserrat_20', 'font_montserrat_24', 'font_montserrat_16'), 0)
    name_label.align(lv.ALIGN.TOP_MID, 0, 22)

    # Arc control (270 degrees, gap at bottom) — velocity gauge
    _arc = lv.arc(parent)
    _arc.set_size(240, 240)
    _arc.align(lv.ALIGN.CENTER, 0, -10)
    _arc.set_range(-10, 10)
    _arc.set_value(_current_value)

    # Arc angles: 135 to 405 (270 degree sweep)
    _arc.set_start_angle(135)
    _arc.set_end_angle(405)

    # Style: orange indicator, dark background
    _arc.set_style_arc_color(lv.color_hex(0xFF9500), lv.PART.INDICATOR | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.INDICATOR)
    _arc.set_style_arc_color(lv.color_hex(0x333333), lv.PART.MAIN | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.MAIN)

    # Hide arc knob
    _arc.set_style_opa(lv.OPA.TRANSP, lv.PART.KNOB)

    # Value label in center of arc
    _value_label = lv.label(_arc)
    _value_label.set_text("0")
    _value_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    _value_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    _value_label.align(lv.ALIGN.CENTER, 0, 0)

    # Scroll direction arrow below arc — the scroll feedback
    _arrow = lv.label(parent)
    _arrow.set_text(_symbol('SYMBOL_UP', 'SYMBOL_REFRESH'))
    _arrow.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    _arrow.set_style_text_color(lv.color_hex(0xFF9500), 0)
    _arrow.align(lv.ALIGN.CENTER, 0, 130)
    _arrow.set_style_opa(0, 0)


def start():
    """Called when plugin becomes active."""
    print("[scroll] Active")


def stop():
    """Called when plugin is deactivated."""
    global _arc, _value_label, _arrow
    if _arc:
        _arc.clean()
        _arc = None
        _value_label = None
        _arrow = None
    print("[scroll] Stopped")


def _pulse_arrow(direction):
    """Bounce the direction arrow to show scrolling happened."""
    global _arrow, _arrow_anim
    if _arrow is None or lv is None:
        return
    try:
        _arrow.set_text(
            _symbol('SYMBOL_UP', 'SYMBOL_REFRESH') if direction > 0
            else _symbol('SYMBOL_DOWN', 'SYMBOL_REFRESH'))

        if _arrow_anim is None:
            _arrow_anim = lv.anim_t()
            _arrow_anim.init()
            _arrow_anim.set_var(_arrow)
            _arrow_anim.set_time(220)
            _arrow_anim.set_playback_time(220)
            _arrow_anim.set_repeat_count(1)
            _arrow_anim.set_custom_exec_cb(_arrow_exec_cb)
        _arrow_anim.set_values(255, 0)
        _arrow_anim.start()
    except Exception as e:
        print(f"[scroll] Arrow anim error: {e}")


def _arrow_exec_cb(a, v):
    """Animation step: fade the arrow, lifting it in the travel direction."""
    global _arrow, _current_value
    if _arrow is None:
        return
    _arrow.set_style_opa(v, 0)
    if _current_value != 0:
        _arrow.set_y(130 - int(_current_value / abs(_current_value)) * (v // 12))


def _decay_arc():
    """Ease the velocity gauge back to 0 after a scroll."""
    global _arc, _value_label, _decay_anim, _current_value
    if _arc is None or lv is None:
        return
    try:
        if _decay_anim is None:
            _decay_anim = lv.anim_t()
            _decay_anim.init()
            _decay_anim.set_var(_arc)
            _decay_anim.set_time(450)
            _decay_anim.set_repeat_count(0)
            _decay_anim.set_custom_exec_cb(_decay_exec_cb)
        _decay_anim.set_values(_current_value, 0)
        _decay_anim.start()
    except Exception as e:
        print(f"[scroll] Decay anim error: {e}")


def _decay_exec_cb(a, v):
    """Animation step: drive the arc + label toward 0."""
    global _arc, _value_label, _current_value
    if _arc is not None:
        _arc.set_value(int(round(v)))
    if _value_label is not None:
        _value_label.set_text(f"{int(round(v)):+d}")


def on_encoder(delta):
    """Handle encoder rotation — scroll by the per-notch delta."""
    global _current_value

    _current_value += delta * _sensitivity
    _current_value = max(-10, min(10, _current_value))

    if _arc:
        _arc.set_value(_current_value)
    if _value_label:
        _value_label.set_text(f"{_current_value:+d}")

    # Send the delta for THIS turn only (not the accumulated velocity) —
    # the server scrolls abs(value) notches per message.
    if _hid and delta != 0:
        direction = 1 if delta > 0 else -1
        for _ in range(abs(delta) * _sensitivity):
            _hid.scroll(direction)

    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "scroll", delta * _sensitivity)

    if delta != 0:
        _pulse_arrow(delta)
        _decay_arc()


def on_button():
    """Handle button press — reset the velocity gauge."""
    global _current_value
    _current_value = 0
    if _arc:
        _arc.set_value(_current_value)
    if _value_label:
        _value_label.set_text("0")
    if _arrow is not None:
        _arrow.set_style_opa(0, 0)


def on_data_update(data):
    """Handle data update from PC (scroll has no readable position)."""
    global _current_value
    if 'value' in data:
        _current_value = max(-10, min(10, int(data['value'])))
        if _arc:
            _arc.set_value(_current_value)
        if _value_label:
            _value_label.set_text(f"{_current_value:+d}")
