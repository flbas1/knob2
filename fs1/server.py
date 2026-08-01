"""
Smart Knob PC Server — the real server.

Orchestrates bootstrap → config → launcher protocol.
Routes app commands (volume, brightness, zoom, scroll) to system actions.
"""
import argparse, fnmatch, json, os, socket, sys, threading, hashlib, base64, time

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SERVER_VERSION = "0.1.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MACHINES_DIR = os.path.join(SCRIPT_DIR, 'machines')
BOOTSTRAP_PATH = os.path.join(SCRIPT_DIR, 'bootstrap.py')
LAUNCHER_PATH = os.path.join(SCRIPT_DIR, 'launcher.py')


def _py_literal(obj):
    """Serialize a JSON-ish object as a valid Python literal (True/False/None)."""
    if isinstance(obj, bool):
        return 'True' if obj else 'False'
    if obj is None:
        return 'None'
    if isinstance(obj, str):
        return json.dumps(obj)
    if isinstance(obj, dict):
        return '{' + ', '.join(_py_literal(k) + ': ' + _py_literal(v)
                               for k, v in obj.items()) + '}'
    if isinstance(obj, (list, tuple)):
        return '[' + ', '.join(_py_literal(x) for x in obj) + ']'
    return repr(obj)

sys.path.insert(0, os.path.join(SCRIPT_DIR, 'pc'))
from knob_client.main import KnobClient


