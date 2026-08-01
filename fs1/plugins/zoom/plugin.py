"""
Zoom Control Plugin for Smart Knob Controller.

Sends Ctrl+MouseWheel via USB HID for zoom in/out.
Also sends input to PC client via WebSocket.

UI: Large arc (0-100), value label, app name.
"""
try:
    import lvgl as lv
except ImportError:
    lv = None

_arc = None
_value_label = None
_current_value = 50
_hid = None
_ws_client = None
_app_name = "zoom"
_sensitivity = 3


def setup(parent, hardware):
    global _arc, _value_label, _hid, _ws_client

    _hid = hardware.get('hid')
    _ws_client = hardware.get('ws_client')

    name_label = lv.label(parent)
    name_label.set_text("Zoom")
    name_label.set_style_text_color(lv.color_hex(0xAAAAAA), 0)
    name_label.set_style_text_font(_font('font_montserrat_20', 'font_montserrat_24', 'font_montserrat_16'), 0)
    name_label.align(lv.ALIGN.TOP_MID, 0, 40)

    _arc = lv.arc(parent)
    _arc.set_size(240, 240)
    _arc.align(lv.ALIGN.CENTER, 0, -10)
    _arc.set_range(0, 100)
    _arc.set_value(_current_value)
    _arc.set_start_angle(135)
    _arc.set_end_angle(405)

    _arc.set_style_arc_color(lv.color_hex(0x34C759), lv.PART.INDICATOR | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.INDICATOR)
    _arc.set_style_arc_color(lv.color_hex(0x333333), lv.PART.MAIN | lv.STATE.DEFAULT)
    _arc.set_style_arc_width(12, lv.PART.MAIN)
    _arc.set_style_opa(lv.OPA.TRANSP, lv.PART.KNOB)

    _value_label = lv.label(_arc)
    _value_label.set_text(f"{_current_value}%")
    _value_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    _value_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    _value_label.align(lv.ALIGN.CENTER, 0, 0)

    icon_label = lv.label(parent)
    icon_label.set_text(_symbol('SYMBOL_ZOOM_IN', 'SYMBOL_EDIT', 'SYMBOL_LEFT'))
    icon_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    icon_label.set_style_text_color(lv.color_hex(0x34C759), 0)
    icon_label.align(lv.ALIGN.CENTER, 0, 120)


def start():
    print("[zoom] Active")


def stop():
    global _arc, _value_label
    if _arc:
        _arc.clean()
        _arc = None
        _value_label = None
    print("[zoom] Stopped")


def on_encoder(delta):
    global _current_value

    _current_value += delta * _sensitivity
    _current_value = max(0, min(100, _current_value))

    if _arc:
        _arc.set_value(_current_value)
    if _value_label:
        _value_label.set_text(f"{_current_value}%")

    # Send HID zoom (Ctrl+MouseWheel)
    if _hid:
        if delta > 0:
            for _ in range(abs(delta)):
                _hid.zoom_in()
        else:
            for _ in range(abs(delta)):
                _hid.zoom_out()

    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "set", _current_value)


def on_button():
    global _current_value
    _current_value = 50
    if _arc:
        _arc.set_value(_current_value)
    if _value_label:
        _value_label.set_text(f"{_current_value}%")
    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "reset", 50)


def on_data_update(data):
    global _current_value
    if 'value' in data:
        _current_value = max(0, min(100, int(data['value'])))
        if _arc:
            _arc.set_value(_current_value)
        if _value_label:
            _value_label.set_text(f"{_current_value}%")
