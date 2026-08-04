"""
Girlfriend plugin for Smart Knob Controller.

Rotate the knob to cycle through her moods. Each mode has its own color,
a little status line, and a few things she says. Press the button to make
her say something.
"""
try:
    import lvgl as lv
except ImportError:
    lv = None

# (name, color, status, things she says)
MODES = (
    ("Mute",     0x8E8E93, "not talking to you",
     ("...", "i'm giving you the silent treatment", "ask nicely")),
    ("Clean",    0xAF52DE, "tidying the flat",
     ("leave the mess to me", "who left these socks here?", "feather duster time")),
    ("Relax",    0x34C759, "chilling on the couch",
     ("this is the life", "come sit with me", "best day ever")),
    ("Watch TV", 0x5AC8FA, "binge-watching our show",
     ("one more episode?", "i called the good seat", "shh, it's the twist")),
    ("Romance",  0xFF2D55, "feeling flirty",
     ("you make my day", "get over here", "you look good today")),
    ("Cook",     0xFF9500, "making us dinner",
     ("taste tester needed", "it's almost ready", "you're on dishes")),
    ("Sleep",    0x5856D6, "nap time",
     ("five more minutes", "wake me for dinner", "the couch is mine")),
)

_app_name = "girlfriend"
_mode_index = 0
_line_index = 0

_ring = None
_name_label = None
_status_label = None
_speech_label = None
_hid = None
_ws_client = None
_pulse_anim = None


def setup(parent, hardware):
    """Create LVGL widgets for the girlfriend app."""
    global _ring, _name_label, _status_label, _speech_label, _hid, _ws_client

    _hid = hardware.get('hid')
    _ws_client = hardware.get('ws_client')

    title = lv.label(parent)
    title.set_text("Girlfriend")
    title.set_style_text_color(lv.color_hex(0xAAAAAA), 0)
    title.set_style_text_font(_font('font_montserrat_20', 'font_montserrat_24', 'font_montserrat_16'), 0)
    title.align(lv.ALIGN.TOP_MID, 0, 22)

    _ring = lv.arc(parent)
    _ring.set_size(300, 300)
    _ring.align(lv.ALIGN.CENTER, 0, -4)
    _ring.set_range(0, 100)
    _ring.set_value(100)
    _ring.set_start_angle(0)
    _ring.set_end_angle(360)
    _ring.set_style_arc_width(14, lv.PART.INDICATOR)
    _ring.set_style_arc_width(14, lv.PART.MAIN)
    _ring.set_style_arc_color(lv.color_hex(0x333333), lv.PART.MAIN | lv.STATE.DEFAULT)
    _ring.set_style_opa(lv.OPA.TRANSP, lv.PART.KNOB)

    _name_label = lv.label(parent)
    _name_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    _name_label.set_style_text_font(_font('font_montserrat_28', 'font_montserrat_24', 'font_montserrat_16'), 0)
    _name_label.align(lv.ALIGN.CENTER, 0, -30)

    _status_label = lv.label(parent)
    _status_label.set_style_text_color(lv.color_hex(0x999999), 0)
    _status_label.set_style_text_font(_font('font_montserrat_16', 'font_montserrat_14', 'font_montserrat_10'), 0)
    _status_label.align(lv.ALIGN.CENTER, 0, 4)

    _speech_label = lv.label(parent)
    _speech_label.set_style_text_font(_font('font_montserrat_16', 'font_montserrat_14', 'font_montserrat_10'), 0)
    _speech_label.align(lv.ALIGN.CENTER, 0, 34)

    _draw()


def start():
    """Called when plugin becomes active."""
    global _mode_index, _line_index
    _mode_index = 0
    _line_index = 0
    _draw()
    print("[girlfriend] Active")


def stop():
    """Called when plugin is deactivated."""
    global _ring, _name_label, _status_label, _speech_label
    if _ring:
        _ring.clean()
        _ring = None
        _name_label = None
        _status_label = None
        _speech_label = None
    print("[girlfriend] Stopped")


def _draw():
    """Apply the current mode's color, name, and status."""
    global _ring, _name_label, _status_label, _speech_label
    name, color, status, _lines = MODES[_mode_index]
    if _ring:
        _ring.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR | lv.STATE.DEFAULT)
    if _name_label:
        _name_label.set_text(name)
    if _status_label:
        _status_label.set_text(status)
    if _speech_label:
        _speech_label.set_text("")
        _speech_label.set_style_text_color(lv.color_hex(color), 0)


def on_encoder(delta):
    """Handle encoder rotation — cycle her moods."""
    global _mode_index, _line_index
    if delta == 0:
        return
    _line_index = 0
    _mode_index = (_mode_index + delta) % len(MODES)
    _draw()
    _pulse_ring()
    if _ws_client:
        _ws_client.send_plugin_input(_app_name, "mode", _mode_index)


def on_button():
    """Handle button press — she says something."""
    global _line_index
    _name, _color, _status, lines = MODES[_mode_index]
    if not lines:
        return
    _line_index = (_line_index + 1) % len(lines)
    if _speech_label:
        _speech_label.set_text(lines[_line_index])


def on_data_update(data):
    """Handle data update from PC (nothing to sync)."""
    pass


def _pulse_ring():
    """Pulse the ring's brightness to show the mood change."""
    global _ring, _pulse_anim
    if _ring is None or lv is None:
        return
    try:
        if _pulse_anim is None:
            _pulse_anim = lv.anim_t()
            _pulse_anim.init()
            _pulse_anim.set_var(_ring)
            _pulse_anim.set_time(180)
            _pulse_anim.set_playback_time(180)
            _pulse_anim.set_repeat_count(1)
            _pulse_anim.set_custom_exec_cb(_pulse_exec_cb)
        _pulse_anim.set_values(255, 130)
        _pulse_anim.start()
    except Exception as e:
        print(f"[girlfriend] Pulse error: {e}")


def _pulse_exec_cb(a, v):
    """Animation step: dim the ring, then let playback restore it."""
    global _ring
    if _ring is not None:
        _ring.set_style_opa(int(v), lv.PART.INDICATOR)
