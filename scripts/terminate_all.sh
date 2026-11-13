#!/bin/bash
# scripts/terminate_all.sh — Force-terminate all registered apps,
# including external processes occupying their ports, whether started by Homeport or not.
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_URL="http://127.0.0.1:7777"

echo "⚡ Terminating all registered apps..."

# 1. Ask the Homeport API to terminate everything if it is running
if curl -s --connect-timeout 1 "$SERVER_URL/api/health" >/dev/null 2>&1; then
    curl -s -X POST "$SERVER_URL/api/apps/terminate-all" >/dev/null 2>&1 || true
fi

# 2. Directly scan ports from data/apps.json and kill any remaining processes
if [ -f "$DIR/data/apps.json" ]; then
    PORTS=$(/usr/bin/python3 -c "
import json
try:
    with open('$DIR/data/apps.json') as f:
        apps = json.load(f)
    ports = [str(a['port']) for a in apps if a.get('port')]
    print(' '.join(ports))
except Exception:
    pass
" 2>/dev/null || true)

    for PORT in $PORTS; do
        # Never kill port 7777 (Homeport server itself)
        if [ "$PORT" != "7777" ] && [ -n "$PORT" ]; then
            PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
            if [ -n "$PIDS" ]; then
                for PID in $PIDS; do
                    echo "Stopping process $PID on port $PORT..."
                    kill -TERM "$PID" 2>/dev/null || true
                done
                sleep 0.2
                for PID in $PIDS; do
                    kill -9 "$PID" 2>/dev/null || true
                done
            fi
        fi
    done
fi

echo "✅ All registered apps have been terminated."
