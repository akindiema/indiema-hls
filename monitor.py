import os
import json
import csv
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
        .status-dot { width:14px; height:14px; border-radius:50%; display:inline-block; }
        .status-live { background:#22c55e; box-shadow:0 0 8px #22c55e; animation: pulse 2s infinite; }
        .status-offline { background:#ef4444; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }
    </style>
</head>
<body class="p-4">
<div class="container-fluid">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1><i class="bi bi-speedometer2"></i> IndieMa TV Live Monitor</h1>
        <div>
            <select id="channelSelect" class="form-select d-inline w-auto me-2" onchange="updateDashboard()"></select>
            <select id="daysSelect" class="form-select d-inline w-auto me-2">
                <option value="1">Today</option>
                <option value="7">Last 7 Days</option>
                <option value="30" selected>Last 30 Days</option>
                <option value="90">Last 3 Months</option>
            </select>
            <button class="btn btn-success me-2" onclick="downloadReport()">📥 Download Report</button>
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

    <!-- Channel Status -->
    <h4 class="mb-3"><i class="bi bi-broadcast"></i> Live Channels Status</h4>
    <div class="row mb-4" id="channel-status"></div>

    <div class="row">
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

        // Populate Channel Dropdown
        const select = document.getElementById('channelSelect');
        select.innerHTML = '<option value="">All Channels</option>';
        Object.keys(data.channels || {}).forEach(cid => {
            const opt = document.createElement('option');
            opt.value = cid;
            opt.textContent = cid.toUpperCase();
            select.appendChild(opt);
        });

        // Channel Status Cards
        let html = '';
        const chData = data.channels || {};
        Object.keys(chData).forEach(cid => {
            const viewers = chData[cid] || 0;
            html += `
                <div class="col-lg-4 col-md-6 mb-3">
                    <div class="card-custom p-3">
                        <div class="d-flex justify-content-between align-items-center">
                            <strong>${cid.toUpperCase()}</strong>
                            <span><span class="status-dot ${viewers > 0 ? 'status-live' : 'status-offline'}"></span> ${viewers > 0 ? 'LIVE' : 'OFFLINE'}</span>
                        </div>
                        <h3 class="mb-0">${viewers} <small class="text-muted">viewers</small></h3>
                    </div>
                </div>`;
        });
        document.getElementById('channel-status').innerHTML = html || '<p class="text-muted">No channels detected yet. Play a channel.</p>';

        // Countries
        let chtml = '';
        (data.countries || []).forEach(c => {
            chtml += `<div class="mb-2">${c.country} <span class="badge bg-primary float-end">${c.viewers}</span></div>`;
        });
        document.getElementById('countries').innerHTML = chtml || 'No data';
    });
}

setInterval(updateDashboard, 5000);
window.onload = updateDashboard;

function downloadReport() {
    const channel = document.getElementById('channelSelect').value || 'all';
    const days = document.getElementById('daysSelect').value;
    window.location.href = `/api/report?channel=${channel}&days=${days}`;
}

function clearAnalytics() {
    if(confirm("Clear ALL analytics data?")) {
        fetch('/clear-analytics', {method:'POST'}).then(() => location.reload());
    }
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
    # Current simple version - will improve with history later
    output = "Timestamp,Channel,Logged_Viewers,Estimated_Viewers,Avg_Session_Min,Country\n"
    output += f"{datetime.now()}, {channel}, 5, 12, 18.5, India\n"
    output += f"{datetime.now()}, {channel}, 7, 17, 22.0, Singapore\n"

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
