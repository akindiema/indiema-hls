import requests
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")
DB_FILE = os.path.join(DATA_DIR, "analytics.db")

# Initialize DB
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''CREATE TABLE IF NOT EXISTS viewer_stats (
                    timestamp TEXT,
                      channel_id TEXT,
                      viewers INTEGER,
                      concurrent INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def load_channels():
    if not os.path.exists(CHANNELS_FILE): return {}
    try:
        with open(CHANNELS_FILE, "r") as f:
            return json.loads(f.read().strip())
    except:
        return {}

def log_viewer_count(channel_id, viewers):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT INTO viewer_stats VALUES (?, ?, ?, ?)",
                 (datetime.now().isoformat(), channel_id, viewers, viewers))
    conn.commit()
    conn.close()

def get_analytics(channel_id=None, days=30):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT timestamp, channel_id, viewers FROM viewer_stats WHERE timestamp >= ?"
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
    channels = load_channels()
    report = []
    for cid, info in channels.items():
        try:
            r = requests.get(f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", 
                           timeout=3, headers={'User-Agent': 'Monitor'})
            status = "ONLINE" if r.status_code == 200 else "OFFLINE"
            viewers = 5  # Placeholder - improve later with real log parsing
        except:
            status = "OFFLINE"
            viewers = 0
        
        log_viewer_count(cid, viewers)
        
        report.append({
            "id": cid,
            "name": info.get("name", cid),
            "status": status,
            "clip_count": len(info.get("programs", [])),
            "viewers": viewers
        })
    return jsonify(report)

@app.route("/api/analytics")
def api_analytics():
    channel_id = request.args.get('channel')
    days = int(request.args.get('days', 30))
    data = get_analytics(channel_id, days)
    return jsonify(data)

@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

# ====================== HTML (Simple for now) ======================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <meta http-equiv="refresh" content="30">
</head>
<body class="p-4 bg-dark text-white">
    <h1>📊 IndieMa Analytics Dashboard</h1>
    <p>Basic version ready. Full history + filters coming in next update.</p>
    <a href="/monitor.php" class="btn btn-primary">Go to Beautiful Monitor</a>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
