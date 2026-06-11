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
SESSION_COUNTER = defaultdict(int)
AD_ACTIVITY = defaultdict(lambda: {"cue_out_count": 0, "last_cue_time": 0, "ad_segments": 0})

ANALYTICS_LOCK = threading.Lock()
GEO_CACHE = {}
GEO_CACHE_TTL = 86400

INACTIVITY_TIMEOUT = 25
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


def is_app_traffic(user_agent: str) -> bool:
    if not user_agent: return False
    ua = user_agent.lower()
    strong = ['swift', 'roku', 'tvos', 'fire tv', 'smarttv', 'android tv', 'webos', 'tizen', 'hbbtv']
    return any(k in ua for k in strong)


def get_viewer_key(ip, user_agent):
    ua = (user_agent or "unknown")[:120]
    return f"{ip}:{ua}"


def parse_log_line(line: str):
    pattern = r'(?P<ip>[\d.:]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+).*?"(?P<user_agent>[^"]*)"'
    match = re.search(pattern, line)
    if not match:
        return None, None, None, False, False

    url = match.group('url').lower()
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    is_app = is_app_traffic(user_agent)
    is_cue_request = '/variant_' in url and '.m3u8' in url
    is_ad_segment = any(x in url for x in ['ad', 'break', 'slate', 'cue'])

    cid_match = re.search(r'/channel/([^/]+)/', url)
    cid = cid_match.group(1) if cid_match else "unknown"

    viewer_key = get_viewer_key(ip, user_agent)
    return cid, viewer_key, ip, is_app, is_cue_request, is_ad_segment


def log_watcher():
    print("✅ Analytics Collector started with Ad Detection")
    for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore')):
        cid, viewer_key, ip, is_app, is_cue, is_ad = parse_log_line(line)
        if not cid or not viewer_key:
            continue

        now = time.time()
        session = VIEWER_TRACKER[cid].get(viewer_key)

        if not session:
            session = {"start_time": now, "last_seen": now, "total_watch": 0, "ip": ip, "is_app": is_app}
            VIEWER_TRACKER[cid][viewer_key] = session
            if is_app:
                SESSION_COUNTER[cid] += 1
        else:
            session["total_watch"] += (now - session["last_seen"])

        session["last_seen"] = now

        # Ad Signal Tracking
        if is_cue:
            AD_ACTIVITY[cid]["cue_out_count"] += 1
            AD_ACTIVITY[cid]["last_cue_time"] = now
        if is_ad:
            AD_ACTIVITY[cid]["ad_segments"] += 1


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
                    if concurrent > peak: peak = concurrent

                    if s.get("is_app"):
                        app_sessions += 1

                    geo = get_geo_info(s["ip"]) if 'get_geo_info' in globals() else {"country": "Unknown"}
                    country_stats[geo["country"]] += 1

                if not viewers:
                    del VIEWER_TRACKER[cid]

            estimated = int(total_concurrent * ESTIMATION_MULTIPLIER)

            analytics["active_sessions"] = total_concurrent
            analytics["estimated_total_viewers"] = estimated
            analytics["app_traffic_sessions"] = app_sessions
            analytics["summary"]["peak_concurrent"] = peak

            if total_concurrent > 0:
                analytics["summary"]["total_watch_time_hours"] = round(total_watch_sec / 3600, 2)
                analytics["summary"]["avg_watch_time_mins"] = round((total_watch_sec / 60) / total_concurrent, 1)

            # Ad Activity
            for cid in list(VIEWER_TRACKER.keys()):
                ad = AD_ACTIVITY.get(cid, {})
                minutes_ago = (now - ad.get("last_cue_time", 0)) / 60
                analytics["ad_activity"][cid] = {
                    "ad_breaks_detected": ad.get("cue_out_count", 0),
                    "last_ad_minutes_ago": round(minutes_ago, 1),
                    "ad_segments": ad.get("ad_segments", 0),
                    "status": "🟢 Ads Likely Filling" if minutes_ago < 15 else "⚪ No Recent Ads"
                }

            # Countries, Timeline, Save...
            for country, count in country_stats.items():
                analytics["countries"].append({
                    "country": country,
                    "viewers": count,
                    "percentage": round((count / total_concurrent) * 100, 1) if total_concurrent > 0 else 0
                })

            slot = datetime.now().strftime("%H:%M")
            if not analytics["timeline"] or analytics["timeline"][-1] != slot:
                analytics["timeline"].append(slot)
                analytics["timeline_data"].append(total_concurrent)
                if len(analytics["timeline"]) > 48:
                    analytics["timeline"] = analytics["timeline"][-48:]
                    analytics["timeline_data"] = analytics["timeline_data"][-48:]

            save_analytics(analytics)

        except Exception as e:
            print(f"Update error: {e}")

        time.sleep(5)


def get_geo_info(ip):
    # (Same as previous version - omitted for brevity)
    return {"country": "Unknown"}


if __name__ == "__main__":
    import tailer
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({"status": "running"})

    print("🚀 Collector with SCTE-35 Ad Detection running on 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
