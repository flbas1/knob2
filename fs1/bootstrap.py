import json, sys, ubinascii

info = {}

# GUID override — set by JS from user's text input before sending to MicroPython
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

info['location'] = 'unknown'
try:
    matches = [m.get('location', 'unknown') for m in _AVAILABLE_MACHINES
               if m.get('guid') == info.get('machine_guid')]
    if matches:
        info['location'] = matches[0]
except NameError:
    pass

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

print(json.dumps({'type': 'bootstrap_response', 'data': info}))
