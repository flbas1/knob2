"""
Bootstrap — runs on the knob (and in the sim) before anything else.

The knob reads its location configs from its own /fs1 partition, picks its
location on the display, then reports it in `bootstrap_response`. The PC
server matches the machine config by that location.

How the list is presented:
  * USB / plugged into a machine — the PC server sends an `identify` message
    carrying the machine guid (`_MACHINE_GUID`). If it matches a location,
    that location is preselected (auto-confirmed when unambiguous, otherwise
    shown first).
  * Standalone on wifi — no machine guid. The knob scans for nearby wifi
    networks and shows only the locations whose configured wifi it can reach.
  * Neither (e.g. the simulator) — every location is shown.

If LVGL isn't available, or only one location is relevant, bootstrap skips
the picker and reports immediately.
"""
import json, sys, ubinascii

info = {}

# GUID override — injected by the PC server when the knob is on the USB link.
try:
    info['machine_guid'] = _MACHINE_GUID
except NameError:
    try:
        import machine as _m
        info['machine_guid'] = ubinascii.hexlify(_m.unique_id()).decode().upper()
    except Exception:
        info['machine_guid'] = 'SIM-UNKNOWN'

try:
    import uos
    uname = uos.uname()
    info['machine'] = uname.machine
    info['sysname'] = uname.sysname
    info['release'] = uname.release
except Exception:
    info['machine'] = 'simulator'

info['server_version'] = 'unknown'
try:
    info['server_version'] = _SERVER_VERSION
except NameError:
    pass

info['modules'] = []
for m in ('machine', 'network', 'lvgl'):
    try:
        __import__(m)
        info['modules'].append(m)
    except ImportError:
        pass

def _load_locations_from_fs():
    """Read the knob's location configs from its own /fs1 partition.

    Returns the same {guid, name, location, wifi} entries the server used to
    inject — the knob is self-contained now and doesn't need the server to
    tell it what locations exist."""
    entries = []
    try:
        import os as _os
        for _fname in sorted(_os.listdir('/fs1/locations')):
            if not _fname.endswith('.json'):
                continue
            with open('/fs1/locations/' + _fname) as _f:
                _cfg = json.load(_f)
            _wifi = _cfg.get('wifi') or {}
            entries.append({
                'guid': _cfg.get('machine_guid', ''),
                'name': _cfg.get('name', ''),
                'location': _cfg.get('location', ''),
                'wifi': _wifi.get('ssid', ''),
            })
    except Exception:
        pass
    return entries


# Location entries: the knob reads them from /fs1; the injected list is only a
# browser-sim fallback (the sim has no /fs1 yet).
_machines = []
try:
    _machines = _AVAILABLE_MACHINES
except NameError:
    pass
_fs_entries = _load_locations_from_fs()
if _fs_entries:
    _machines = _fs_entries

# Unique locations, in server order, each tagged with its wifi ssid.
_locations = []
_seen = set()
for _m in _machines:
    _loc = _m.get('location')
    if not _loc or _loc in _seen:
        continue
    _seen.add(_loc)
    _locations.append({'name': _loc, 'wifi': _m.get('wifi') or ''})

info['location'] = _locations[0]['name'] if _locations else 'unknown'


def _find_location_config(location_name):
    """Return the full config (incl. wifi password) for a location name, or None."""
    try:
        import os as _os
        for _fname in sorted(_os.listdir('/fs1/locations')):
            if not _fname.endswith('.json'):
                continue
            with open('/fs1/locations/' + _fname) as _f:
                _cfg = json.load(_f)
            if _cfg.get('location') == location_name:
                return _cfg
    except Exception:
        pass
    return None


def _wifi_join(location_name):
    """Join the chosen location's wifi when the knob is standalone.

    Returns a status string ('connected' / 'failed') when a join was
    attempted, or None when skipped (USB link up, no wifi configured, or no
    `network` module — e.g. the browser sim, where this is a no-op)."""
    try:
        from wifi_connect import on_usb_link, connect as _join
    except Exception:
        return None
    try:
        if on_usb_link():
            return None
    except Exception:
        pass
    _cfg = _find_location_config(location_name)
    if not _cfg:
        return None
    _wifi = _cfg.get('wifi') or {}
    _ssid = _wifi.get('ssid')
    if not _ssid:
        return None
    if _join(_ssid, _wifi.get('password', '')):
        return 'connected'
    return 'failed'


def _report():
    print(json.dumps({'type': 'bootstrap_response', 'data': info}))


try:
    import lvgl as lv
except ImportError:
    lv = None


def _font(*names):
    if lv is None:
        return None
    for n in names:
        f = getattr(lv, n, None)
        if f is not None:
            return f
    return None


def _guid_matches(pattern, guid):
    """Exact match, or a trailing-* prefix glob."""
    if pattern == guid:
        return True
    if pattern and pattern.endswith('*') and guid.startswith(pattern[:-1]):
        return True
    return False


