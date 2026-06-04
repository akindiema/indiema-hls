import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, send_file
import csv
import io

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

def get_current_viewers(channel_id):
    try:
        if not os.path.exists(NGINX_LOG):
            return 5
        cmd = f"grep -a '{channel_id}' {NGINX_LOG} | grep '.ts' | tail -n 500 | awk '{{print $1}}' | sort -u | wc -l"
        output = os.popen(cmd).read().strip()
        return int(output) if output else 5
    except:
        return 5

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
        
        # Log to DB
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT INTO viewer_log (channel_id, viewers) VALUES (?, ?)", (cid, viewers))
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

@app.route("/api/stats")
def api_stats():
    return jsonify(generate_report())

@app.route("/api/analytics")
def api_analytics():
    channel_id = request.args.get('channel')
    days = int(request.args.get('days', 30))
    conn = sqlite3.connect(DB_FILE)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    query = "SELECT timestamp, viewers FROM viewer_log WHERE channel_id = ? AND timestamp >= ? ORDER BY timestamp"
    data = conn.execute(query, (channel_id, cutoff)).fetchall()
    conn.close()
    return jsonify([{"time": row[0], "viewers": row[1]} for row in data])

@app.route("/api/export")
def export_csv():
    channel_id = request.args.get('channel')
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT timestamp, viewers FROM viewer_log"
    if channel_id:
        query += " WHERE channel_id = ?"
        data = conn.execute(query, (channel_id,)).fetchall()
    else:
        data = conn.execute(query).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Viewers"])
    writer.writerows(data)
    output.seek(0)

    return send_file(output, mimetype="text/csv", as_attachment=True, download_name=f"{channel_id or 'all'}_analytics.csv")

@app.route("/monitor")
def monitor():
    return redirect("/monitor.php")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
