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
HISTORY_FILE = os.path.join(DATA_DIR, "analytics_history.json")

VIEWER_TRACKER = defaultdict(dict)   # cid -> viewer_key -> session
AD_ACTIVITY = defaultdict(lambda: {"cue_out_count": 0, "last_cue_time": 0})
HISTORY = {"snapshots": []}

ANALYTICS_LOCK = threading.Lock()
INACTIVITY_TIMEOUT = 45

def save_analytics(analytics):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with ANALYTICS_LOCK:
            tmp = ANALYTICS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(analytics, f, indent=2)
            os.replace(tmp, ANALYTICS_FILE)
    except: pass

def load_or_init_history():
    global HISTORY
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                HISTORY = json.load(f)
        except: pass

def save_history():
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(HISTORY, f, indent=2)
    except: pass

def get_geo_info(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
        data = r.json()
        return {"country": data.get("country_name", "Unknown")}
    except:
        return {"country": "Unknown"}

def parse_log_line(line):
    pattern = r'(?P<ip>[\d.:]+) - .*? "(?P<method>\w+) (?P<url>.*?) HTTP.*?" .*?"(?P<user_agent>[^"]*)"'
    m = re.search(pattern, line)
    if not m: return None, None, None, False

    url = m.group('url').lower()
    ip = m.group('ip')
    ua = m.group('user_agent')

    cid_match = re.search(r'/channel/([^/]+)/', m.group('url'))
    cid = cid_match.group(1) if cid_match else None
    if not cid and '/segments/' in url:
        seg_match = re.search(r'/segments/([a-z0-9-]+)_', url)
        cid = seg_match.group(1) if seg_match else "unknown"

    is_cue = '/variant_' in url and '.m3u8' in url
    viewer_key = f"{ip}:{ua[:80]}"
    return cid, viewer_key, ip, is_cue

def log_watcher():
    print("✅ Exact Concurrent Tracker Started")
    import tailer
    for line in tailer.follow(open("/var/log/nginx/access.log", encoding='utf-8', errors='ignore')):
        cid, key, ip, is_cue = parse_log_line(line)
        if not cid or not key: continue

        now = time.time()
        if key not in VIEWER_TRACKER[cid]:
            VIEWER_TRACKER[cid][key] = {"start": now, "last": now, "ip": ip}
        else:
            VIEWER_TRACKER[cid][key]["last"] = now

        if is_cue:
            AD_ACTIVITY[cid]["last_cue_time"] = now

def update_loop():
    load_or_init_history()
    while True:
        now = time.time()
        analytics = {
            "active_sessions": 0,
            "estimated_total_viewers": 0,
            "summary": {"total_watch_time_hours": 0.0, "avg_watch_time_mins": 0.0},
            "channels": {},
            "countries": [],
            "ad_activity": {},
            "last_updated": datetime.now().isoformat()
        }

        total_concurrent = 0
        country_count = defaultdict(int)
        total_watch = 0

        for cid in list(VIEWER_TRACKER.keys()):
            active = 0
            for k in list(VIEWER_TRACKER[cid].keys()):
                s = VIEWER_TRACKER[cid][k]
                if now - s["last"] > INACTIVITY_TIMEOUT:
                    total_watch += (s["last"] - s["start"])
                    del VIEWER_TRACKER[cid][k]
                    continue
                active += 1
                geo = get_geo_info(s["ip"])
                country_count[geo["country"]] += 1

            if active > 0:
                analytics["channels"][cid] = active
                total_concurrent += active

            if not VIEWER_TRACKER[cid]:
                del VIEWER_TRACKER[cid]

        # Exact Concurrent
        analytics["active_sessions"] = total_concurrent
        analytics["estimated_total_viewers"] = total_concurrent   # Now exact (no multiplier)

        if total_concurrent > 0:
            analytics["summary"]["avg_watch_time_mins"] = round((total_watch / 60) / total_concurrent, 1)
        analytics["summary"]["total_watch_time_hours"] = round(total_watch / 3600, 2)

        # Countries & Ad
        for c, cnt in sorted(country_count.items(), key=lambda x: x[1], reverse=True)[:8]:
            analytics["countries"].append({"country": c, "viewers": cnt})

        for cid in analytics["channels"]:
            ad = AD_ACTIVITY[cid]
            mins = (now - ad.get("last_cue_time", 0)) / 60
            analytics["ad_activity"][cid] = {
                "status": "🟢 Active" if mins < 20 else "⚪ Idle",
                "last_ad_minutes_ago": round(mins, 1)
            }

        save_analytics(analytics)

        # Save snapshot for reports
        if len(HISTORY["snapshots"]) == 0 or (now - HISTORY["snapshots"][-1]["ts"]) > 300:   # every 5 min
            HISTORY["snapshots"].append({
                "ts": now,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "concurrent": total_concurrent,
                "channels": dict(analytics["channels"])
            })
            if len(HISTORY["snapshots"]) > 2000:   # keep ~7 days
                HISTORY["snapshots"] = HISTORY["snapshots"][-1500:]
            save_history()

        time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=log_watcher, daemon=True).start()
    threading.Thread(target=update_loop, daemon=True).start()

    from flask import Flask, jsonify
    app = Flask(__name__)
    app.run(host="0.0.0.0", port=5021, debug=False)
