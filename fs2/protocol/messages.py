"""
Shared protocol definitions for Smart Knob Controller.

Message types and format constants used by both knob firmware
and PC/iOS/Android clients.
"""

# Message types (knob → PC)
MSG_DISCOVER = "discover"
MSG_PLUGIN_INPUT = "plugin_input"
MSG_APP_SWITCH = "app_switch"
MSG_DATA_REQUEST = "data_request"

# Message types (PC → knob)
MSG_IDENTIFY = "identify"
MSG_DATA_UPDATE = "data_update"
MSG_STATE_UPDATE = "state_update"


def make_discover():
    """Knob sends this on connection."""
    return {"type": MSG_DISCOVER}


def make_identify(device, platform, version="1.0.0"):
    """PC responds with this to identify itself."""
    return {
        "type": MSG_IDENTIFY,
        "device": device,
        "platform": platform,
        "version": version
    }


def make_plugin_input(app, action, value):
    """Knob sends this when user interacts with a plugin."""
    return {
        "type": MSG_PLUGIN_INPUT,
        "app": app,
        "action": action,
        "value": value
    }


def make_data_update(app, data):
    """PC sends this to update knob display with new data."""
    return {
        "type": MSG_DATA_UPDATE,
        "app": app,
        "data": data
    }


def make_app_switch(app):
    """Knob sends this when user switches apps."""
    return {
        "type": MSG_APP_SWITCH,
        "app": app
    }


def make_state_update(state):
    """PC sends this to update knob state."""
    return {
        "type": MSG_STATE_UPDATE,
        "state": state
    }


def make_data_request(app):
    """Knob sends this to request data from PC for an app."""
    return {
        "type": MSG_DATA_REQUEST,
        "app": app
    }
