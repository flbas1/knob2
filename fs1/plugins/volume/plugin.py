"""
Volume Control Plugin for Smart Knob Controller.

Controls system volume via USB HID Consumer Control.
Also sends input to PC client via WebSocket for display updates.

UI: Large arc (0-100), value label, app name.
"""
try:
    import lvgl as lv
except ImportError:
    lv = None

# Plugin state
_arc = None
_value_label = None
_current_value = 50
_hid = None
_ws_client = None
_app_name = "volume"
_sensitivity = 3


def setup(parent, hardware):
    """Create LVGL widgets for volume control."""
    global _arc, _value_label, _hid, _ws_client

    _hid = hardware.get('hid')
    _ws_client = hardware.get('ws_client')

    # App name at top
    name_label = lv.label(parent)
    name_label.set_text("Volume")
    name_label.set_style_text_color(lv.color_hex(0xAAAAAA), 0)
    name_label.set_style_text_font(_font('font_montserrat_20', 'font_montserrat_24', 'font_montserrat_16'), 0)
    name_label.align(lv.ALIGN.TOP_MID, 0, 22)

    # Arc control (270 degrees, gap at bottom)
    _arc = lv.arc(parent)
    _arc.set_size(240, 240)
    _arc.align(lv.ALIGN.CENTER, 0, -10)
    _arc.set_range(0, 100)
    _arc.set_value(_current_value)

    # Arc angles: 135 to 405 (270 degree sweep)
    _arc.set_start_angle(135)
    _arc.set_end_angle(405)

    # Style: blue indicator, dark background
    _arc.set_style_arc_color(lv.color_hex(0x007AFF), lv.PART.INDICATOR | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.INDICATOR)
    _arc.set_style_arc_color(lv.color_hex(0x333333), lv.PART.MAIN | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.MAIN)

    # Hide arc knob
    _arc.set_style_opa(lv.OPA.TRANSP, lv.PART.KNOB)

    # Value label in center of arc
    _value_label = lv.label(_arc)
    _value_label.set_text(f"{_current_value}%")
    _value_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    _value_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    _value_label.align(lv.ALIGN.CENTER, 0, 0)

    # Speaker icon below arc
    icon_label = lv.label(parent)
    icon_label.set_text(_symbol('SYMBOL_VOLUME_FULL', 'SYMBOL_AUDIO'))
    icon_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    icon_label.set_style_text_color(lv.color_hex(0x007AFF), 0)
    icon_label.align(lv.ALIGN.CENTER, 0, 120)


def start():
    """Called when plugin becomes active."""
    # Ask the PC for the current volume so the arc opens at the real value
    if _ws_client:
        _ws_client.send_data_request(_app_name)
    print("[volume] Active")


def stop():
    """Called when plugin is deactivated."""
    global _arc, _value_label
    if _arc:
        _arc.clean()
        _arc = None
        _value_label = None
    print("[volume] Stopped")


def on_encoder(delta):
    """Handle encoder rotation — adjust volume."""
    global _current_value

    _current_value += delta * _sensitivity
    _current_value = max(0, min(100, _current_value))

    if _arc:
        _arc.set_value(_current_value)
    if _value_label:
        _value_label.set_text(f"{_current_value}%")

    # Send HID volume command
    if _hid:
        if delta > 0:
            for _ in range(abs(delta)):
                _hid.volume_up()
        else:
            for _ in range(abs(delta)):
                _hid.volume_down()

    # Send to PC via WebSocket
    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "set", _current_value)


def on_button():
    """Handle button press — toggle mute."""
    global _current_value

    if _hid:
        _hid.mute()

    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "mute", 0)


def on_data_update(data):
    """Handle data update from PC (e.g., external volume change)."""
    global _current_value

    if 'value' in data:
        _current_value = int(data['value'])
        _current_value = max(0, min(100, _current_value))
        if _arc:
            _arc.set_value(_current_value)
        if _value_label:
            _value_label.set_text(f"{_current_value}%")
