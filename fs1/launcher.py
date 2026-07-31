"""
Launcher for Smart Knob Controller.

The launcher manages the home screen and plugin switching.
It owns the LVGL event loop and routes input to the active plugin.

Home screen shows plugin icons in a diamond/cross pattern on the
360x360 round display. Encoder navigates, button selects.
"""
import gc
import json
import os
from time import sleep_ms

try:
    import lvgl as lv
    LVGL_AVAILABLE = True
except ImportError:
    LVGL_AVAILABLE = False
    print("[launcher] LVGL not available — running in stub mode")


# Icon positions on 360x360 display (diamond/cross pattern)
ICON_POSITIONS = [
    (0, -110),    # Top
    (110, 0),     # Right
    (0, 110),     # Bottom
    (-110, 0),    # Left
]

# LVGL symbol mapping for common plugin icons
ICON_SYMBOLS = {
    'volume': lv.SYMBOL_VOLUME_FULL if LVGL_AVAILABLE else None,
    'zoom': lv.SYMBOL_ZOOM_IN if LVGL_AVAILABLE else None,
    'scroll': lv.SYMBOL_REFRESH if LVGL_AVAILABLE else None,
    'brightness': lv.SYMBOL_BRIGHTNESS if LVGL_AVAILABLE else None,
    'music': lv.SYMBOL_AUDIO if LVGL_AVAILABLE else None,
    'settings': lv.SYMBOL_SETTINGS if LVGL_AVAILABLE else None,
    'default': lv.SYMBOL_WIFI if LVGL_AVAILABLE else None,
}

# Animation types
ANIM_NONE = 'none'
ANIM_PULSE = 'pulse'
ANIM_ROTATE = 'rotate'
ANIM_BOUNCE = 'bounce'


