"""
Smart Knob PC Client — Main Entry Point

WebSocket server that:
1. Listens for knob connections
2. Identifies the PC to the knob
3. Handles plugin input messages (volume, zoom, scroll, brightness)
4. Calls Home Assistant REST API for brightness control

Usage:
    python -m knob_client.main [--host 0.0.0.0] [--port 8765]

No external dependencies — uses Python stdlib only.
"""
import argparse
import json
import socket
import struct
import threading
import time
import platform
import subprocess
import os

# Protocol message types
MSG_DISCOVER = "discover"
MSG_IDENTIFY = "identify"
MSG_PLUGIN_INPUT = "plugin_input"
MSG_APP_SWITCH = "app_switch"
MSG_DATA_UPDATE = "data_update"
MSG_STATE_UPDATE = "state_update"
MSG_DATA_REQUEST = "data_request"


class KnobClient:
    """WebSocket server that bridges knob to system services."""

    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.knob_socket = None
        self.knob_addr = None
        self.running = False

        # Home Assistant config
        self.ha_url = os.environ.get("HA_URL", "http://homeassistant.local:8123")
        self.ha_token = os.environ.get("HA_TOKEN", "")

        # Platform-specific volume control
        self._volume_control = self._init_volume_control()

    def _init_volume_control(self):
        """Initialize platform-specific volume control."""
        system = platform.system()
        if system == "Darwin":
            return MacVolumeControl()
        elif system == "Linux":
            return LinuxVolumeControl()
        elif system == "Windows":
            return WindowsVolumeControl()
        else:
            print(f"[client] Warning: Unknown platform {system}")
            return None

    def start(self):
        """Start the WebSocket server."""
        self.running = True
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(1)
        server.settimeout(1.0)

        print(f"[client] Listening on {self.host}:{self.port}")
        print(f"[client] Platform: {platform.system()}")
        print(f"[client] Waiting for knob connection...")

        while self.running:
            try:
                client_sock, addr = server.accept()
                print(f"[client] Knob connected from {addr}")
                self._handle_knob(client_sock, addr)
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break

        self.running = False
        server.close()
        print("[client] Server stopped.")

    def _handle_knob(self, sock, addr):
        """Handle a connected knob."""
        self.knob_socket = sock
        self.knob_addr = addr

        try:
            while self.running:
                # Read WebSocket frame
                data = self._recv_ws_frame(sock)
                if not data:
                    break

                msg = json.loads(data)
                self._process_message(msg)

        except (ConnectionResetError, BrokenPipeError):
            print("[client] Knob disconnected.")
        finally:
            sock.close()
            self.knob_socket = None
            print("[client] Waiting for knob connection...")

    def _process_message(self, msg):
        """Process a message from the knob."""
        msg_type = msg.get("type", "")

        if msg_type == MSG_DISCOVER:
            print("[client] Knob discovered. Sending identify...")
            self._send_identify()

        elif msg_type == MSG_PLUGIN_INPUT:
            app = msg.get("app", "")
            action = msg.get("action", "")
            value = msg.get("value", 0)
            print(f"[client] Plugin input: {app} {action}={value}")
            self._handle_plugin_input(app, action, value)

        elif msg_type == MSG_APP_SWITCH:
            app = msg.get("app", "")
            print(f"[client] App switched to: {app}")

        elif msg_type == MSG_DATA_REQUEST:
            app = msg.get("app", "")
            print(f"[client] Data request for: {app}")
            self._handle_data_request(app)

    def _send_identify(self):
        """Send identify message to knob."""
        hostname = platform.node()
        system = platform.system().lower()
        msg = {
            "type": MSG_IDENTIFY,
            "device": hostname,
            "platform": system,
            "version": "1.0.0"
        }
        self._send_ws_text(json.dumps(msg))

    def _handle_plugin_input(self, app, action, value):
        """Route plugin input to appropriate system handler."""
        if app == "volume":
            if action == "mute":
                if self._volume_control:
                    self._volume_control.toggle_mute()
            elif action == "set":
                if self._volume_control:
                    self._volume_control.set_volume(value)

        elif app == "zoom":
            if action == "set":
                self._send_zoom(value)

        elif app == "scroll":
            if action == "scroll":
                self._send_scroll(value)

        elif app == "brightness":
            if action == "set":
                self._set_ha_brightness(value)

    def _handle_data_request(self, app):
        """Handle data request from knob (e.g., current brightness)."""
        if app == "brightness":
            brightness = self._get_ha_brightness()
            if brightness is not None:
                msg = {
                    "type": MSG_DATA_UPDATE,
                    "app": "brightness",
                    "data": {"value": brightness}
                }
                self._send_ws_text(json.dumps(msg))

    def _send_zoom(self, value):
        """Send zoom command (Ctrl+scroll)."""
        # Platform-specific zoom implementation
        system = platform.system()
        try:
            if system == "Darwin":
                # macOS: use AppleScript or cliclick
                pass
            elif system == "Linux":
                # Linux: use xdotool
                pass
            elif system == "Windows":
                # Windows: use pyautogui or SendInput
                pass
        except Exception as e:
            print(f"[client] Zoom failed: {e}")

    def _send_scroll(self, value):
        """Send scroll command."""
        system = platform.system()
        try:
            if system == "Darwin":
                # macOS: use cliclick
                direction = "scroll-up" if value > 0 else "scroll-down"
                for _ in range(abs(value)):
                    subprocess.run(["cliclick", direction], capture_output=True)
            elif system == "Linux":
                # Linux: use xdotool
                direction = "4" if value > 0 else "5"
                for _ in range(abs(value)):
                    subprocess.run(["xdotool", "click", direction], capture_output=True)
            elif system == "Windows":
                pass
        except Exception as e:
            print(f"[client] Scroll failed: {e}")

    def _set_ha_brightness(self, value):
        """Set brightness via Home Assistant REST API."""
        if not self.ha_token:
            print("[client] No HA token configured — skipping brightness")
            return

        try:
            import urllib.request
            url = f"{self.ha_url}/api/services/light/turn_on"
            data = json.dumps({
                "entity_id": "light.office_light",
                "brightness_pct": value
            }).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {self.ha_token}")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[client] HA brightness failed: {e}")

    def _get_ha_brightness(self):
        """Get current brightness from Home Assistant."""
        if not self.ha_token:
            return None

        try:
            import urllib.request
            url = f"{self.ha_url}/api/states/light.office_light"
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self.ha_token}")
            resp = urllib.request.urlopen(req, timeout=5)
            state = json.loads(resp.read())
            return state.get("attributes", {}).get("brightness", 0) * 100 // 255
        except Exception as e:
            print(f"[client] HA get brightness failed: {e}")
            return None

    def _send_ws_text(self, payload):
        """Send a WebSocket text frame."""
        if not self.knob_socket:
            return
        data = payload.encode("utf-8")
        frame = bytearray()
        frame.append(0x81)  # FIN + text opcode
        length = len(data)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.append((length >> 8) & 0xFF)
            frame.append(length & 0xFF)
        else:
            frame.append(127)
            for i in range(7, -1, -1):
                frame.append((length >> (8 * i)) & 0xFF)
        frame.extend(data)
        self.knob_socket.sendall(bytes(frame))

    def _recv_ws_frame(self, sock):
        """Receive a WebSocket text frame (simplified, no fragmentation)."""
        try:
            header = sock.recv(2)
            if len(header) < 2:
                return None

            opcode = header[0] & 0x0F
            if opcode != 0x01:  # Not text
                return None

            length = header[1] & 0x7F
            if length == 126:
                ext = sock.recv(2)
                length = (ext[0] << 8) | ext[1]
            elif length == 127:
                ext = sock.recv(8)
                length = 0
                for b in ext:
                    length = (length << 8) | b

            payload = b""
            while len(payload) < length:
                chunk = sock.recv(length - len(payload))
                if not chunk:
                    return None
                payload += chunk

            return payload.decode("utf-8")
        except:
            return None


