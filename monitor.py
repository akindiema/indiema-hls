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
NGINX_LOG = "/data/nginx_access.log"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS viewer_log (
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    channel_id TEXT,
                    viewers INTEGER,
                    ip TEXT,
                    country TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_current_viewers(channel_id):
    try:
        if not os.path.exists(NGINX_LOG):
            return 5
        cmd = f"grep -a '{channel_id}' {NGINX_LOG} | grep '.ts' | tail -n 500 | awk '{{print $1}}' | sort -u | wc -l"
        output = os.popen(cmd).read().strip()
        return int(output) if output else 5
    except:
        return 5

def get_country_from_ip(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/country_name/", timeout=3)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return "Unknown"

def generate_report():
    channels = load_channels()
    report = []
    for cid, info in channels.items():
        viewers = get_current_viewers(cid)
        try:
            r = requests.get(f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", timeout=3)
            status = "ONLINE" if r.status_code == 200 else "OFFLINE"
        except:
            status = "OFFLINE"
        
        # Log with IP & Country (simplified)
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT INTO viewer_log (channel_id, viewers, country) VALUES (?, ?, ?)", 
                     (cid, viewers, "IN"))  # Placeholder - improve with real IP later
        conn.commit()
        conn.close()
        
        report.append({
            "id": cid,
            "name": info.get("name", cid),
            "status": status,
            "clip_count": len(info.get("programs", [])),
            "viewers": viewers
        })
    return report

def load_channels():
    if not os.path.exists(CHANNELS_FILE): return {}
    try:
        with open(CHANNELS_FILE) as f:
            return json.load(f)
    except:
        return {}

@app.route("/api/stats")
def api_stats():
    return jsonify(generate_report())

@app.route("/api/analytics")
def api_analytics():
    channel = request.args.get('channel')
    days = int(request.args.get('days', 30))
    conn = sqlite3.connect(DB_FILE)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    query = "SELECT timestamp, viewers, country FROM viewer_log WHERE channel_id = ? AND timestamp >= ? ORDER BY timestamp"
    data = conn.execute(query, (channel, cutoff)).fetchall()
    conn.close()
    return jsonify([{"time": row[0], "viewers": row[1], "country": row[2]} for row in data])

@app.route("/monitor")
def monitor():
    return redirect("/monitor.php")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
