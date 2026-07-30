"""
Smart Knob Test Environment — WebSocket Bridge Server

Python stdlib-only WebSocket bridge that:
1. Serves the LVGL MicroPython simulator (index.html) on HTTP port 8080
2. Bridges WebSocket messages between browser simulator and PC client on WS port 8765
3. Provides virtual encoder/touch input from the browser to the simulator

No pip dependencies — uses only Python stdlib.

Usage:
    python server.py [--http-port 8080] [--ws-port 8765]
"""
import argparse
import http.server
import json
import socket
import socketserver
import threading

import os
import hashlib
import base64
import struct

# WebSocket magic string for handshake
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketBridge:
    """Bridges browser WebSocket to PC client WebSocket."""

    def __init__(self, ws_port=8765):
        self.ws_port = ws_port
        self.browser_socket = None
        self.pc_socket = None
        self.browser_lock = threading.Lock()
        self.pc_lock = threading.Lock()
        self.running = False
        self.server_socket = None

    def start(self):
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.ws_port))
        self.server_socket.listen(2)
        self.server_socket.settimeout(1.0)

        print(f"[ws] WebSocket bridge listening on port {self.ws_port}")

        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                # Determine if this is browser or PC client
                # (first message identifies the sender)
                threading.Thread(
                    target=self._handle_connection,
                    args=(client_sock, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_connection(self, sock, addr):
        """Handle a new WebSocket connection (browser or PC)."""
        success, extra_data = self._ws_handshake(sock)
        if not success:
            sock.close()
            return

        print(f"[ws] WebSocket client connected: {addr}")

        # Wait for first message to identify sender
        buf = bytearray(extra_data)
        first_msg, buf = self._recv_ws_frame(sock, buf)
        if not first_msg:
            sock.close()
            return

        try:
            data = json.loads(first_msg)
            sender_type = data.get("sender", "browser")
        except:
            sender_type = "browser"

        if sender_type == "pc_client":
            with self.pc_lock:
                self.pc_socket = sock
            print(f"[ws] PC client registered: {addr}")
        else:
            with self.browser_lock:
                self.browser_socket = sock
            print(f"[ws] Browser simulator registered: {addr}")

        # Forward the identification message too
        if sender_type == "pc_client":
            self._forward_to_browser(first_msg)
        else:
            self._forward_to_pc(first_msg)

        # Bridge all subsequent messages
        try:
            while self.running:
                msg, buf = self._recv_ws_frame(sock, buf)
                if msg is None:
                    break

                if sender_type == "pc_client":
                    self._forward_to_browser(msg)
                else:
                    self._forward_to_pc(msg)
        except Exception as e:
            print(f"[ws] Connection error: {e}")
        finally:
            sock.close()
            if sender_type == "pc_client":
                with self.pc_lock:
                    self.pc_socket = None
            else:
                with self.browser_lock:
                    self.browser_socket = None
            print(f"[ws] Client disconnected: {addr}")

    def _forward_to_browser(self, msg):
        with self.browser_lock:
            if self.browser_socket:
                self._send_ws_text(self.browser_socket, msg)

    def _forward_to_pc(self, msg):
        with self.pc_lock:
            if self.pc_socket:
                self._send_ws_text(self.pc_socket, msg)

    def _ws_handshake(self, sock):
        """Perform WebSocket handshake.
        Returns (True, extra_data) on success, (False, None) on failure.
        extra_data is any bytes after the HTTP headers that belong to the first WS frame.
        """
        try:
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = sock.recv(1024)
                if not chunk:
                    print(f"[ws] handshake: recv returned empty", flush=True)
                    return False, None
                request += chunk

            # Split headers from any trailing WS frame data
            header_end = request.index(b"\r\n\r\n") + 4
            extra_data = request[header_end:]
            print(f"[ws] handshake: read {len(request)} bytes, extra={len(extra_data)}", flush=True)

            # Extract Sec-WebSocket-Key
            for line in request.split(b"\r\n"):
                if b"Sec-WebSocket-Key:" in line:
                    key = line.split(b":")[1].strip()
                    break
            else:
                print(f"[ws] handshake: no Sec-WebSocket-Key found", flush=True)
                return False, None

            # Compute accept hash
            accept = base64.b64encode(
                hashlib.sha1(key + WS_MAGIC.encode()).digest()
            ).decode()
            print(f"[ws] handshake: key={key!r} accept={accept}", flush=True)

            # Send handshake response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            sock.sendall(response.encode())
            print(f"[ws] handshake: 101 sent, extra={len(extra_data)} bytes", flush=True)
            return True, extra_data
        except Exception as e:
            print(f"[ws] Handshake failed: {e}", flush=True)
            return False, None

    def _send_ws_text(self, sock, payload):
        """Send a WebSocket text frame."""
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
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
        try:
            sock.sendall(bytes(frame))
        except:
            pass

    def _recv_ws_frame(self, sock, buf=None):
        """Receive a WebSocket text frame.
        buf: optional bytearray buffer with data already read from the socket.
        Returns (decoded_text, buf) on success, (None, buf) on failure/close.
        buf is returned with consumed bytes removed so it can be reused.
        """
        try:
            if buf is None:
                buf = bytearray()

            # Read at least 2 bytes for the frame header
            while len(buf) < 2:
                chunk = sock.recv(8)
                if not chunk:
                    return None, buf
                buf.extend(chunk)

            header = buf[:2]
            del buf[:2]

            opcode = header[0] & 0x0F
            if opcode == 0x08:
                return None, buf
            if opcode == 0x09:
                self._handle_pong(sock, header)
                return self._recv_ws_frame(sock, buf)
            if opcode != 0x01:
                return None, buf

            masked = header[1] & 0x80
            raw_length = header[1] & 0x7F

            # Read extended length + mask key + payload, accumulating in buf
            total_needed = 0
            if raw_length == 126:
                total_needed = 2
            elif raw_length == 127:
                total_needed = 8

            if masked:
                total_needed += 4

            # Determine full payload length
            if raw_length < 126:
                payload_length = raw_length
            else:
                ext_len = 2 if raw_length == 126 else 8
                while len(buf) < ext_len:
                    chunk = sock.recv(ext_len - len(buf))
                    if not chunk:
                        return None, buf
                    buf.extend(chunk)
                if raw_length == 126:
                    payload_length = (buf[0] << 8) | buf[1]
                else:
                    payload_length = 0
                    for b in buf[:8]:
                        payload_length = (payload_length << 8) | b
                del buf[:ext_len]

            total_needed = payload_length + (4 if masked else 0)

            while len(buf) < total_needed:
                chunk = sock.recv(total_needed - len(buf))
                if not chunk:
                    return None, buf
                buf.extend(chunk)

            if masked:
                mask_key = bytes(buf[:4])
                del buf[:4]
                payload = bytes(buf[:payload_length])
                del buf[:payload_length]
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
            else:
                payload = bytes(buf[:payload_length])
                del buf[:payload_length]

            return payload.decode("utf-8"), buf
        except Exception:
            return None, buf if buf is not None else bytearray()

    def _handle_pong(self, sock, header):
        """Respond to ping with pong."""
        length = header[1] & 0x7F
        masked = header[1] & 0x80
        if length > 0:
            read_len = length + (4 if masked else 0)
            try:
                data = sock.recv(read_len)
            except:
                pass
        pong = bytearray([0x8A, 0x00])
        try:
            sock.sendall(bytes(pong))
        except:
            pass


socketserver.TCPServer.allow_reuse_address = True


class HTTPHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves from the test-env directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"[http] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Smart Knob Test Environment Server")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP server port")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket bridge port")
    args = parser.parse_args()

    # Start WebSocket bridge in background thread
    bridge = WebSocketBridge(ws_port=args.ws_port)
    ws_thread = threading.Thread(target=bridge.start, daemon=True)
    ws_thread.start()

    # Start HTTP server on main thread
    print(f"[http] Serving simulator at http://localhost:{args.http_port}")
    print(f"[http] Press Ctrl+C to stop")

    with socketserver.TCPServer(("0.0.0.0", args.http_port), HTTPHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

    bridge.running = False
    print("[server] Stopped.")


if __name__ == "__main__":
    main()
