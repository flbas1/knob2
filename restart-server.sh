#!/usr/bin/env bash
# Restart the PC server (fs1/server.py) with a fresh, cleared log.
set -e
PORT=8765
LOG=/workspaces/knob-controller/server.log

PID=$(ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1)
if [ -n "$PID" ]; then
    echo "Stopping server (pid $PID)..."
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$PID" 2>/dev/null || break
        sleep 0.5
    done
fi

echo "Starting server... (log: $LOG, cleared on start)"
cd /workspaces/knob-controller/fs1
setsid nohup python3 -u /workspaces/knob-controller/fs1/server.py > "$LOG" 2>&1 < /dev/null &
sleep 1
ss -ltn | grep ":$PORT "
echo "Server restarted."
