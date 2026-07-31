"""
testKnob.py — transparent bridge between browser sim and the real PC server.

Serves the test website (HTTP :8080) and forwards all WS messages
bidirectionally to server.py (:8765). Zero logic — pure pipe.
"""
import argparse, http.server, json, socket, socketserver, threading
import os, hashlib, base64

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

SERVER_HOST = "localhost"
SERVER_PORT = 8765


class Bridge:
    """Transparent WS bridge: browser ↔ server.py."""

    def __init__(self, port=8766):
        self.port = port
        self.server_socket = None
        self.running = False

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(5)
        self.server_socket.settimeout(1.0)
        print(f"[bridge] Listening for browsers on :{self.port}")

        while self.running:
            try:
                bsock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_browser, args=(bsock,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_browser(self, bsock):
        success, extra = self._ws_handshake(bsock)
        if not success:
            bsock.close()
            return
        buf = bytearray(extra)
        print(f"[bridge] Browser connected")

        ssock = self._connect_to_server()
        if ssock is None:
            print("[bridge] Server not available — closing")
            bsock.close()
            return

        # Forward browser's first queued message (the identity)
        first, buf = self._recv_ws_frame(bsock, buf)
        if first:
            self._send_ws_text(ssock, first)

        # Bidirectional bridge
        stop = threading.Event()

        def pipe(src, dst, name):
            b = bytearray()
            while not stop.is_set():
                msg, b = self._recv_ws_frame(src, b)
                if msg is None:
                    break
                self._send_ws_text(dst, msg)
            stop.set()

        t1 = threading.Thread(target=pipe, args=(bsock, ssock, "B→S"), daemon=True)
        t2 = threading.Thread(target=pipe, args=(ssock, bsock, "S→B"), daemon=True)
        t1.start()
        t2.start()
        stop.wait()
        bsock.close()
        ssock.close()
        print("[bridge] Browser disconnected")

    def _connect_to_server(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((SERVER_HOST, SERVER_PORT))
            req = self._ws_handshake_client(s)
            s.sendall(req.encode())
            resp = b""
            while b"\r\n\r\n" not in resp:
                c = s.recv(4096)
                if not c: raise ConnectionError()
                resp += c
            assert b"101" in resp
            print(f"[bridge] Connected to server at {SERVER_HOST}:{SERVER_PORT}")
            return s
        except Exception as e:
            print(f"[bridge] Server connect failed: {e}")
            return None

    def _ws_handshake_client(self, sock):
        key = base64.b64encode(hashlib.sha1(os.urandom(16)).hexdigest()[:16].encode()).decode()
        return (
            f"GET / HTTP/1.1\r\nHost: {SERVER_HOST}:{SERVER_PORT}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )

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
            if buf is None: buf = bytearray()
            while True:
                while len(buf) < 2:
                    c = sock.recv(8)
                    if not c: return None, buf
                    buf.extend(c)
                hdr = buf[:2]; del buf[:2]
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
                        for b in buf[:8]: plen = (plen << 8) | b
                    del buf[:elen]
                need = plen + (4 if masked else 0)
                while len(buf) < need:
                    c = sock.recv(need - len(buf))
                    if not c: return None, buf
                    buf.extend(c)
                if masked:
                    mk = bytes(buf[:4]); del buf[:4]
                    pl = bytes(b ^ mk[i % 4] for i, b in enumerate(bytes(buf[:plen]))); del buf[:plen]
                else:
                    pl = bytes(buf[:plen]); del buf[:plen]

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


class HTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()
    def log_message(self, fmt, *args):
        print(f"[http] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="testKnob — browser simulator bridge")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--ws-port", type=int, default=8766)
    parser.add_argument("--server-host", default="localhost")
    parser.add_argument("--server-port", type=int, default=8765)
    args = parser.parse_args()

    global SERVER_HOST, SERVER_PORT
    SERVER_HOST = args.server_host
    SERVER_PORT = args.server_port

    bridge = Bridge(port=args.ws_port)
    threading.Thread(target=bridge.start, daemon=True).start()

    print(f"[testKnob] Serving test website at http://localhost:{args.http_port}")
    print(f"[testKnob] Bridging to server at {SERVER_HOST}:{SERVER_PORT}")
    with socketserver.TCPServer(("0.0.0.0", args.http_port), HTTPHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    bridge.running = False

if __name__ == "__main__":
    main()
