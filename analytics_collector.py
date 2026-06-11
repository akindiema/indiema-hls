import os
import json
import time
import threading
from datetime import datetime
from collections import defaultdict
import re
import tailer  # pip install tailer

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")
NGINX_LOG_PATH = os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.log")

# {channel_id: {viewer_key: last_seen_timestamp}}
VIEWER_TRACKER = defaultdict(dict)
ANALYTICS_LOCK = threading.Lock()

def save_analytics(analytics):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with ANALYTICS_LOCK:
            tmp_file = ANALYTICS_FILE + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump(analytics, f, indent=2)
            os.replace(tmp_file, ANALYTICS_FILE)
    except Exception as e:
        print(f"Save analytics error: {e}")


def get_viewer_key(ip: str, user_agent: str) -> str:
    """Create a more unique key than just IP"""
    ua = (user_agent or "unknown")[:120]  # truncate long UAs
    return f"{ip}:{ua}"


def parse_log_line(line: str):
    # Improved regex to also capture User-Agent (recommended nginx log format)
    # Example log format: $remote_addr - $remote_user [$time_local] "$request" $status ...
    pattern = r'(?P<ip>[\d.:]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+).*?"(?P<user_agent>[^"]*)"'
    
    match = re.search(pattern, line)
    if not match:
        return None, None

    url = match.group('url')
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    # Only track actual video delivery requests
    if '/segments/' in url or url.endswith(('.ts', '.m4s', '.m3u8')):
        cid_match = re.search(r'/channel/([^/]+)/', url)
        cid = cid_match.group(1) if cid_match else "unknown"
        
        viewer_key = get_viewer_key(ip, user_agent)
        return cid, viewer_key

    return None, None


def log_watcher():
    print(f"✅ Analytics Collector started. Watching: {NGINX_LOG_PATH}")
    
    for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore')):
        cid, viewer_key = parse_log_line(line)
        if cid and viewer_key:
            VIEWER_TRACKER[cid][viewer_key] = time.time()


def update_analytics_loop():
    while True:
        try:
            now = time.time()
            analytics = {
                "summary": {
                    "total_watch_time_hours": 0,      # TODO: implement proper calculation
                    "avg_watch_time_mins": 0,
                    "peak_concurrent": 0
                },
                "active_sessions": 0,
                "channels": {},
                "countries": [{"country": "Unknown", "city": "Global", "viewers": 0, "percentage": 100}],
                "timeline": [],
                "timeline_data": [],
                "last_updated": datetime.now().isoformat()
            }

            total_concurrent = 0
            peak = 0

            for cid, viewers in VIEWER_TRACKER.items():
                # Clean inactive viewers (25 seconds timeout is better for HLS)
                for key in list(viewers.keys()):
                    if now - viewers[key] > 25:
                        del viewers[key]

                concurrent = len(viewers)
                total_concurrent += concurrent
                if concurrent > peak:
                    peak = concurrent

                if concurrent > 0:
                    analytics["channels"][cid] = {
                        "live_viewers": concurrent,
                        "display_name": cid.upper()
                    }

            analytics["summary"]["peak_concurrent"] = max(
                analytics["summary"]["peak_concurrent"], peak
            )
            analytics["active_sessions"] = total_concurrent

            # Simple timeline (last 4 hours)
            slot = datetime.now().strftime("%H:%M")
            if not analytics["timeline"] or analytics["timeline"][-1] != slot:
                analytics["timeline"].append(slot)
                analytics["timeline_data"].append(total_concurrent)
                if len(analytics["timeline"]) > 48:   # 48 * 5min = 4 hours
                    analytics["timeline"] = analytics["timeline"][-48:]
                    analytics["timeline_data"] = analytics["timeline_data"][-48:]

            save_analytics(analytics)

        except Exception as e:
            print(f"Analytics update error: {e}")

        time.sleep(5)   # Update every 5 seconds


if __name__ == "__main__":
    # Start background threads
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    # Simple health check server
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({
            "status": "running",
            "active_channels": len(VIEWER_TRACKER),
            "total_viewers": sum(len(v) for v in VIEWER_TRACKER.values())
        })

    print("🚀 Analytics Collector + Health server started on port 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
