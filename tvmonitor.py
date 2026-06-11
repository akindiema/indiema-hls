import os
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify

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
    return {"summary": {"total_watch_time_hours": 0, "avg_watch_time_mins": 0, "peak_concurrent": 0},
            "active_sessions": 0, "estimated_total_viewers": 0, "app_traffic_sessions": 0,
            "channels": {}, "countries": [], "timeline": [], "timeline_data": [],
            "last_updated": datetime.now().isoformat(), "trend": "stable"}

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
        .trend-up { color: #4ade80; }
        .trend-down { color: #f87171; }
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1 class="fw-bold"><i class="bi bi-speedometer2 text-info me-2"></i>IndieMa TV Live Monitor</h1>
            <span class="badge bg-success fs-6 px-3 py-2" id="last-updated">Just now</span>
        </div>

        <!-- Global Metrics -->
        <div class="row mb-4">
            <div class="col-md-3"><div class="card-custom p-4 text-center">
                <small>TOTAL ACTIVE (LOGGED)</small>
                <h1 class="metric-value text-white" id="total-viewers">0</h1>
            </div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center">
                <small>ESTIMATED TOTAL (Swift TV)</small>
                <h1 class="metric-value text-warning" id="estimated-viewers">0</h1>
            </div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center">
                <small>TOTAL WATCH HOURS</small>
                <h1 class="metric-value text-success" id="total-hours">0</h1>
            </div></div>
            <div class="col-md-3"><div class="card-custom p-4 text-center">
                <small>AVG SESSION</small>
                <h1 class="metric-value text-info" id="avg-session">0</h1><small>minutes</small>
            </div></div>
        </div>

        <!-- Swift TV / App Traffic -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5><i class="bi bi-tv me-2"></i>Swift TV & CTV App Traffic</h5>
                    <div class="row text-center">
                        <div class="col-md-4">
                            <h3 class="text-primary" id="app-sessions">0</h3>
                            <small>Detected App Sessions</small>
                        </div>
                        <div class="col-md-4">
                            <h3 id="trend-indicator">STABLE</h3>
                            <small>Trend</small>
                        </div>
                        <div class="col-md-4">
                            <small class="text-muted">Multiplier used: <span id="multiplier">4x</span></small>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Countries & Channels (same as previous version) -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5><i class="bi bi-globe text-primary me-2"></i>Top Countries</h5>
                    <div class="row" id="countries-row"></div>
                </div>
            </div>
        </div>

        <h4 class="mb-3"><i class="bi bi-broadcast text-danger me-2"></i>Live Channels</h4>
        <div class="row" id="channel-cards"></div>

        <div class="row mt-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5>Audience Timeline (Last 4 Hours)</h5>
                    <canvas id="timelineChart" height="120"></canvas>
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
                document.getElementById('last-updated').textContent = 'Updated ' + new Date(data.last_updated).toLocaleTimeString();

                // Trend
                const trendEl = document.getElementById('trend-indicator');
                trendEl.textContent = (data.trend || 'stable').toUpperCase();
                trendEl.className = data.trend === 'rising' ? 'trend-up' : (data.trend === 'dropping' ? 'trend-down' : '');

                // Countries, Channels, Chart... (kept from previous version - abbreviated here for space)
                // ... (full countries + channel cards code from my previous response)

                // Timeline Chart update (same as before)
            }).catch(err => console.error(err));
        }
        setInterval(updateDashboard, 5000);
        window.onload = updateDashboard;
    </script>
</body>
</html>
"""

# (Keep the same Flask routes as in your previous version)
@app.route("/api/analytics")
def api_analytics():
    return jsonify(load_analytics())

@app.route("/monitor")
@app.route("/")
def monitor_dashboard():
    return render_template_string(MONITOR_HTML)

if __name__ == "__main__":
    if not os.path.exists(ANALYTICS_FILE):
        with open(ANALYTICS_FILE, "w") as f:
            json.dump(get_default_analytics(), f, indent=2)
    app.run(host="0.0.0.0", port=5020, debug=False)
