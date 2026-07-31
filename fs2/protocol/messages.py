"""
Shared protocol definitions for Smart Knob Controller.

Message types and format constants used by both knob firmware
and PC/iOS/Android clients.

Protocol (server-driven bootstrap):
    execute  (server → knob)  run MicroPython code
    config   (server → knob)  machine config
    bootstrap_response (knob → server)  identity after bootstrap
    config_ack (knob → server)  config accepted
    launcher_ready (knob → server)  launcher UI live
    app_selected (knob → server)  user picked an app
    action   (knob → server)  app command (volume, brightness, zoom, scroll)
    data_update (either)  app-specific state push
    data_request (knob → server)  request current state
"""

# Message types (server → knob)
MSG_EXECUTE = "execute"
MSG_CONFIG = "config"

# Message types (knob → server)
MSG_BOOTSTRAP_RESPONSE = "bootstrap_response"
MSG_CONFIG_ACK = "config_ack"
MSG_LAUNCHER_READY = "launcher_ready"
MSG_APP_SELECTED = "app_selected"
MSG_ACTION = "action"
MSG_DATA_REQUEST = "data_request"

# Message types (either direction)
MSG_DATA_UPDATE = "data_update"


def make_execute(code, machines=None):
    """Server sends MicroPython code for the knob to run.

    `machines` is an optional list of {guid, name, location} dicts
    used by the simulator to populate its Machine dropdown.
    """
    msg = {"type": MSG_EXECUTE, "code": code}
    if machines is not None:
        msg["machines"] = machines
    return msg


def make_config(config):
    """Server sends the matched machine config."""
    return {"type": MSG_CONFIG, "config": config}


def make_bootstrap_response(info):
    """Knob reports its identity after running bootstrap.py.

    `info` carries at minimum `machine_guid` (and `machine` name).
    """
    return {"type": MSG_BOOTSTRAP_RESPONSE, "data": info}


def make_config_ack(status="ok"):
    """Knob acknowledges the config was accepted."""
    return {"type": MSG_CONFIG_ACK, "status": status}


def make_launcher_ready(apps):
    """Knob announces the launcher UI is live with its app list."""
    return {"type": MSG_LAUNCHER_READY, "apps": apps}


def make_app_selected(app):
    """Knob sends this when the user selects an app."""
    return {"type": MSG_APP_SELECTED, "app": app}


def make_action(app, cmd, value=None):
    """Knob sends an app command (volume up, brightness set, scroll, zoom)."""
    return {"type": MSG_ACTION, "app": app, "cmd": cmd, "value": value}


def make_data_update(app, data):
    """Server (or knob) pushes app-specific state."""
    return {"type": MSG_DATA_UPDATE, "app": app, "data": data}


def make_data_request(app):
    """Knob requests current state from the server for an app."""
    return {"type": MSG_DATA_REQUEST, "app": app}
