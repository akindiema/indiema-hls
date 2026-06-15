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

# ====================== CORE STRUCTURES ======================
VIEWER_TRACKER = defaultdict(dict)      # cid -> viewer_key -> session
AD_ACTIVITY = defaultdict(lambda: {"cue_out_count": 0, "last_cue_time": 0, "ad_segments": 0})
SESSION_COUNTER = defaultdict(int)

ANALYTICS_LOCK = threading.Lock()
INACTIVITY_TIMEOUT = 35          # seconds
ESTIMATION_MULTIPLIER = 4.0

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

def is_hls_request(url: str) -> bool:
    return any(x in url.lower() for x in ['/master.m3u8', '/variant_', '/segments/', '.ts', '.m3u8'])

def is_app_traffic(user_agent: str) -> bool:
    if not user_agent: return False
    ua = user_agent.lower()
    return any(k in ua for k in ['swift', 'roku', 'tvos', 'fire tv', 'smarttv', 'android tv', 'webos', 'tizen'])

def get_viewer_key(ip, user_agent):
    ua = (user_agent or "unknown")[:100]
    return f"{ip}:{ua}"

def parse_log_line(line: str):
    # More robust regex for common Nginx log formats
    pattern = r'(?P<ip>[\d.:]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+).*?"(?P<user_agent>[^"]*)"'
    match = re.search(pattern, line)
    if not match:
        return None, None, None, False, False, False

    url = match.group('url').lower()
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    cid_match = re.search(r'/channel/([^/]+)/', match.group('url'))
    cid = cid_match.group(1) if cid_match else None

    if not cid and '/segments/' in url:
        # Try to extract cid from segment filename
        seg_match = re.search(r'([a-z0-9-]+)_\d+_\d+_\d+\.ts', url)
        cid = seg_match.group(1) if seg_match else "unknown"

    is_app = is_app_traffic(user_agent)
    is_cue = '/variant_' in url and '.m3u8' in url
    is_ad = any(x in url for x in ['ad', 'break', 'slate', 'cue'])

    return cid, get_viewer_key(ip, user_agent), ip, is_app, is_cue, is_ad

def log_watcher():
    print(f"✅ Analytics Collector started - Watching: {NGINX_LOG_PATH}")
    
    if not os.path.exists(NGINX_LOG_PATH):
        print(f"⚠️ WARNING: Log file not found: {NGINX_LOG_PATH}")
        print("   Make sure Nginx is configured to log to this path.")
        return

    try:
        import tailer
        for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore'), delay=0.5):
            try:
                cid, viewer_key, ip, is_app, is_cue, is_ad = parse_log_line(line)
                if not cid or not viewer_key:
                    continue

                now = time.time()
                session = VIEWER_TRACKER[cid].get(viewer_key)

                if not session:
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
                else:
                    session["total_watch"] += (now - session["last_seen"])

                session["last_seen"] = now

                # Ad Tracking
                if is_cue:
                    AD_ACTIVITY[cid]["cue_out_count"] += 1
                    AD_ACTIVITY[cid]["last_cue_time"] = now
                if is_ad:
                    AD_ACTIVITY[cid]["ad_segments"] += 1

            except Exception as e:
                continue  # Skip bad lines
    except ImportError:
        print("❌ 'tailer' module not found. Install with: pip install tailer")
    except Exception as e:
        print(f"Log watcher error: {e}")

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
                "ad_activity": {},
                "timeline": [],
                "timeline_data": [],
                "last_updated": datetime.now().isoformat(),
                "trend": "stable"
            }

            total_concurrent = 0
            peak = 0
            total_watch_sec = 0
            app_sessions = 0

            for cid in list(VIEWER_TRACKER.keys()):
                viewers = VIEWER_TRACKER[cid]
                for key in list(viewers.keys()):
                    s = viewers[key]
                    if now - s["last_seen"] > INACTIVITY_TIMEOUT:
                        total_watch_sec += s.get("total_watch", 0)
                        del viewers[key]
                        continue

                    total_concurrent += 1
                    if s.get("is_app"):
                        app_sessions += 1

                if len(viewers) > peak:
                    peak = len(viewers)

                if not viewers:
                    del VIEWER_TRACKER[cid]

            # Final calculations
            analytics["active_sessions"] = total_concurrent
            analytics["estimated_total_viewers"] = int(total_concurrent * ESTIMATION_MULTIPLIER)
            analytics["app_traffic_sessions"] = app_sessions
            analytics["summary"]["peak_concurrent"] = peak

            if total_watch_sec > 0:
                analytics["summary"]["total_watch_time_hours"] = round(total_watch_sec / 3600, 2)
                analytics["summary"]["avg_watch_time_mins"] = round((total_watch_sec / 60) / max(total_concurrent, 1), 1)

            # Ad Activity
            for cid in VIEWER_TRACKER.keys():
                ad = AD_ACTIVITY.get(cid, {})
                minutes_ago = (now - ad.get("last_cue_time", 0)) / 60
                analytics["ad_activity"][cid] = {
                    "ad_breaks_detected": ad.get("cue_out_count", 0),
                    "last_ad_minutes_ago": round(minutes_ago, 1),
                    "status": "🟢 Ads Likely Filling" if minutes_ago < 18 else "⚪ No Recent Ads"
                }

            save_analytics(analytics)

        except Exception as e:
            print(f"Analytics update error: {e}")

        time.sleep(5)

# ====================== START ======================
if __name__ == "__main__":
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({"status": "running", "log_path": NGINX_LOG_PATH})

    print("🚀 Optimized Analytics Collector with improved HLS detection running on 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
