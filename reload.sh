#!/bin/bash
echo "Stopping HLS Engine..."
fuser -k 5000/tcp
echo "Starting HLS Engine with new URLs..."
nohup /home/kanth/hls_engine/venv/bin/python3 /home/kanth/hls_engine/app.py > /home/kanth/hls_engine/app_log.txt 2>&1 &
echo "Engine Reloaded Successfully!"