class Launcher:
    """Home screen launcher with plugin switching."""

    def __init__(self):
        self.hardware = None
        self.plugin_mgr = None
        self.ws_client = None
        self.hid = None
        self.machine_config = None

        # LVGL objects
        self.scr_home = None
        self.scr_plugin = None
        self.home_icons = []
        self.home_labels = []
        self.home_selected = 0
        self.machine_label = None
        self.plugin_container = None

        # State
        self.current_screen = 'home'  # 'home' or 'plugin'
        self.enabled_plugins = []

    def run(self):
        """Main entry point. Initializes everything and runs the event loop."""
        # Initialize hardware
        from hardware import Hardware
        self.hardware = Hardware()

        if not LVGL_AVAILABLE:
            print("[launcher] LVGL not available. Exiting.")
            return

        # Initialize LVGL
        lv.init()
        self._init_display()
        self._init_touch()
        self._init_encoder()
        self._init_hid()
        self._init_websocket()
        self._load_machine_config()

        # Initialize plugin manager
        from plugin_manager import PluginManager
        self.plugin_mgr = PluginManager(self.hardware)

        # Filter plugins by machine config
        self._filter_plugins()

        # Create screens
        self._create_home_screen()
        self._create_plugin_screen()

        # Load home screen
        lv.screen_load(self.scr_home)

        print("[launcher] Ready. Entering main loop.")
        self._main_loop()

    def _init_display(self):
        """Initialize display and register LVGL flush callback (LVGL v9 API)."""
        self.hardware.init_display()

    def _init_touch(self):
        """Initialize touch and register LVGL input driver (LVGL v9 API)."""
        touch = self.hardware.init_touch()

        indev = lv.indev_create()
        indev.type = lv.INDEV_TYPE.POINTER
        indev.read_cb = self._touch_cb

    def _init_encoder(self):
        """Initialize encoder (polled from main loop, NOT LVGL indev)."""
        self.hardware.init_encoder()

    def _init_hid(self):
        """Initialize USB HID device."""
        try:
            from hid import HIDDevice
            self.hid = HIDDevice()
            self.hid.init()
            self.hardware._hid = self.hid
        except Exception as e:
            print(f"[launcher] HID init failed: {e}")

    def _init_websocket(self):
        """Initialize WebSocket client."""
        try:
            from ws_client import WSClient
            ws_uri = self._load_ws_uri()
            self.ws_client = WSClient(uri=ws_uri)
            self.hardware._ws = self.ws_client
            self.ws_client.set_message_callback(self._on_ws_message)
        except Exception as e:
            print(f"[launcher] WebSocket init failed: {e}")

    def _load_ws_uri(self):
        """Load WebSocket URI from settings or use default."""
        try:
            with open('/fs1/settings.json', 'r') as f:
                settings = json.load(f)
            return settings.get('websocket_uri', 'ws://10.10.10.2:8765')
        except:
            return 'ws://10.10.10.2:8765'

    def _load_machine_config(self):
        """Load machine config from fs1/machines/."""
        try:
            machines = os.listdir('/fs1/machines')
            for fname in machines:
                if fname.endswith('.json'):
                    with open(f'/fs1/machines/{fname}', 'r') as f:
                        self.machine_config = json.load(f)
                    print(f"[launcher] Loaded machine: {self.machine_config.get('name', fname)}")
                    return
        except OSError:
            print("[launcher] No machines directory found — all plugins enabled")

    def _filter_plugins(self):
        """Determine which plugins to show based on machine config."""
        all_plugins = self.plugin_mgr.get_plugin_list()

        if self.machine_config and 'plugins' in self.machine_config:
            enabled = self.machine_config['plugins']
            self.enabled_plugins = [
                (pid, manifest) for pid, manifest in all_plugins
                if pid in enabled
            ]
        else:
            # No config — show all plugins (setup mode)
            self.enabled_plugins = all_plugins

        print(f"[launcher] Enabled plugins: {[p[0] for p in self.enabled_plugins]}")

    def _create_home_screen(self):
        """Create the home screen with plugin icons."""
        self.scr_home = lv.obj()
        self.scr_home.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.scr_home.clear_flag(lv.OBJ_FLAG.SCROLLABLE)

        # Machine name label in center
        self.machine_label = lv.label(self.scr_home)
        machine_name = "Connecting..."
        if self.machine_config:
            machine_name = self.machine_config.get('name', 'Knob')
        self.machine_label.set_text(machine_name)
        self.machine_label.set_style_text_color(lv.color_hex(0x666666), 0)
        self.machine_label.set_style_text_font(lv.font_montserrat_14, 0)
        self.machine_label.align(lv.ALIGN.CENTER, 0, 0)

        # Create icon buttons
        self.home_icons = []
        self.home_labels = []

        for i, (plugin_id, manifest) in enumerate(self.enabled_plugins):
            if i >= 4:
                break  # Max 4 icons on home screen

            x_off, y_off = ICON_POSITIONS[i]

            # Icon container (circle)
            icon_obj = lv.obj(self.scr_home)
            icon_obj.set_size(70, 70)
            icon_obj.set_style_radius(35, 0)
            icon_obj.set_style_border_width(2, 0)
            icon_obj.set_style_bg_opa(lv.OPA.TRANSP, 0)
            icon_obj.align(lv.ALIGN.CENTER, x_off, y_off)
            icon_obj.clear_flag(lv.OBJ_FLAG.SCROLLABLE)
            icon_obj.set_style_pad_all(0, 0)

            # Icon symbol
            icon_label = lv.label(icon_obj)
            icon_symbol = manifest.get('icon', 'default')
            symbol_char = ICON_SYMBOLS.get(icon_symbol, ICON_SYMBOLS['default'])
            if symbol_char:
                icon_label.set_text(symbol_char)
            icon_label.set_style_text_font(lv.font_montserrat_28, 0)
            icon_label.align(lv.ALIGN.CENTER, 0, -8)

            # Plugin name below icon
            name_label = lv.label(icon_obj)
            name_label.set_text(manifest.get('name', plugin_id)[:8])
            name_label.set_style_text_font(lv.font_montserrat_10, 0)
            name_label.align(lv.ALIGN.CENTER, 0, 18)

            self.home_icons.append(icon_obj)
            self.home_labels.append(name_label)

        # Update initial selection
        self._update_home_selection()

    def _create_plugin_screen(self):
        """Create the plugin screen (shared container for all plugins)."""
        self.scr_plugin = lv.obj()
        self.scr_plugin.set_style_bg_color(lv.color_hex(0x000000), 0)
        self.scr_plugin.clear_flag(lv.OBJ_FLAG.SCROLLABLE)

        # Plugin container (full screen, plugins add widgets to this)
        self.plugin_container = self.scr_plugin

    def _update_home_selection(self):
        """Update visual state of home screen icons."""
        for i, icon_obj in enumerate(self.home_icons):
            if i >= len(self.enabled_plugins):
                icon_obj.add_flag(lv.OBJ_FLAG.HIDDEN)
                continue

            icon_obj.clear_flag(lv.OBJ_FLAG.HIDDEN)

            if i == self.home_selected:
                icon_obj.set_style_bg_color(lv.color_hex(0x007AFF), 0)
                icon_obj.set_style_bg_opa(lv.OPA.COVER, 0)
                icon_obj.set_style_border_color(lv.color_hex(0x007AFF), 0)
                self.home_labels[i].set_style_text_color(lv.color_hex(0xFFFFFF), 0)
            else:
                icon_obj.set_style_bg_opa(lv.OPA.TRANSP, 0)
                icon_obj.set_style_border_color(lv.color_hex(0x555555), 0)
                self.home_labels[i].set_style_text_color(lv.color_hex(0x888888), 0)

    def _enter_plugin(self, index):
        """Enter a plugin from the home screen."""
        if index >= len(self.enabled_plugins):
            return

        plugin_id, manifest = self.enabled_plugins[index]

        # Activate plugin (creates LVGL widgets in plugin_container)
        success = self.plugin_mgr.activate(plugin_id, self.plugin_container)
        if not success:
            print(f"[launcher] Failed to activate plugin: {plugin_id}")
            return

        self.current_screen = 'plugin'

        # Notify PC
        if self.ws_client:
            self.ws_client.send_app_switch(plugin_id)

        # Switch to plugin screen
        lv.screen_load(self.scr_plugin)

    def _go_home(self):
        """Return to home screen from plugin."""
        self.plugin_mgr.deactivate()
        self.current_screen = 'home'
        self._update_home_selection()
        lv.screen_load(self.scr_home)

    def _on_ws_message(self, msg):
        """Handle incoming WebSocket messages from PC."""
        msg_type = msg.get('type', '')

        if msg_type == 'identify':
            # PC identified itself — update machine config
            device = msg.get('device', 'unknown')
            platform = msg.get('platform', 'unknown')
            print(f"[launcher] PC identified: {device} ({platform})")
            # Try to load matching machine config
            self._load_machine_config_for_device(device, platform)
            self._filter_plugins()
            # Recreate home screen with new plugins
            self._create_home_screen()
            lv.screen_load(self.scr_home)

        elif msg_type == 'data_update':
            # Data update for a specific app
            app = msg.get('app', '')
            data = msg.get('data', {})
            if self.plugin_mgr.is_active():
                self.plugin_mgr.on_data_update(data)

    def _load_machine_config_for_device(self, device, platform):
        """Try to load a machine config matching the connected device."""
        try:
            machines = os.listdir('/fs1/machines')
            for fname in machines:
                if fname.endswith('.json'):
                    with open(f'/fs1/machines/{fname}', 'r') as f:
                        config = json.load(f)
                    # Match by name or platform
                    if (config.get('machine_id') == device or
                        config.get('platform') == platform):
                        self.machine_config = config
                        print(f"[launcher] Matched machine: {config.get('name', fname)}")
                        return
        except OSError:
            pass

    def _main_loop(self):
        """Main event loop — polls encoder, touch, WebSocket, refreshes LVGL."""
        from encoder import ENCODER_NONE, ENCODER_CW, ENCODER_CCW, ENCODER_BUTTON
        from time import ticks_ms, ticks_diff

        last_tick = ticks_ms()
        ws_poll_interval = 50  # ms between WebSocket polls
        last_ws_poll = ticks_ms()

        while True:
            now = ticks_ms()

            # LVGL tick
            elapsed = ticks_diff(now, last_tick)
            if elapsed > 0:
                lv.tick_inc(elapsed)
                last_tick = now

            # LVGL timer handler
            lv.timer_handler()

            # Poll encoder
            if self.hardware.encoder:
                event = self.hardware.encoder.poll()
                if event == ENCODER_CW:
                    self._handle_encoder(1)
                elif event == ENCODER_CCW:
                    self._handle_encoder(-1)
                elif event == ENCODER_BUTTON:
                    self._handle_button()

            # Poll touch
            if self.hardware.touch:
                pressed, x, y, gesture = self.hardware.touch.read()
                Launcher._update_touch_cache(pressed, x, y)
                if self.current_screen == 'home' and pressed and gesture == 0x05:
                    self._handle_touch(x, y)

            # Poll WebSocket
            if self.ws_client and ticks_diff(now, last_ws_poll) > ws_poll_interval:
                self.ws_client.poll()
                last_ws_poll = now

            # Yield to other tasks
            sleep_ms(5)

    def _handle_encoder(self, delta):
        """Route encoder event to appropriate handler."""
        if self.current_screen == 'home':
            # Navigate between icons
            count = len(self.enabled_plugins)
            if count > 0:
                self.home_selected = (self.home_selected + delta) % count
                self._update_home_selection()
        elif self.current_screen == 'plugin':
            # Forward to active plugin
            self.plugin_mgr.on_encoder(delta)

    def _handle_button(self):
        """Route button press to appropriate handler."""
        if self.current_screen == 'home':
            self._enter_plugin(self.home_selected)
        elif self.current_screen == 'plugin':
            self._go_home()

    def _handle_touch(self, x, y):
        """Handle touch on home screen — check if an icon was tapped."""
        # Simple hit testing against icon positions
        for i, (plugin_id, manifest) in enumerate(self.enabled_plugins):
            if i >= 4:
                break
            ix, iy = ICON_POSITIONS[i]
            ix += 180  # Center offset
            iy += 180
            # Check if touch is within icon radius (35px)
            dx = x - ix
            dy = y - iy
            if dx * dx + dy * dy < 35 * 35:
                self._enter_plugin(i)
                return

    # LVGL callbacks
    @staticmethod
    def _flush_cb(disp_drv, area, color_p):
        """LVGL display flush callback — routed to SH8601 driver."""
        import sh8601 as _hw
        _hw.flush(disp_drv, area, color_p)

    @staticmethod
    def _touch_cb(indev_drv, data):
        """LVGL touch read callback — reads cached state from main loop."""
        cached = getattr(Launcher, '_touch_cache', None)
        if cached:
            px, py, pstate = cached
            data.point.x = px
            data.point.y = py
            data.state = pstate
        else:
            data.state = lv.INDEV_STATE.RELEASED

    @staticmethod
    def _update_touch_cache(pressed, x, y):
        """Update cached touch state for LVGL callback."""
        Launcher._touch_cache = (
            x, y,
            lv.INDEV_STATE.PRESSED if pressed else lv.INDEV_STATE.RELEASED
        )
