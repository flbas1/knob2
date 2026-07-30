"""
Plugin Manager for Smart Knob Controller.

Loads plugin Python modules from fs1/plugins/,
manages their lifecycle, and routes input events.
"""
import os
import json
import gc


class PluginManager:
    """Manages loading, switching, and input routing for plugins."""

    def __init__(self, hardware):
        self.hardware = hardware
        self.plugins = {}        # id -> manifest dict
        self.plugin_modules = {} # id -> module object
        self.active_id = None
        self.active_module = None
        self._scan_plugins()

    def _scan_plugins(self):
        """Scan fs1/plugins/ for manifest.json files."""
        try:
            plugin_dirs = os.listdir('/fs1/plugins')
        except OSError:
            print("[plugin_mgr] No plugins directory found")
            return

        for dir_name in plugin_dirs:
            manifest_path = f'/fs1/plugins/{dir_name}/manifest.json'
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                plugin_id = manifest.get('id', dir_name)
                self.plugins[plugin_id] = manifest
                print(f"[plugin_mgr] Found plugin: {plugin_id}")
            except Exception as e:
                print(f"[plugin_mgr] Skipping {dir_name}: {e}")

    def get_plugin_list(self):
        """Return list of (id, manifest) tuples for all loaded plugins."""
        return list(self.plugins.items())

    def get_plugin_manifest(self, plugin_id):
        """Return manifest dict for a plugin."""
        return self.plugins.get(plugin_id)

    def load_plugin(self, plugin_id):
        """Load a plugin module from fs1/plugins/<id>/plugin.py.

        Returns the module, or None on failure.
        """
        if plugin_id in self.plugin_modules:
            return self.plugin_modules[plugin_id]

        manifest = self.plugins.get(plugin_id)
        if not manifest:
            print(f"[plugin_mgr] Unknown plugin: {plugin_id}")
            return None

        entry = manifest.get('entry', 'plugin.py')
        module_path = f'/fs1/plugins/{plugin_id}/{entry[:-3]}'

        try:
            # Import the plugin module
            import sys
            sys.path.insert(0, f'/fs1/plugins/{plugin_id}')
            module = __import__(entry[:-3])  # Import without .py
            sys.path.pop(0)

            self.plugin_modules[plugin_id] = module
            print(f"[plugin_mgr] Loaded plugin: {plugin_id}")
            return module
        except Exception as e:
            print(f"[plugin_mgr] Failed to load {plugin_id}: {e}")
            return None

    def activate(self, plugin_id, parent_obj):
        """Activate a plugin: call stop() on current, load + start() new.

        Args:
            plugin_id: Plugin to activate
            parent_obj: LVGL parent object for the plugin to create widgets in
        """
        # Deactivate current plugin
        if self.active_module and hasattr(self.active_module, 'stop'):
            try:
                self.active_module.stop()
            except Exception as e:
                print(f"[plugin_mgr] stop() failed: {e}")

        # Load new plugin if not already loaded
        module = self.load_plugin(plugin_id)
        if not module:
            return False

        self.active_id = plugin_id
        self.active_module = module

        # Setup plugin (create LVGL widgets)
        if hasattr(module, 'setup'):
            try:
                module.setup(parent_obj, {
                    'encoder': self.hardware.encoder,
                    'hid': getattr(self.hardware, '_hid', None),
                    'ws_client': getattr(self.hardware, '_ws', None),
                })
            except Exception as e:
                print(f"[plugin_mgr] setup() failed: {e}")
                return False

        # Start plugin
        if hasattr(module, 'start'):
            try:
                module.start()
            except Exception as e:
                print(f"[plugin_mgr] start() failed: {e}")

        gc.collect()
        return True

    def deactivate(self):
        """Deactivate the current plugin (return to home screen)."""
        if self.active_module and hasattr(self.active_module, 'stop'):
            try:
                self.active_module.stop()
            except Exception as e:
                print(f"[plugin_mgr] stop() failed: {e}")

        self.active_id = None
        self.active_module = None

    def on_encoder(self, delta):
        """Route encoder event to active plugin."""
        if self.active_module and hasattr(self.active_module, 'on_encoder'):
            try:
                self.active_module.on_encoder(delta)
            except Exception as e:
                print(f"[plugin_mgr] on_encoder() failed: {e}")

    def on_button(self):
        """Route button event to active plugin."""
        if self.active_module and hasattr(self.active_module, 'on_button'):
            try:
                self.active_module.on_button()
            except Exception as e:
                print(f"[plugin_mgr] on_button() failed: {e}")

    def on_data_update(self, data):
        """Route data_update from PC to active plugin."""
        if self.active_module and hasattr(self.active_module, 'on_data_update'):
            try:
                self.active_module.on_data_update(data)
            except Exception as e:
                print(f"[plugin_mgr] on_data_update() failed: {e}")

    def is_active(self):
        """Return True if a plugin is currently active."""
        return self.active_module is not None
