#!/usr/bin/env python3
import glob
import os
import subprocess
import sys
import time

connect_cmd = sys.argv[1] if len(sys.argv) > 1 else "repl"
log = sys.argv[2] if len(sys.argv) > 2 else None

def knob_ports():
    return [p for p in sorted(glob.glob("/dev/cu.*"))
            if "usbmodem" in p or "usbserial" in p]

print("Waiting for the knob port to disappear, then reappear.", flush=True)
print("Then I'll run: mpremote connect <port>", connect_cmd, flush=True)
print("(override the command with the first argument, e.g. python3 watch-cu.py 'reset')", flush=True)

saw_port = bool(knob_ports())
saw_gone = False

while True:
    cur = knob_ports()
    if cur and not saw_port:
        saw_port = True
        print(f"[{time.strftime('%H:%M:%S')}] port appeared: {', '.join(cur)}", flush=True)
    if not cur and saw_port and not saw_gone:
        saw_gone = True
        print(f"[{time.strftime('%H:%M:%S')}] port disappeared — replug or wait for re-enumeration...", flush=True)
    if cur and saw_gone:
        port = cur[0]
        print(f"[{time.strftime('%H:%M:%S')}] port back: {port} — connecting", flush=True)
        cmd = [sys.executable, "-m", "mpremote", "connect", port] + connect_cmd.split()
        print(">>", " ".join(cmd), flush=True)
        subprocess.call(cmd)
        sys.exit(0)
    if log and os.path.exists(log):
        print(f"--- tail {log} ---")
        with open(log) as f:
            print("".join(f.readlines()[-15:]), end="")
    time.sleep(1)
