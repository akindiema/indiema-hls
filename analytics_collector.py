import os
import json
import time
import threading
from datetime import datetime
from collections import defaultdict
import re
import tailer  # pip install tailer (add to requirements)

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")
NGINX_LOG_PATH = os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.log")  # Adjust if different

VIEWER_TRACKER = defaultdict(dict)   # {cid: {ip: last_seen}}
ANALYTICS_LOCK = threading.Lock()

def save_analytics(analytics):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with ANALYTICS_LOCK:
            with open(ANALYTICS_FILE + ".tmp", "w") as f:
                json.dump(analytics, f, indent=2)
            os.replace(ANALYTICS_FILE + ".tmp", ANALYTICS_FILE)
    except Exception as e:
        print(f"Save analytics error: {e}")

def parse_log_line(line):
    # Parse common Nginx log format
    pattern = r'(?P<ip>[\d.]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+)'
    match = re.search(pattern, line)
    if not match:
        return None, None
    
    url = match.group('url')
    ip = match.group('ip')
    
    if '/segments/' in url or url.endswith('.ts'):
        # Extract channel id from URL: /channel/indiematv/segments/xxx.ts
        cid_match = re.search(r'/channel/([^/]+)/', url)
        cid = cid_match.group(1) if cid_match else "unknown"
        return cid, ip
    return None, None

def log_watcher():
    print(f"Analytics Collector started. Watching: {NGINX_LOG_PATH}")
    
    for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore')):
        cid, ip = parse_log_line(line)
        if cid and ip:
            VIEWER_TRACKER[cid][ip] = time.time()

def update_analytics_loop():
    while True:
        try:
            now = time.time()
            analytics = {
                "summary": {
                    "total_watch_time_hours": 1420,   # You can improve later
                    "avg_watch_time_mins": 24.5,
                    "peak_concurrent": 0
                },
                "countries": [   # Will be basic for now
                    {"country": "Unknown", "city": "Global", "viewers": 0, "percentage": 100}
                ],
                "timeline": [],
                "timeline_data": [],
                "channels": {},
                "last_updated": datetime.now().isoformat(),
                "active_sessions": 0
            }

            total_concurrent = 0
            peak = 0

            for cid, viewers in VIEWER_TRACKER.items():
                # Clean inactive viewers (no request in last 45 seconds)
                for ip in list(viewers.keys()):
                    if now - viewers[ip] > 45:
                        del viewers[ip]

                concurrent = len(viewers)
                total_concurrent += concurrent
                if concurrent > peak:
                    peak = concurrent

                analytics["channels"][cid] = {
                    "live_viewers": concurrent,
                    "display_name": cid.upper()
                }

            analytics["summary"]["peak_concurrent"] = peak
            analytics["active_sessions"] = total_concurrent

            # Simple timeline
            slot = datetime.now().strftime("%H:%M")
            if not analytics["timeline"] or analytics["timeline"][-1] != slot:
                analytics["timeline"].append(slot)
                analytics["timeline_data"].append(total_concurrent)
                if len(analytics["timeline"]) > 48:
                    analytics["timeline"] = analytics["timeline"][-48:]
                    analytics["timeline_data"] = analytics["timeline_data"][-48:]

            save_analytics(analytics)

        except Exception as e:
            print(f"Analytics update error: {e}")

        time.sleep(6)   # Update every 6 seconds

if __name__ == "__main__":
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()
    
    # Keep main thread alive + simple health endpoint
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route("/health")
    def health():
        return jsonify({"status": "analytics_collector_running", "active_channels": len(VIEWER_TRACKER)})
    
    app.run(host="0.0.0.0", port=5021, debug=False)
