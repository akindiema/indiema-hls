import os
import json
import time
import threading
import re
import requests
from datetime import datetime
from collections import defaultdict

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")
NGINX_LOG_PATH = os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.log")

VIEWER_TRACKER = defaultdict(dict)
SESSION_COUNTER = defaultdict(int)          # New app sessions
ANALYTICS_LOCK = threading.Lock()

GEO_CACHE = {}
GEO_CACHE_TTL = 86400

# ================== CONFIG ==================
INACTIVITY_TIMEOUT = 25
ESTIMATION_MULTIPLIER = 4.0      # Adjust after you get real data from Swift TV
# ===========================================

def save_analytics(analytics):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with ANALYTICS_LOCK:
            tmp_file = ANALYTICS_FILE + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump(analytics, f, indent=2)
            os.replace(tmp_file, ANALYTICS_FILE)
    except Exception as e:
        print(f"Save error: {e}")


def is_app_traffic(user_agent: str) -> bool:
    """Much stricter detection for real CTV / Swift TV like traffic"""
    if not user_agent:
        return False
    ua = user_agent.lower()

    # Strong CTV / Smart TV indicators
    strong_indicators = [
        'swift', 'roku', 'tvos', 'fire tv', 'smarttv', 'smart-tv', 'hbbtv',
        'webos', 'tizen', 'android tv', 'googletv', 'bravia', 'vestel'
    ]
    
    # Weaker but still good indicators (require combination)
    weak_indicators = ['ctv', 'exoplayer', 'smart-hub']
    
    # Block common false positives
    false_positives = ['chrome', 'firefox', 'safari', 'edge', 'mozilla', 'applewebkit', 'android; mobile']
    
    # Must have at least one strong indicator
    has_strong = any(ind in ua for ind in strong_indicators)
    if has_strong:
        return True
    
    # Or weak indicator + not a common browser
    has_weak = any(ind in ua for ind in weak_indicators)
    is_browser = any(fp in ua for fp in false_positives)
    
    return has_weak and not is_browser


def get_viewer_key(ip, user_agent):
    ua = (user_agent or "unknown")[:120]
    return f"{ip}:{ua}"


def parse_log_line(line):
    pattern = r'(?P<ip>[\d.:]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+).*?"(?P<user_agent>[^"]*)"'
    match = re.search(pattern, line)
    if not match:
        return None, None, None, False

    url = match.group('url')
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    if any(x in url for x in ['/segments/', '.ts', '.m4s', '.m3u8']):
        cid_match = re.search(r'/channel/([^/]+)/', url)
        cid = cid_match.group(1) if cid_match else "unknown"
        viewer_key = get_viewer_key(ip, user_agent)
        is_app = is_app_traffic(user_agent)
        return cid, viewer_key, ip, is_app
    return None, None, None, False


# log_watcher and update_analytics_loop remain almost the same as previous version
# (Only change is using the stricter is_app_traffic)

def log_watcher():
    print(f"✅ Analytics Collector started with strict CTV detection.")
    for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore')):
        cid, viewer_key, ip, is_app = parse_log_line(line)
        if not cid or not viewer_key:
            continue

        now = time.time()
        session = VIEWER_TRACKER[cid].get(viewer_key)

        if session:
            delta = now - session["last_seen"]
            session["total_watch"] += delta
        else:
            session = {
                "start_time": now,
                "last_seen": now,
                "total_watch": 0,
                "ip": ip,
                "is_app": is_app
            }
            VIEWER_TRACKER[cid][viewer_key] = session
            if is_app:
                SESSION_COUNTER[cid] += 1

        session["last_seen"] = now


def update_analytics_loop():
    while True:
        try:
            now = time.time()
            analytics = {
                "summary": {"total_watch_time_hours": 0.0, "avg_watch_time_mins": 0.0, "peak_concurrent": 0},
                "active_sessions": 0,
                "estimated_total_viewers": 0,
                "app_traffic_sessions": 0,
                "channels": {},
                "countries": [],
                "timeline": [],
                "timeline_data": [],
                "last_updated": datetime.now().isoformat(),
                "trend": "stable"
            }

            total_concurrent = 0
            peak = 0
            total_watch_sec = 0
            app_sessions = 0
            country_stats = defaultdict(int)

            for cid, viewers in list(VIEWER_TRACKER.items()):
                for key in list(viewers.keys()):
                    s = viewers[key]
                    if now - s["last_seen"] > INACTIVITY_TIMEOUT:
                        total_watch_sec += s.get("total_watch", 0)
                        del viewers[key]
                        continue

                    concurrent = len(viewers)
                    total_concurrent += concurrent
                    if concurrent > peak:
                        peak = concurrent

                    if s.get("is_app"):
                        app_sessions += 1

                    geo = get_geo_info(s["ip"])   # assume get_geo_info function exists as before
                    country_stats[geo["country"]] += 1

                if not viewers:
                    del VIEWER_TRACKER[cid]

            estimated = int(total_concurrent * ESTIMATION_MULTIPLIER)

            analytics["summary"]["peak_concurrent"] = peak
            analytics["active_sessions"] = total_concurrent
            analytics["estimated_total_viewers"] = estimated
            analytics["app_traffic_sessions"] = app_sessions

            if total_concurrent > 0:
                analytics["summary"]["total_watch_time_hours"] = round(total_watch_sec / 3600, 2)
                analytics["summary"]["avg_watch_time_mins"] = round((total_watch_sec / 60) / total_concurrent, 1)

            # Countries, timeline, save... (same as previous full version)

            save_analytics(analytics)

        except Exception as e:
            print(f"Update error: {e}")

        time.sleep(5)


if __name__ == "__main__":
    import tailer
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({"status": "running", "app_sessions": sum(SESSION_COUNTER.values())})

    print("🚀 Strict CTV Detection Collector running on port 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
