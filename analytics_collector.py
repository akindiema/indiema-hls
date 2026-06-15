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

# ====================== CORE STRUCTURES ======================
VIEWER_TRACKER = defaultdict(dict)      # cid -> viewer_key -> session
AD_ACTIVITY = defaultdict(lambda: {"cue_out_count": 0, "last_cue_time": 0})
GEO_CACHE = {}
ANALYTICS_LOCK = threading.Lock()

INACTIVITY_TIMEOUT = 45   # seconds (ideal for HLS)
ESTIMATION_MULTIPLIER = 2.5   # Realistic multiplier (you can change)

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

def get_geo_info(ip):
    if ip in GEO_CACHE and time.time() - GEO_CACHE[ip].get('ts', 0) < 86400:
        return GEO_CACHE[ip]
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=4)
        if r.status_code == 200:
            data = r.json()
            country = data.get("country_name") or data.get("country") or "Unknown"
            GEO_CACHE[ip] = {"country": country, "ts": time.time()}
            return {"country": country}
    except:
        pass
    return {"country": "Unknown"}

def parse_log_line(line: str):
    pattern = r'(?P<ip>[\d.:]+) - .*? "(?P<method>\w+) (?P<url>.*?) HTTP.*?" .*?"(?P<user_agent>[^"]*)"'
    match = re.search(pattern, line)
    if not match:
        return None, None, None, False

    url = match.group('url').lower()
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    # Extract Channel ID
    cid_match = re.search(r'/channel/([^/]+)/', match.group('url'))
    cid = cid_match.group(1) if cid_match else None

    if not cid and '/segments/' in url:
        seg_match = re.search(r'/segments/([a-z0-9-]+)_', url)
        cid = seg_match.group(1) if seg_match else "unknown"

    is_cue = '/variant_' in url and '.m3u8' in url

    viewer_key = f"{ip}:{user_agent[:80]}"
    return cid, viewer_key, ip, is_cue

def log_watcher():
    print("✅ Final Analytics Collector Started - Watching Nginx Logs")
    try:
        import tailer
        log_file = open("/var/log/nginx/access.log", encoding='utf-8', errors='ignore')
        
        for line in tailer.follow(log_file, delay=0.3):
            try:
                cid, viewer_key, ip, is_cue = parse_log_line(line)
                if not cid or not viewer_key:
                    continue

                now = time.time()

                if viewer_key not in VIEWER_TRACKER[cid]:
                    VIEWER_TRACKER[cid][viewer_key] = {
                        "start": now,
                        "last": now,
                        "ip": ip
                    }
                else:
                    VIEWER_TRACKER[cid][viewer_key]["last"] = now

                if is_cue:
                    AD_ACTIVITY[cid]["cue_out_count"] += 1
                    AD_ACTIVITY[cid]["last_cue_time"] = now

            except:
                continue
    except Exception as e:
        print(f"Log watcher error: {e}")

def update_analytics_loop():
    while True:
        try:
            now = time.time()
            analytics = {
                "active_sessions": 0,
                "estimated_total_viewers": 0,
                "summary": {"total_watch_time_hours": 0.0, "avg_watch_time_mins": 0.0, "peak_concurrent": 0},
                "countries": [],
                "ad_activity": {},
                "channels": {},
                "last_updated": datetime.now().isoformat()
            }

            total_concurrent = 0
            total_watch_sec = 0
            country_count = defaultdict(int)

            for cid in list(VIEWER_TRACKER.keys()):
                active_viewers = 0
                for key in list(VIEWER_TRACKER[cid].keys()):
                    s = VIEWER_TRACKER[cid][key]
                    if now - s["last"] > INACTIVITY_TIMEOUT:
                        total_watch_sec += (s["last"] - s["start"])
                        del VIEWER_TRACKER[cid][key]
                        continue
                    
                    active_viewers += 1
                    geo = get_geo_info(s["ip"])
                    country_count[geo["country"]] += 1

                if active_viewers > 0:
                    analytics["channels"][cid] = active_viewers
                    total_concurrent += active_viewers

                if not VIEWER_TRACKER[cid]:
                    del VIEWER_TRACKER[cid]

            # Final Calculations
            analytics["active_sessions"] = total_concurrent
            analytics["estimated_total_viewers"] = int(total_concurrent * ESTIMATION_MULTIPLIER)

            if total_concurrent > 0:
                analytics["summary"]["avg_watch_time_mins"] = round((total_watch_sec / 60) / total_concurrent, 1)
            analytics["summary"]["total_watch_time_hours"] = round(total_watch_sec / 3600, 2)

            # Countries
            for country, count in sorted(country_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                analytics["countries"].append({"country": country, "viewers": count})

            # Ad Activity
            for cid in analytics["channels"]:
                ad = AD_ACTIVITY[cid]
                mins_ago = (now - ad.get("last_cue_time", 0)) / 60
                analytics["ad_activity"][cid] = {
                    "ad_breaks_detected": ad.get("cue_out_count", 0),
                    "last_ad_minutes_ago": round(mins_ago, 1),
                    "status": "🟢 Active" if mins_ago < 20 else "⚪ Idle"
                }

            save_analytics(analytics)

        except Exception as e:
            print(f"Update loop error: {e}")

        time.sleep(5)

# ====================== START ======================
if __name__ == "__main__":
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({
            "status": "running",
            "active_channels": len(VIEWER_TRACKER),
            "log_path": "/var/log/nginx/access.log"
        })

    print("🚀 Final Smart Analytics Collector v2.0 Running on Port 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
