import os
import json
import time
import threading
import re
import requests
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")
NGINX_LOG_PATH = os.getenv("NGINX_ACCESS_LOG", "/var/log/nginx/access.log")

# {cid: {viewer_key: session_data}}
VIEWER_TRACKER = defaultdict(dict)
ANALYTICS_LOCK = threading.Lock()

# GeoIP cache: {ip: {"country": , "city": , "last_updated": }}
GEO_CACHE = {}
GEO_CACHE_TTL = 86400  # 24 hours

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


def get_geo_info(ip: str):
    """Simple free IP geolocation with cache"""
    if ip in GEO_CACHE and time.time() - GEO_CACHE[ip].get("last_updated", 0) < GEO_CACHE_TTL:
        return GEO_CACHE[ip]

    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?fields=country,city", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            geo = {
                "country": data.get("country", "Unknown"),
                "city": data.get("city", "Unknown"),
                "last_updated": time.time()
            }
            GEO_CACHE[ip] = geo
            return geo
    except:
        pass
    return {"country": "Unknown", "city": "Unknown", "last_updated": time.time()}


def get_viewer_key(ip: str, user_agent: str) -> str:
    ua = (user_agent or "unknown")[:100]
    return f"{ip}:{ua}"


def parse_log_line(line: str):
    pattern = r'(?P<ip>[\d.:]+) - .*?\[(?P<time>.*?)\] "(?P<method>\w+) (?P<url>.*?) HTTP.*?" (?P<status>\d+).*?"(?P<user_agent>[^"]*)"'
    match = re.search(pattern, line)
    if not match:
        return None, None

    url = match.group('url')
    ip = match.group('ip')
    user_agent = match.group('user_agent')

    if any(x in url for x in ['/segments/', '.ts', '.m4s', '.m3u8']):
        cid_match = re.search(r'/channel/([^/]+)/', url)
        cid = cid_match.group(1) if cid_match else "unknown"
        viewer_key = get_viewer_key(ip, user_agent)
        return cid, viewer_key, ip
    return None, None, None


def log_watcher():
    print(f"✅ Analytics Collector started. Watching: {NGINX_LOG_PATH}")
    for line in tailer.follow(open(NGINX_LOG_PATH, encoding='utf-8', errors='ignore')):
        cid, viewer_key, ip = parse_log_line(line)
        if cid and viewer_key and ip:
            now = time.time()
            session = VIEWER_TRACKER[cid].get(viewer_key)

            if session:
                # Accumulate watch time since last seen
                delta = now - session["last_seen"]
                session["total_watch"] += delta
            else:
                # New session
                session = {
                    "start_time": now,
                    "last_seen": now,
                    "total_watch": 0,
                    "ip": ip
                }
                VIEWER_TRACKER[cid][viewer_key] = session

            session["last_seen"] = now


def update_analytics_loop():
    while True:
        try:
            now = time.time()
            analytics = {
                "summary": {
                    "total_watch_time_hours": 0.0,
                    "avg_watch_time_mins": 0.0,
                    "peak_concurrent": 0
                },
                "active_sessions": 0,
                "channels": {},
                "countries": [],
                "timeline": [],
                "timeline_data": [],
                "last_updated": datetime.now().isoformat()
            }

            total_concurrent = 0
            peak = 0
            total_watch_seconds = 0
            country_stats = defaultdict(int)

            for cid, viewers in list(VIEWER_TRACKER.items()):
                for key in list(viewers.keys()):
                    session = viewers[key]
                    # Clean inactive (30 seconds timeout)
                    if now - session["last_seen"] > 30:
                        # Finalize watch time
                        total_watch_seconds += session["total_watch"]
                        del viewers[key]
                        continue

                    concurrent = len(viewers)
                    total_concurrent += concurrent
                    if concurrent > peak:
                        peak = concurrent

                    # Geo
                    geo = get_geo_info(session["ip"])
                    country_stats[geo["country"]] += 1

                    if cid not in analytics["channels"]:
                        analytics["channels"][cid] = {
                            "live_viewers": concurrent,
                            "display_name": cid.upper(),
                            "total_watch_hours": round(session["total_watch"] / 3600, 2)
                        }

                if not viewers:  # Remove empty channel
                    del VIEWER_TRACKER[cid]

            # Global stats
            analytics["summary"]["peak_concurrent"] = max(analytics.get("summary", {}).get("peak_concurrent", 0), peak)
            analytics["active_sessions"] = total_concurrent

            if total_concurrent > 0:
                analytics["summary"]["total_watch_time_hours"] = round(total_watch_seconds / 3600, 2)
                analytics["summary"]["avg_watch_time_mins"] = round((total_watch_seconds / 60) / total_concurrent, 1)

            # Countries
            for country, count in country_stats.items():
                analytics["countries"].append({
                    "country": country,
                    "viewers": count,
                    "percentage": round((count / total_concurrent) * 100, 1) if total_concurrent > 0 else 0
                })

            # Timeline
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

        time.sleep(5)


if __name__ == "__main__":
    import tailer  # pip install tailer

    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_analytics_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({
            "status": "running",
            "active_channels": len(VIEWER_TRACKER),
            "total_viewers": sum(len(v) for v in VIEWER_TRACKER.values())
        })

    print("🚀 Analytics Collector with Watch Time + GeoIP started on port 5021")
    app.run(host="0.0.0.0", port=5021, debug=False)
