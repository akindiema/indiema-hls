import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")
DB_FILE = os.path.join(DATA_DIR, "analytics.db")

# Init DB
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS viewer_log (
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    channel_id TEXT,
                    viewers INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def load_channels():
    if not os.path.exists(CHANNELS_FILE): return {}
    try:
        with open(CHANNELS_FILE) as f:
            return json.load(f)
    except:
        return {}

def log_viewers():
    channels = load_channels()
    for cid in channels.keys():
        try:
            r = requests.get(f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", timeout=3)
            viewers = 8 if r.status_code == 200 else 0   # Placeholder - improve later
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO viewer_log (channel_id, viewers) VALUES (?, ?)", (cid, viewers))
            conn.commit()
            conn.close()
        except:
            pass

def get_analytics(channel_id=None, period="30d"):
    conn = sqlite3.connect(DB_FILE)
    days = {"1d":1, "7d":7, "15d":15, "30d":30, "90d":90, "1y":365, "all":9999}.get(period, 30)
    
    query = "SELECT timestamp, channel_id, viewers FROM viewer_log WHERE timestamp >= ?"
    params = [(datetime.now() - timedelta(days=days)).isoformat()]
    if channel_id:
        query += " AND channel_id = ?"
        params.append(channel_id)
    
    data = conn.execute(query, params).fetchall()
    conn.close()
    return data

# ====================== ROUTES ======================
@app.route("/api/stats")
def api_stats():
    log_viewers()   # Log current viewers
    channels = load_channels()
    report = []
    for cid, info in channels.items():
        try:
            r = requests.get(f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", timeout=3)
            status = "ONLINE" if r.status_code == 200 else "OFFLINE"
        except:
            status = "OFFLINE"
        report.append({
            "id": cid,
            "name": info.get("name", cid),
            "status": status,
            "clip_count": len(info.get("programs", [])),
            "viewers": 0
        })
    return jsonify(report)

@app.route("/api/analytics")
def api_analytics():
    channel = request.args.get('channel')
    period = request.args.get('period', '30d')
    data = get_analytics(channel, period)
    return jsonify(data)

@app.route("/monitor")
def monitor():
    return redirect("/monitor.php")

@app.route("/")
def home():
    return "Analytics running. Go to /monitor.php"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
