import os
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")

def load_analytics():
    if not os.path.exists(ANALYTICS_FILE):
        return get_default_analytics()
    try:
        with open(ANALYTICS_FILE, "r") as f:
            return json.load(f)
    except:
        return get_default_analytics()

def get_default_analytics():
    return {
        "summary": {"total_watch_time_hours": 0, "avg_watch_time_mins": 0, "peak_concurrent": 0},
        "active_sessions": 0,
        "estimated_total_viewers": 0,
        "app_traffic_sessions": 0,
        "channels": {},
        "countries": [],
        "ad_activity": {},
        "timeline": [],
        "timeline_data": [],
        "last_updated": datetime.now().isoformat(),
        "trend": "stable"
    }

MONITOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa TV - Live Analytics</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        body { background: #0a0f1c; color: #e2e8f0; }
        .card-custom { background: #1e2937; border: 1px solid #334155; border-radius: 16px; }
        .live-dot { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .metric-value { font-size: 2.8rem; font-weight: 700; }
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1 class="fw-bold"><i class="bi bi-speedometer2 text-info me-2"></i>IndieMa TV Live Monitor</h1>
            <button onclick="clearAnalytics()" class="btn btn-danger px-4"><i class="bi bi-trash"></i> Clear</button>
        </div>

        <!-- Global Metrics -->
        <div class="row mb-4">
            <div class="col-md-3"><div class="card-custom p-4 text-center"><small>LOGGED VIEWERS</small><h1 class="metric-value text-white" id="total-viewers">0</h1></div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center"><small>ESTIMATED TOTAL</small><h1 class="metric-value text-warning" id="estimated-viewers">0</h1></div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center"><small>TOTAL WATCH HOURS</small><h1 class="metric-value text-success" id="total-hours">0</h1></div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center"><small>AVG SESSION</small><h1 class="metric-value text-info" id="avg-session">0</h1><small>min</small></div></div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5><i class="bi bi-tv"></i> Swift TV & CTV Traffic</h5>
                    <div class="row text-center">
                        <div class="col-md-4"><h3 id="app-sessions" class="text-primary">0</h3><small>App Sessions</small></div>
                        <div class="col-md-4"><h3 id="trend-indicator">STABLE</h3><small>Trend</small></div>
                        <div class="col-md-4"><small>Multiplier: <strong>4x</strong></small></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Ad Status -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5><i class="bi bi-megaphone text-warning"></i> Ad Insertion (SCTE-35) Status</h5>
                    <div class="row" id="ad-status-row"></div>
                </div>
            </div>
        </div>

        <h4 class="mb-3"><i class="bi bi-broadcast text-danger"></i> Live Channels</h4>
        <div class="row" id="channel-cards"></div>

        <div class="row mt-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5>Audience Timeline</h5>
                    <canvas id="timelineChart" height="130"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        let timelineChart;
        function updateDashboard() {
            fetch('/api/analytics').then(r => r.json()).then(data => {
                document.getElementById('total-viewers').textContent = data.active_sessions || 0;
                document.getElementById('estimated-viewers').textContent = data.estimated_total_viewers || 0;
                document.getElementById('total-hours').textContent = Math.round(data.summary?.total_watch_time_hours || 0);
                document.getElementById('avg-session').textContent = data.summary?.avg_watch_time_mins?.toFixed(1) || '0';
                document.getElementById('app-sessions').textContent = data.app_traffic_sessions || 0;

                // Ad Status
                const adRow = document.getElementById('ad-status-row');
                adRow.innerHTML = '';
                Object.keys(data.ad_activity || {}).forEach(cid => {
                    const ad = data.ad_activity[cid];
                    adRow.innerHTML += `
                        <div class="col-md-4 mb-3">
                            <div class="card-custom p-3">
                                <strong>${cid.toUpperCase()}</strong><br>
                                <span class="badge ${ad.last_ad_minutes_ago < 15 ? 'bg-success' : 'bg-secondary'}">${ad.status}</span>
                                <small>Last ad: ${ad.last_ad_minutes_ago} min ago</small>
                            </div>
                        </div>`;
                });
            });
        }
        setInterval(updateDashboard, 4000);
        window.onload = updateDashboard;

        function clearAnalytics() {
            if (confirm("Clear all analytics?")) fetch('/clear-analytics', {method: 'POST'}).then(() => location.reload());
        }
    </script>
</body>
</html>
"""

@app.route("/api/analytics")
def api_analytics():
    return jsonify(load_analytics())

@app.route("/clear-analytics", methods=["POST"])
def clear_analytics():
    try:
        default = {
            "summary": {"total_watch_time_hours": 0, "avg_watch_time_mins": 0, "peak_concurrent": 0},
            "active_sessions": 0, "estimated_total_viewers": 0, "app_traffic_sessions": 0,
            "channels": {}, "countries": [], "ad_activity": {},
            "timeline": [], "timeline_data": [],
            "last_updated": datetime.now().isoformat()
        }
        with open(ANALYTICS_FILE, "w") as f:
            json.dump(default, f, indent=2)
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

@app.route("/monitor")
@app.route("/")
def monitor_dashboard():
    return render_template_string(MONITOR_HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5020, debug=False)
