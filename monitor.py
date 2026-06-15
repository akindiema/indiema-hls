import os
import json
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")

def load_analytics():
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"active_sessions": 0, "estimated_total_viewers": 0, "summary": {}, "countries": [], "ad_activity": {}, "channels": {}}

def get_channel_status():
    """Check which channels are actually running"""
    try:
        # Call app_final.py status (we'll add this tiny endpoint later if needed)
        r = requests.get("http://127.0.0.1:5000/status", timeout=2)
        if r.status_code == 200:
            return r.json().get("active_channels", [])
    except:
        pass
    # Fallback: Try known channels from analytics
    return list(load_analytics().get("channels", {}).keys())

MONITOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>IndieMa TV Analytics</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        body { background:#0a0f1c; color:#e2e8f0; }
        .card-custom { background:#1e2937; border:1px solid #334155; border-radius:12px; }
        .status-dot { width:14px; height:14px; border-radius:50%; display:inline-block; vertical-align:middle; }
        .status-live { background:#22c55e; box-shadow:0 0 8px #22c55e; animation: pulse 2s infinite; }
        .status-offline { background:#ef4444; }
        @keyframes pulse { 0%,100% {opacity:1} 50% {opacity:0.6} }
    </style>
</head>
<body class="p-4">
<div class="container-fluid">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1><i class="bi bi-speedometer2"></i> IndieMa TV Live Monitor</h1>
        <div>
            <select id="channelSelect" class="form-select d-inline w-auto me-2" onchange="filterChannel()">
                <option value="">All Channels</option>
            </select>
            <button class="btn btn-success me-2" onclick="downloadReport()">📥 Report</button>
            <button class="btn btn-danger" onclick="clearAnalytics()">🗑️ Clear</button>
        </div>
    </div>

    <!-- Global Stats -->
    <div class="row mb-4">
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>LOGGED VIEWERS</small><h1 id="live" class="text-white">0</h1></div></div>
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>ESTIMATED TOTAL</small><h1 id="est" class="text-warning">0</h1></div></div>
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>TOTAL HOURS</small><h1 id="hours" class="text-success">0</h1></div></div>
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>AVG SESSION</small><h1 id="avg" class="text-info">0</h1><small>min</small></div></div>
    </div>

    <!-- Live Channels Status -->
    <h4 class="mb-3"><i class="bi bi-broadcast"></i> Live Channels Status</h4>
    <div class="row" id="channel-status"></div>

    <div class="row mt-4">
        <div class="col-md-7"><div class="card-custom p-4"><h5>Top Countries</h5><div id="countries"></div></div></div>
        <div class="col-md-5"><div class="card-custom p-4"><h5>Ad Insertion Status</h5><div id="ads"></div></div></div>
    </div>
</div>

<script>
function updateDashboard() {
    fetch('/api/analytics').then(r => r.json()).then(data => {
        document.getElementById('live').textContent = data.active_sessions || 0;
        document.getElementById('est').textContent = data.estimated_total_viewers || 0;
        document.getElementById('hours').textContent = (data.summary?.total_watch_time_hours || 0).toFixed(1);
        document.getElementById('avg').textContent = (data.summary?.avg_watch_time_mins || 0).toFixed(1);

        // Channel Status Cards
        let html = '';
        const activeCh = data.channels || {};
        Object.keys(activeCh).forEach(cid => {
            const viewers = activeCh[cid] || 0;
            const isLive = viewers > 0;
            html += `
                <div class="col-lg-4 col-md-6 mb-3">
                    <div class="card-custom p-3">
                        <div class="d-flex justify-content-between">
                            <strong>${cid.toUpperCase()}</strong>
                            <span><span class="status-dot ${isLive ? 'status-live' : 'status-offline'}"></span> ${isLive ? 'LIVE' : 'OFFLINE'}</span>
                        </div>
                        <h3 class="mb-0">${viewers} <small>viewers</small></h3>
                    </div>
                </div>`;
        });
        document.getElementById('channel-status').innerHTML = html || '<p class="text-muted">No active channels detected</p>';

        // Countries
        let chtml = '';
        (data.countries || []).forEach(c => {
            chtml += `<div>${c.country} <span class="badge bg-primary float-end">${c.viewers}</span></div>`;
        });
        document.getElementById('countries').innerHTML = chtml;
    });
}

setInterval(updateDashboard, 5000);
window.onload = updateDashboard;

function downloadReport() { 
    const ch = document.getElementById('channelSelect').value || 'all';
    window.location.href = `/api/report?channel=${ch}&days=30`;
}

function clearAnalytics() {
    if(confirm("Clear ALL analytics?")) fetch('/clear-analytics', {method:'POST'}).then(()=>location.reload());
}

function filterChannel() {
    updateDashboard();
}
</script>
</body>
</html>
"""

# ====================== ROUTES ======================
@app.route("/api/analytics")
def api_analytics():
    return jsonify(load_analytics())

@app.route("/api/report")
def download_report():
    channel = request.args.get("channel", "all")
    days = request.args.get("days", "30")
    # TODO: Connect to real history later
    output = f"Date,Channel,Viewers,Avg_Session,Country\n"
    output += f"{datetime.now().date()}, {channel}, 12, 18.5, India\n"
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=indiema_report_{channel}_{days}d.csv"})

@app.route("/clear-analytics", methods=["POST"])
def clear_analytics():
    default = {"active_sessions":0, "estimated_total_viewers":0, "summary":{}, "countries":[], "ad_activity":{}, "channels":{}}
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(default, f, indent=2)
    return jsonify({"success": True})

@app.route("/monitor")
@app.route("/")
def dashboard():
    return render_template_string(MONITOR_HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5020, debug=False)
