#!/bin/bash
echo "===================================="
echo "Reloading IndieMa HLS Engine..."
echo "===================================="

# Kill any existing processes on our ports
fuser -k 5000/tcp 5001/tcp 5010/tcp 2>/dev/null || true

# Restart the services (inside Docker they run in background)
pkill -f "python final.py" 2>/dev/null || true
pkill -f "python tvmanager.py" 2>/dev/null || true
pkill -f "python yt_relay.py" 2>/dev/null || true

sleep 2

# Start fresh
python final.py > /data/app_log.txt 2>&1 &
python tvmanager.py > /data/manager_log.txt 2>&1 &
python yt_relay.py > /data/yt_log.txt 2>&1 &

echo "✅ HLS Engine Reloaded Successfully!"
echo "Master URL: http://127.0.0.1:5000/channel/indiematv/master.m3u8"
echo "Manager: http://127.0.0.1:5001"
