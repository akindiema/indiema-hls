import requests
import json
import os
import subprocess
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# === DOCKER COMPATIBLE PATH ===
DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

NGINX_LOG = "/var/log/nginx/access.log"

def get_channels():
    if not os.path.exists(CHANNELS_FILE): return {}
    try:
        with open(CHANNELS_FILE, "r") as f:
            content = f.read().strip()
            if not content: return {}
            return json.loads(content)
    except:
        return {}

def get_live_viewers(channel_id):
    """
    Counts unique IPs that requested a .ts segment for a specific channel 
    in the last 2 minutes from the Nginx access log.
    """
    try:
        # Command: grep for channel segments | get unique IPs | count
        cmd = f"grep '{channel_id}' {NGINX_LOG} | grep '.ts' | awk '{{print $1}}' | sort -u | wc -l"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        return int(output) if output else 0
    except:
        return 0

def generate_report():
    channels = get_channels()
    report = []
    for cid, info in channels.items():
        # Check if Engine is serving the master playlist
        try:
            # Increased timeout to 3s to prevent false 'OFFLINE' reports during heavy load
            r = requests.get(
                f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", 
                timeout=3,
                headers={'User-Agent': 'IndieMa-Monitor/1.0'}
            )
            status = "ONLINE" if r.status_code == 200 else "OFFLINE"
        except:
            status = "OFFLINE"
            
        report.append({
            "id": cid,
            "name": info.get("name", cid),
            "status": status,
            "color": "success" if status == "ONLINE" else "danger",
            "clip_count": len(info.get("programs", [])),
            "viewers": get_live_viewers(cid)
        })
    return report

# --- ROUTES ---

@app.route("/")
def dashboard():
    """Main Web View"""
    report = generate_report()
    return render_template_string(HTML_TEMPLATE, report=report)

@app.route("/api/stats")
def api_stats():
    """JSON API for your PHP Monitor"""
    return jsonify(generate_report())

# --- HTML TEMPLATE ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa | Stream Health</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <meta http-equiv="refresh" content="30">
    <style>
        body { background: #0f172a; color: white; padding: 40px; font-family: sans-serif; }
        .card { background: #1e293b; border: none; border-radius: 15px; transition: 0.3s; }
        .status-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .bg-success { background-color: #00ff88 !important; box-shadow: 0 0 10px #00ff88; }
        .bg-danger { background-color: #ff4444 !important; box-shadow: 0 0 10px #ff4444; }
        .viewer-count { font-size: 1.5rem; font-weight: bold; color: #38bdf8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-5">
            <h1 class="fw-bold">📡 Live Network Health</h1>
            <div class="text-end">
                <span class="badge bg-dark border border-secondary p-2">Auto-refresh: 30s</span>
            </div>
        </div>

        <div class="row">
            {% for s in report %}
            <div class="col-md-6 mb-4">
                <div class="card p-4 shadow-lg border-top border-4 border-{{ s.color }}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h3 class="mb-1 text-white">{{ s.name }}</h3>
                            <p class="text-muted small">ID: {{ s.id }} | Clips: {{ s.clip_count }}</p>
                        </div>
                        <div class="text-end">
                            <div class="status-dot bg-{{ s.color }}"></div>
                            <span class="fw-bold text-{{ s.color }}">{{ s.status }}</span>
                        </div>
                    </div>
                    <div class="mt-3 pt-3 border-top border-secondary d-flex justify-content-between align-items-center">
                        <span class="text-muted small uppercase">Live Viewers</span>
                        <span class="viewer-count">{{ s.viewers }}</span>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