def _wifi_ssids():
    """Set of visible wifi ssids, or None when wifi can't be used."""
    try:
        import network as _net
        wlan = _net.WLAN(_net.STA_IF)
        if not wlan.active():
            wlan.active(True)
        seen = set()
        for entry in wlan.scan():
            ssid = entry[0]
            if isinstance(ssid, bytes):
                try:
                    ssid = ssid.decode()
                except Exception:
                    continue
            if ssid:
                seen.add(str(ssid))
        return seen
    except Exception:
        return None


_selected = 0
_done = False
_scr = None
_title = None
_hint = None
_rows = []

_FONT = _font('font_montserrat_16', 'font_montserrat_14')
_FONT_SMALL = _font('font_montserrat_14', 'font_montserrat_16')


def _clear_scroll(obj):
    try:
        obj.clear_flag(lv.OBJ_FLAG.SCROLLABLE)
    except Exception:
        pass


def _setup_ui():
    global _scr, _title, _hint
    _scr = lv.obj()
    _scr.set_style_bg_color(lv.color_hex(0x000000), 0)
    _clear_scroll(_scr)
    _title = lv.label(_scr)
    _title.set_text('Where are you?')
    _title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    if _FONT:
        _title.set_style_text_font(_FONT, 0)
    _title.align(lv.ALIGN.TOP_MID, 0, 24)
    _hint = lv.label(_scr)
    _hint.set_text('')
    _hint.set_style_text_color(lv.color_hex(0x555555), 0)
    if _FONT_SMALL:
        _hint.set_style_text_font(_FONT_SMALL, 0)
    _hint.align(lv.ALIGN.BOTTOM_MID, 0, -16)
    lv.screen_load(_scr)


def _draw():
    global _rows
    for obj in _rows:
        try:
            obj.delete()
        except Exception:
            pass
    _rows = []
    n = len(_locations)
    if n == 0:
        return
    row_h = min(40, 220 // n)
    start_y = 96
    for i, loc in enumerate(_locations):
        row = lv.obj(_scr)
        row.set_size(240, row_h - 4)
        row.set_pos(60, start_y + i * row_h)
        _clear_scroll(row)
        if i == _selected:
            row.set_style_bg_color(lv.color_hex(0x007AFF), 0)
            row.set_style_bg_opa(lv.OPA.COVER, 0)
        else:
            row.set_style_bg_color(lv.color_hex(0x1A1A2E), 0)
            row.set_style_bg_opa(lv.OPA.COVER, 0)
        lab = lv.label(row)
        lab.set_text(loc['name'])
        if i == _selected:
            lab.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        else:
            lab.set_style_text_color(lv.color_hex(0x999999), 0)
        if _FONT_SMALL:
            lab.set_style_text_font(_FONT_SMALL, 0)
        lab.align(lv.ALIGN.CENTER, 0, 0)
        _rows.append(row)


def _confirm():
    global _done
    if _done:
        return
    _done = True
    if _locations:
        info['location'] = _locations[_selected]['name']
        _wifi_status = _wifi_join(info['location'])
        if _wifi_status:
            info['wifi'] = _wifi_status
        if _title is not None:
            try:
                _title.set_text('Chosen: ' + info['location'])
            except Exception:
                pass
    _report()


def on_encoder(delta):
    if _done or not _locations:
        return
    global _selected
    _selected = (_selected + delta) % len(_locations)
    _draw()


def on_button():
    if _done:
        return
    _confirm()


def on_touch(x, y, pressed):
    if _done or not pressed or not _locations:
        return
    n = len(_locations)
    row_h = min(40, 220 // n)
    start_y = 96
    i = (y - start_y) // row_h
    if 0 <= i < n:
        global _selected
        _selected = i
        _draw()
        _confirm()


# ── Decide how to present the locations ────────────────────────────────
_guid = info.get('machine_guid', '')
_mode = 'all'

# 1) Preselect the machine this knob is plugged into (USB).
_matching = []
if _guid and _guid != 'SIM-UNKNOWN':
    for _m in _machines:
        if (_guid_matches(_m.get('guid') or '', _guid)
                and _m.get('location') and _m['location'] not in _matching):
            _matching.append(_m['location'])
if _matching:
    _locations = [l for l in _locations if l['name'] in _matching]
    _mode = 'preselect'

# 2) Standalone on wifi — show only locations whose wifi is reachable.
if not _matching:
    _visible = _wifi_ssids()
    if _visible:
        _wifi_locs = [l for l in _locations if l['wifi'] and l['wifi'] in _visible]
        if _wifi_locs:
            _locations = _wifi_locs
            _mode = 'wifi'

# Auto-report when there is no display, or nothing to choose.
if lv is None or len(_locations) <= 1:
    _confirm()
else:
    _setup_ui()
    if _mode == 'preselect':
        _hint.set_text('press to confirm')
    elif _mode == 'wifi':
        _hint.set_text('wifi available only')
    _draw()
