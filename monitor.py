import os
import json
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)
DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")
HISTORY_FILE = os.path.join(DATA_DIR, "analytics_history.json")

def load_analytics():
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE) as f:
                return json.load(f)
        except: pass
    return {"active_sessions":0, "channels":{}, "countries":[], "ad_activity":{}}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except: pass
    return {"snapshots": []}

MONITOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>IndieMa TV Analytics</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        body { background:#0a0f1c; color:#e2e8f0; }
        .card-custom { background:#1e2937; border:1px solid #334155; border-radius:12px; }
        .status-dot { width:14px; height:14px; border-radius:50%; display:inline-block; }
        .status-live { background:#22c55e; box-shadow:0 0 8px #22c55e; animation:pulse 2s infinite; }
        .status-offline { background:#ef4444; }
        @keyframes pulse {0%,100%{opacity:1} 50%{opacity:0.6}}
    </style>
</head>
<body class="p-4">
<div class="container-fluid">
    <div class="d-flex justify-content-between mb-4">
        <h1><i class="bi bi-speedometer2"></i> IndieMa TV Live Monitor</h1>
        <div>
            <select id="channelSelect" class="form-select d-inline w-auto me-2"></select>
            <select id="daysSelect" class="form-select d-inline w-auto me-2">
                <option value="1">Today</option>
                <option value="7">7 Days</option>
                <option value="30" selected>30 Days</option>
            </select>
            <button class="btn btn-success me-2" onclick="downloadReport()">📥 Report</button>
            <button class="btn btn-danger" onclick="clearAnalytics()">🗑️ Clear</button>
        </div>
    </div>

    <div class="row mb-4">
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>CONCURRENT VIEWERS</small><h1 id="live" class="text-white">0</h1></div></div>
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>TOTAL HOURS</small><h1 id="hours" class="text-success">0</h1></div></div>
        <div class="col-md-3"><div class="card-custom p-4 text-center"><small>AVG SESSION</small><h1 id="avg" class="text-info">0</h1><small>min</small></div></div>
    </div>

    <h4 class="mb-3"><i class="bi bi-broadcast"></i> Live Channels Status</h4>
    <div class="row mb-4" id="channel-status"></div>
</div>

<script>
function updateDashboard() {
    fetch('/api/analytics').then(r => r.json()).then(data => {
        document.getElementById('live').textContent = data.active_sessions || 0;
        document.getElementById('hours').textContent = (data.summary?.total_watch_time_hours || 0).toFixed(1);
        document.getElementById('avg').textContent = (data.summary?.avg_watch_time_mins || 0).toFixed(1);

        // Channel Status
        let html = '';
        Object.keys(data.channels || {}).forEach(cid => {
            const viewers = data.channels[cid];
            html += `
                <div class="col-lg-4 col-md-6 mb-3">
                    <div class="card-custom p-3">
                        <div class="d-flex justify-content-between">
                            <strong>${cid.toUpperCase()}</strong>
                            <span><span class="status-dot ${viewers > 0 ? 'status-live' : 'status-offline'}"></span> LIVE</span>
                        </div>
                        <h3>${viewers} <small>concurrent</small></h3>
                    </div>
                </div>`;
        });
        document.getElementById('channel-status').innerHTML = html || '<p>No active channels</p>';

        // Populate dropdown
        const sel = document.getElementById('channelSelect');
        sel.innerHTML = '<option value="">All Channels</option>';
        Object.keys(data.channels || {}).forEach(cid => {
            let opt = document.createElement('option');
            opt.value = cid; opt.textContent = cid.toUpperCase();
            sel.appendChild(opt);
        });
    });
}
setInterval(updateDashboard, 4000);
window.onload = updateDashboard;

function downloadReport() {
    const ch = document.getElementById('channelSelect').value || 'all';
    const days = document.getElementById('daysSelect').value;
    window.location.href = `/api/report?channel=${ch}&days=${days}`;
}

function clearAnalytics() {
    if(confirm("Clear all data?")) fetch('/clear-analytics', {method:'POST'}).then(()=>location.reload());
}
</script>
</body>
</html>
"""

@app.route("/api/analytics")
def api_analytics():
    return jsonify(load_analytics())

@app.route("/api/report")
def download_report():
    channel = request.args.get("channel", "all")
    days = int(request.args.get("days", 30))
    
    history = load_history()
    output = "Timestamp,Concurrent_Viewers,Channel,Note\n"
    
    for snap in history.get("snapshots", []):
        if channel != "all" and channel not in snap.get("channels", {}):
            continue
        conc = snap.get("concurrent", 0)
        output += f"{snap['time']},{conc},{channel if channel!='all' else 'All'},Exact Count\n"
    
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=concurrent_report_{channel}_{days}d.csv"})

@app.route("/clear-analytics", methods=["POST"])
def clear_analytics():
    default = {"active_sessions":0, "channels":{}, "summary":{}}
    with open(ANALYTICS_FILE, "w") as f:
        json.dump(default, f, indent=2)
    return jsonify({"success": True})

@app.route("/monitor")
@app.route("/")
def dashboard():
    return render_template_string(MONITOR_HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5020, debug=False)
