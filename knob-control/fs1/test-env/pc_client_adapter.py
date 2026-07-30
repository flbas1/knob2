"""
PC Client Adapter — connects KnobClient to the bridge server as a WebSocket client.
Usage: python pc_client_adapter.py [--port 8765]
"""
import argparse
import hashlib
import base64
import json
import socket
import sys
import os
import select
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pc'))
from knob_client.main import KnobClient

WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def ws_connect(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))

    key = base64.b64encode(hashlib.sha1(os.urandom(16)).hexdigest()[:16].encode()).decode()
    handshake = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(handshake.encode())

    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Handshake failed")
        resp += chunk

    if b"101" not in resp:
        raise ConnectionError(f"Bad handshake: {resp.decode(errors='replace')[:200]}")

    return sock

def ws_send(sock, text):
    data = text.encode("utf-8")
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
    sock.sendall(bytes(frame))

def ws_recv(sock):
    header = sock.recv(2)
    if len(header) < 2:
        return None
    opcode = header[0] & 0x0F
    if opcode == 0x08:
        return None
    if opcode == 0x09:
        pong = bytearray([0x8A, 0x00])
        try:
            sock.sendall(bytes(pong))
        except:
            pass
        return ""
    if opcode != 0x01:
        return ""
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

def main():
    parser = argparse.ArgumentParser(description="PC Client Adapter")
    parser.add_argument("--host", default="localhost", help="Bridge host")
    parser.add_argument("--port", type=int, default=8765, help="Bridge WebSocket port")
    args = parser.parse_args()

    print(f"[pc] Connecting to bridge at {args.host}:{args.port}...")
    sock = ws_connect(args.host, args.port)
    print("[pc] Connected to bridge")
    ws_send(sock, json.dumps({"sender": "pc_client", "type": "ready"}))
    print("[pc] Sent identification")

    sock.setblocking(False)
    poll = select.poll()
    poll.register(sock, select.POLLIN)
    last_ping = time.monotonic()

    print("[pc] Waiting for messages...")
    running = True
    while running:
        now = time.monotonic()
        if now - last_ping > 1.0:
            ping_frame = bytearray([0x89, 0x00])
            try:
                sock.sendall(bytes(ping_frame))
            except:
                break
            last_ping = now

        events = poll.poll(500)
        if not events:
            continue

        try:
            msg = ws_recv(sock)
        except:
            msg = None

        if msg is None:
            print("[pc] Connection closed")
            break
        if msg == "":
            continue

        try:
            data = json.loads(msg)
        except json.JSONDecodeError as e:
            print(f"[pc] Parse error: {e}")
            continue

        print(f"[pc] << {json.dumps(data)}")

        if data.get("type") == "discover":
            import platform
            response = {
                "type": "identify",
                "device": platform.node(),
                "platform": platform.system().lower(),
                "version": "1.0.0"
            }
            ws_send(sock, json.dumps(response))
            print(f"[pc] >> identify: {response}")

        elif data.get("type") == "plugin_input":
            app = data.get("app", "")
            action = data.get("action", "")
            value = data.get("value", 0)
            print(f"[pc]   -> handler: {app} {action}={value}")
            response = {
                "type": "state_update",
                "app": app,
                "state": "applied"
            }
            ws_send(sock, json.dumps(response))
            print(f"[pc]   -> ack sent")

        elif data.get("type") == "data_request":
            app = data.get("app", "")
            print(f"[pc]   -> data request: {app}")
            if app == "brightness":
                response = {
                    "type": "data_update",
                    "app": "brightness",
                    "data": {"value": 75}
                }
                ws_send(sock, json.dumps(response))
                print(f"[pc]   -> brightness=75 sent")

        elif data.get("sender") == "browser":
            print(f"[pc]   -> browser message: {data.get('type', 'unknown')}")

    sock.close()
    print("[pc] Disconnected")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[pc] Stopped")