class KnobServer:
    """PC-side server: bootstrap → config → launcher → route commands."""

    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.knob_socket = None
        self.knob_addr = None
        self.knob_lock = threading.Lock()
        self.client = KnobClient(host=host, port=port)

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)
        print(f"[server] Listening on {self.host}:{self.port}")

        while self.running:
            try:
                sock, addr = self.server_socket.accept()
                print(f"[server] Knob connected from {addr}")
                threading.Thread(target=self._handle_knob, args=(sock, addr), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break
        self.running = False
        print("[server] Stopped.")

    def _handle_knob(self, sock, addr):
        """Handle a knob connection through the full bootstrap flow."""
        success, extra = self._ws_handshake(sock)
        if not success:
            sock.close()
            return

        buf = bytearray(extra)
        self.knob_socket = sock
        self.knob_addr = addr

        try:
            buf = self._run_bootstrap(sock, buf)
            if buf is None:
                return
            print(f"[server] Bootstrap complete — entering command loop")
            self.client.knob_socket = sock
            while self.running:
                msg, buf = self._recv_ws_frame(sock, buf)
                if msg is None:
                    break
                self._route_message(msg)
        except Exception as e:
            print(f"[server] Error: {e}")
        finally:
            with self.knob_lock:
                self.knob_socket = None
                self.knob_addr = None
                self.client.knob_socket = None
            sock.close()
            print(f"[server] Knob disconnected: {addr}")

    # ── Bootstrap ───────────────────────────────────────────────────

    def _run_bootstrap(self, sock, buf):
        """3-step bootstrap: send code → receive GUID → send config → ack → send launcher."""
        try:
            with open(BOOTSTRAP_PATH) as f:
                boot_code = f.read()
        except OSError:
            print("[server] bootstrap.py not found"); return None

        machines = self._load_machine_list()
        if machines:
            preamble = (
                f"_SERVER_VERSION = \"{SERVER_VERSION}\"\n"
                "_AVAILABLE_MACHINES = " + json.dumps(machines) + "\n"
            )
            boot_code = preamble + boot_code
            print(f"[server] Injected {len(machines)} machines (v{SERVER_VERSION}) into bootstrap")

        print("[server] Sending bootstrap.py...")
        self._send_ws_text(sock, json.dumps({
            "type": "execute",
            "file": "bootstrap.py",
            "code": boot_code,
            "machines": machines
        }))

        guid = None
        while True:
            frame, buf = self._recv_ws_frame(sock, buf)
            if frame is None: return None
            try:
                d = json.loads(frame)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "bootstrap_response":
                info = d.get("data", {})
                guid = info.get("machine_guid", "")
                print(f"[server] Knob: machine={info.get('machine')} guid={guid} "
                      f"version={info.get('server_version')} location={info.get('location')}")
                break

        config = self._match_machine(guid)
        if config is None:
            config = {"name": "Knob", "apps": []}

        print(f"[server] Config: {config.get('name')} — sending...")
        self._send_ws_text(sock, json.dumps({"type": "config", "config": config}))

        while True:
            frame, buf = self._recv_ws_frame(sock, buf)
            if frame is None: return None
            try:
                d = json.loads(frame)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "config_ack":
                print(f"[server] Config accepted: {d.get('status')}")
                break

        try:
            with open(LAUNCHER_PATH) as f:
                launch_code = f.read()
        except OSError:
            print("[server] launcher.py not found"); return None

        apps = self._build_app_list(config)
        if apps:
            launch_code = "_SERVER_APPS = " + _py_literal(apps) + "\n" + launch_code
            print(f"[server] Injected {len(apps)} apps into launcher")

        print("[server] Sending launcher.py...")
        self._send_ws_text(sock, json.dumps({"type": "execute", "file": "launcher.py", "code": launch_code}))
        return buf

    def _build_app_list(self, machine):
        """Merge a machine's app list with the plugin manifests + code on disk."""
        manifests = self._load_plugin_manifests()
        apps = []
        for app in machine.get('apps') or []:
            pid = app.get('id')
            if not pid:
                continue
            man = manifests.get(pid, {})
            entry = {k: v for k, v in man.items()}
            entry['id'] = pid
            entry['name'] = app.get('name') or man.get('name') or pid
            entry['icon'] = app.get('icon') or man.get('icon')
            entry['icon_data'] = man.get('icon_data')
            entry['code'] = self._read_plugin_code(pid)
            apps.append(entry)
        return apps

    def _read_plugin_code(self, pid):
        """Read a plugin's source so the knob can run it without local files."""
        path = os.path.join(SCRIPT_DIR, 'plugins', pid, 'plugin.py')
        if not os.path.isfile(path):
            return None
        try:
            with open(path) as f:
                return f.read()
        except OSError:
            return None

    def _load_plugin_manifests(self):
        """Scan fs1/plugins/*/manifest.json for plugin metadata."""
        manifests = {}
        plugins_dir = os.path.join(SCRIPT_DIR, 'plugins')
        if not os.path.isdir(plugins_dir):
            return manifests
        for name in os.listdir(plugins_dir):
            mpath = os.path.join(plugins_dir, name, 'manifest.json')
            if not os.path.isfile(mpath):
                continue
            try:
                with open(mpath) as f:
                    m = json.load(f)
                manifests[m.get('id', name)] = m
            except Exception as e:
                print(f"[server] Bad manifest {mpath}: {e}")
        return manifests

    def _match_machine(self, guid):
        if not os.path.isdir(MACHINES_DIR):
            return None
        for fname in os.listdir(MACHINES_DIR):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(MACHINES_DIR, fname)) as f:
                try:
                    cfg = json.load(f)
                except json.JSONDecodeError:
                    continue
            if fnmatch.fnmatch(guid, cfg.get("machine_guid", "")):
                print(f"[server] Matched {guid} → {fname}")
                return cfg
        return None

    def _load_machine_list(self):
        entries = []
        if os.path.isdir(MACHINES_DIR):
            for fname in sorted(os.listdir(MACHINES_DIR)):
                if not fname.endswith('.json'):
                    continue
                with open(os.path.join(MACHINES_DIR, fname)) as f:
                    try:
                        cfg = json.load(f)
                    except json.JSONDecodeError:
                        continue
                entries.append({
                    "guid": cfg.get("machine_guid", ""),
                    "name": cfg.get("name", ""),
                    "location": cfg.get("location", "")
                })
        return entries

    # ── Command routing ─────────────────────────────────────────────

    def _route_message(self, msg_str):
        try:
            msg = json.loads(msg_str)
        except json.JSONDecodeError:
            return
        t = msg.get("type")

        if t == "action":
            app = msg.get("app", "")
            cmd = msg.get("cmd", "")
            val = msg.get("value")
            print(f"[server] Action: {app} {cmd}={val}")
            self.client._handle_plugin_input(app, cmd, val)

        elif t == "app_selected":
            app = msg.get("app", "")
            print(f"[server] App selected: {app}")
            # Future: send app MicroPython code to knob

        elif t == "launcher_ready":
            apps = msg.get("apps", [])
            print(f"[server] Launcher ready: {apps}")

        elif t == "data_request":
            app = msg.get("app", "")
            self.client._handle_data_request(app)

        elif t == "app_loaded":
            print(f"[server] App running: {msg.get('name') or msg.get('app')}")

        elif t == "app_closed":
            print(f"[server] App stopped: {msg.get('app')}")

        else:
            print(f"[server] Unknown message: {t}")

    # ── WebSocket ───────────────────────────────────────────────────

    def _ws_handshake(self, sock):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                c = sock.recv(1024)
                if not c: return False, None
                req += c
            sep = req.index(b"\r\n\r\n") + 4
            extra = req[sep:]
            for line in req.split(b"\r\n"):
                if b"Sec-WebSocket-Key:" in line:
                    key = line.split(b":")[1].strip()
                    break
            else:
                return False, None
            accept = base64.b64encode(hashlib.sha1(key + WS_MAGIC.encode()).digest()).decode()
            sock.sendall((
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
            ).encode())
            return True, extra
        except Exception:
            return False, None

    def _send_ws_text(self, sock, payload):
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        frame = bytearray([0x81])
        length = len(data)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.extend([126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            frame.append(127)
            for i in range(7, -1, -1):
                frame.append((length >> (8 * i)) & 0xFF)
        frame.extend(data)
        try:
            sock.sendall(bytes(frame))
        except Exception:
            pass

    def _recv_ws_frame(self, sock, buf=None):
        try:
            if buf is None:
                buf = bytearray()
            while True:
                while len(buf) < 2:
                    c = sock.recv(8)
                    if not c: return None, buf
                    buf.extend(c)
                hdr = buf[:2]
                del buf[:2]
                op = hdr[0] & 0x0F
                if op == 0x08: return None, buf
                masked = hdr[1] & 0x80
                raw = hdr[1] & 0x7F
                if raw < 126:
                    plen = raw
                else:
                    elen = 2 if raw == 126 else 8
                    while len(buf) < elen:
                        c = sock.recv(elen - len(buf))
                        if not c: return None, buf
                        buf.extend(c)
                    if raw == 126:
                        plen = (buf[0] << 8) | buf[1]
                    else:
                        plen = 0
                        for b in buf[:8]:
                            plen = (plen << 8) | b
                    del buf[:elen]
                need = plen + (4 if masked else 0)
                while len(buf) < need:
                    c = sock.recv(need - len(buf))
                    if not c: return None, buf
                    buf.extend(c)
                if masked:
                    mk = bytes(buf[:4])
                    del buf[:4]
                    pl = bytes(buf[:plen])
                    del buf[:plen]
                    pl = bytes(b ^ mk[i % 4] for i, b in enumerate(pl))
                else:
                    pl = bytes(buf[:plen])
                    del buf[:plen]

                if op == 0x09:
                    pong = bytearray([0x8A])
                    if len(pl) < 126:
                        pong.append(len(pl))
                    elif len(pl) < 65536:
                        pong.extend([126, (len(pl) >> 8) & 0xFF, len(pl) & 0xFF])
                    else:
                        pong.append(127)
                        for i in range(7, -1, -1):
                            pong.append((len(pl) >> (8 * i)) & 0xFF)
                    pong.extend(pl)
                    try: sock.sendall(bytes(pong))
                    except: pass
                    continue

                if op != 0x01: continue
                return pl.decode("utf-8"), buf
        except Exception:
            return None, buf if buf is not None else bytearray()


def main():
    parser = argparse.ArgumentParser(description="Smart Knob PC Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = KnobServer(host=args.host, port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")

if __name__ == "__main__":
    main()
