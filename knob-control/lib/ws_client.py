"""
WebSocket client for Smart Knob Controller.

Connects to PC client over WiFi (or USB CDC-Ether).
Handles the discover/identify handshake and message routing.

Designed for MicroPython on ESP32-S3.
"""
import json
from time import sleep_ms, ticks_ms, ticks_diff

MSG_DISCOVER = "discover"
MSG_IDENTIFY = "identify"
MSG_DATA_UPDATE = "data_update"
MSG_PLUGIN_INPUT = "plugin_input"
MSG_APP_SWITCH = "app_switch"
MSG_STATE_UPDATE = "state_update"
MSG_DATA_REQUEST = "data_request"

STATE_DISCONNECTED = 0
STATE_CONNECTING = 1
STATE_CONNECTED = 2

CONNECT_TIMEOUT_MS = 5000


class WSClient:
    def __init__(self, uri="ws://10.10.10.2:8765"):
        self.uri = uri
        self._socket = None
        self._state = STATE_DISCONNECTED
        self._message_cb = None
        self._machine_info = None
        self._recv_buf = bytearray()

    def set_message_callback(self, cb):
        self._message_cb = cb

    def connect(self):
        try:
            import usocket
            host, port = self._parse_uri()

            self._socket = usocket.socket()
            self._socket.setblocking(False)

            try:
                self._socket.connect((host, port))
            except OSError as e:
                if e.args[0] == 119:
                    self._state = STATE_CONNECTING
                    self._connect_start = ticks_ms()
                    return True
                raise

            self._state = STATE_CONNECTED
            self._do_handshake()
            return True
        except Exception as e:
            print(f"[ws] Connect failed: {e}")
            self._state = STATE_DISCONNECTED
            self._socket = None
            return False

    def _parse_uri(self):
        uri = self.uri
        if uri.startswith("ws://"):
            uri = uri[5:]
        elif uri.startswith("wss://"):
            uri = uri[6:]

        if "/" in uri:
            uri = uri.split("/")[0]

        if ":" in uri:
            host, port_str = uri.rsplit(":", 1)
            port = int(port_str)
        else:
            host = uri
            port = 8765

        return host, port

    def _do_handshake(self):
        import ubinascii
        import uos

        key = ubinascii.b64encode(uos.urandom(16)).decode()
        req = (
            "GET / HTTP/1.1\r\n"
            "Host: knob\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self._socket.send(req.encode())
        sleep_ms(100)

        try:
            resp = self._socket.recv(1024)
            if resp and b"101" in resp:
                self._state = STATE_CONNECTED
                self._send_discover()
                return True
        except OSError:
            pass

        self._state = STATE_DISCONNECTED
        return False

    def disconnect(self):
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
        self._socket = None
        self._state = STATE_DISCONNECTED

    def is_connected(self):
        return self._state == STATE_CONNECTED

    def get_machine_info(self):
        return self._machine_info

    def send_text(self, data):
        if self._state != STATE_CONNECTED or not self._socket:
            return False
        try:
            msg = json.dumps(data)
            self._socket.send(self._encode_ws_frame(msg))
            return True
        except Exception as e:
            print(f"[ws] Send failed: {e}")
            self._state = STATE_DISCONNECTED
            return False

    def send_plugin_input(self, app_name, action, value):
        return self.send_text({
            "type": MSG_PLUGIN_INPUT,
            "app": app_name,
            "action": action,
            "value": value
        })

    def send_app_switch(self, app_name):
        return self.send_text({
            "type": MSG_APP_SWITCH,
            "app": app_name
        })

    def send_data_request(self, app_name):
        return self.send_text({
            "type": MSG_DATA_REQUEST,
            "app": app_name
        })

    def poll(self):
        if self._state == STATE_CONNECTING:
            self._poll_connect()
            return

        if self._state != STATE_CONNECTED or not self._socket:
            return

        try:
            chunk = self._socket.recv(2048)
            if chunk:
                self._recv_buf.extend(chunk)
                self._process_recv_buf()
        except OSError:
            pass

    def _poll_connect(self):
        if ticks_diff(ticks_ms(), self._connect_start) > CONNECT_TIMEOUT_MS:
            print("[ws] Connect timeout")
            self.disconnect()
            return

        try:
            self._socket.recv(0)
            self._state = STATE_CONNECTED
            self._do_handshake()
        except OSError as e:
            if e.args[0] == 119:
                pass
            elif e.args[0] == 106:
                pass
            else:
                self._state = STATE_CONNECTED
                self._do_handshake()

    def _process_recv_buf(self):
        while len(self._recv_buf) >= 2:
            opcode = self._recv_buf[0] & 0x0F

            if opcode == 0x08:
                self.disconnect()
                return

            if opcode == 0x09:
                self._handle_ping()
                continue

            if opcode != 0x01:
                self._recv_buf = self._recv_buf[2:]
                continue

            second_byte = self._recv_buf[1]
            masked = bool(second_byte & 0x80)
            payload_len = second_byte & 0x7F
            header_size = 2

            if payload_len == 126:
                if len(self._recv_buf) < 4:
                    return
                payload_len = (self._recv_buf[2] << 8) | self._recv_buf[3]
                header_size = 4
            elif payload_len == 127:
                if len(self._recv_buf) < 10:
                    return
                payload_len = 0
                for i in range(8):
                    payload_len = (payload_len << 8) | self._recv_buf[2 + i]
                header_size = 10

            mask_offset = header_size
            if masked:
                header_size += 4

            total = header_size + payload_len
            if len(self._recv_buf) < total:
                return

            payload = self._recv_buf[header_size:header_size + payload_len]
            self._recv_buf = self._recv_buf[total:]

            if masked:
                mask = self._recv_buf[mask_offset:mask_offset + 4]
                for i in range(payload_len):
                    payload[i] ^= mask[i % 4]

            try:
                text = payload.decode("utf-8")
                msg = json.loads(text)
                self._dispatch(msg)
            except:
                pass

    def _handle_ping(self):
        if len(self._recv_buf) >= 2:
            self._recv_buf = self._recv_buf[2:]

    def _dispatch(self, msg):
        msg_type = msg.get("type", "")

        if msg_type == MSG_IDENTIFY:
            self._machine_info = msg
            print(f"[ws] PC identified: {msg.get('device', 'unknown')}")

        if self._message_cb:
            self._message_cb(msg)

    def _send_discover(self):
        self.send_text({"type": MSG_DISCOVER})

    def _encode_ws_frame(self, payload):
        data = payload.encode("utf-8")
        frame = bytearray()
        frame.append(0x81)
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
        return bytes(frame)