class MacVolumeControl:
    """macOS volume control via osascript."""

    def set_volume(self, level):
        level = max(0, min(100, level))
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            capture_output=True
        )

    def get_volume(self):
        result = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True
        )
        return int(result.stdout.strip()) if result.stdout.strip() else 0

    def toggle_mute(self):
        subprocess.run(
            ["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"],
            capture_output=True
        )


class LinuxVolumeControl:
    """Linux volume control via amixer (ALSA)."""

    def set_volume(self, level):
        level = max(0, min(100, level))
        subprocess.run(
            ["amixer", "set", "Master", f"{level}%"],
            capture_output=True
        )

    def get_volume(self):
        result = subprocess.run(
            ["amixer", "get", "Master"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "[" in line and "%" in line:
                pct = line.split("[")[1].split("%")[0]
                return int(pct)
        return 0

    def toggle_mute(self):
        subprocess.run(
            ["amixer", "set", "Master", "toggle"],
            capture_output=True
        )


class WindowsVolumeControl:
    """Windows volume control (placeholder — needs pycaw or nircmd)."""

    def set_volume(self, level):
        level = max(0, min(100, level))
        # Option 1: nircmd (must be installed)
        try:
            subprocess.run(
                ["nircmd", "setsysvolume", str(level * 655)],
                capture_output=True
            )
            return
        except FileNotFoundError:
            pass
        # Option 2: PowerShell (Windows 10+)
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f"$w = New-Object -ComObject WScript.Shell; "
                 f"1..50 | ForEach-Object {{$w.SendKeys([char]174)}}; "
                 f"1..{level // 2} | ForEach-Object {{$w.SendKeys([char]175)}}"],
                capture_output=True, timeout=5
            )
        except Exception as e:
            print(f"[client] Windows volume failed: {e}")

    def get_volume(self):
        return 50  # Placeholder

    def toggle_mute(self):
        try:
            subprocess.run(
                ["nircmd", "mutesysvolume"],
                capture_output=True
            )
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Smart Knob PC Client")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    args = parser.parse_args()

    client = KnobClient(host=args.host, port=args.port)
    try:
        client.start()
    except KeyboardInterrupt:
        print("\n[client] Shutting down...")


if __name__ == "__main__":
    main()
