"""
Shared protocol definitions for Smart Knob Controller.

Import all message constructors:
    from protocol import make_discover, make_identify, make_plugin_input
"""
from .messages import (
    MSG_DISCOVER,
    MSG_IDENTIFY,
    MSG_DATA_UPDATE,
    MSG_PLUGIN_INPUT,
    MSG_APP_SWITCH,
    MSG_STATE_UPDATE,
    MSG_DATA_REQUEST,
    make_discover,
    make_identify,
    make_plugin_input,
    make_data_update,
    make_app_switch,
    make_state_update,
    make_data_request,
)
