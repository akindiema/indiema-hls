import os
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# === CONFIGURATIONS ===
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
        "summary": {
            "total_watch_time_hours": 0,
            "avg_watch_time_mins": 0,
            "peak_concurrent": 0
        },
        "active_sessions": 0,
        "estimated_total_viewers": 0,
        "app_traffic_sessions": 0,
        "channels": {},
        "countries": [],
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
        body { background: #0a0f1c; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }
        .card-custom { background: #1e2937; border: 1px solid #334155; border-radius: 16px; }
        .live-dot { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .metric-value { font-size: 2.8rem; font-weight: 700; }
        .channel-card { transition: all 0.3s; }
        .channel-card:hover { transform: translateY(-4px); }
        h1, h4, h5, h6, .card-custom small, .text-muted { color: #ffffff !important; }
        .text-muted { opacity: 0.85; }
        .trend-up { color: #4ade80; }
        .trend-down { color: #f87171; }
        .country-flag { font-size: 1.5rem; }
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="fw-bold mb-0"><i class="bi bi-speedometer2 text-info me-2"></i>IndieMa TV Live Monitor</h1>
                <small class="text-muted">Real-time Viewership • Updated every 5s</small>
            </div>
            <div class="text-end">
                <span class="badge bg-success fs-6 px-3 py-2" id="last-updated">Just now</span>
            </div>
        </div>

        <!-- Global Metrics -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card-custom p-4 text-center">
                    <small class="text-muted">LOGGED ACTIVE VIEWERS</small>
                    <h1 class="metric-value text-white" id="total-viewers">0</h1>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card-custom p-4 text-center">
                    <small class="text-muted">ESTIMATED TOTAL (Swift TV)</small>
                    <h1 class="metric-value text-warning" id="estimated-viewers">0</h1>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card-custom p-4 text-center">
                    <small class="text-muted">TOTAL WATCH HOURS</small>
                    <h1 class="metric-value text-success" id="total-hours">0</h1>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card-custom p-4 text-center">
                    <small class="text-muted">AVG SESSION</small>
                    <h1 class="metric-value text-info" id="avg-session">0</h1>
                    <small class="text-muted">minutes</small>
                </div>
            </div>
        </div>

        <!-- Swift TV App Traffic -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5 class="mb-3"><i class="bi bi-tv-fill text-primary me-2"></i>Swift TV & CTV App Traffic</h5>
                    <div class="row text-center">
                        <div class="col-md-4">
                            <h3 class="text-primary mb-0" id="app-sessions">0</h3>
                            <small class="text-muted">Detected App Sessions</small>
                        </div>
                        <div class="col-md-4">
                            <h3 class="mb-0" id="trend-indicator">STABLE</h3>
                            <small class="text-muted">Viewership Trend</small>
                        </div>
                        <div class="col-md-4">
                            <small class="text-muted">Estimation Multiplier: <strong id="multiplier">4x</strong></small>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Top Countries -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5 class="mb-3"><i class="bi bi-globe text-primary me-2"></i>Top Countries</h5>
                    <div class="row" id="countries-row"></div>
                </div>
            </div>
        </div>

        <!-- Live Channels -->
        <h4 class="mb-3 text-white"><i class="bi bi-broadcast text-danger me-2"></i>Live Channels</h4>
        <div class="row" id="channel-cards"></div>

        <!-- Audience Timeline -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card-custom p-4">
                    <h5 class="mb-3">Audience Timeline (Last 4 Hours)</h5>
                    <canvas id="timelineChart" height="130"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        let timelineChart;

        function updateDashboard() {
            fetch('/api/analytics')
                .then(r => r.json())
                .then(data => {
                    // Global Metrics
                    document.getElementById('total-viewers').textContent = data.active_sessions || 0;
                    document.getElementById('estimated-viewers').textContent = data.estimated_total_viewers || 0;
                    document.getElementById('total-hours').textContent = Math.round(data.summary?.total_watch_time_hours || 0);
                    document.getElementById('avg-session').textContent = data.summary?.avg_watch_time_mins?.toFixed(1) || '0';
                    document.getElementById('app-sessions').textContent = data.app_traffic_sessions || 0;
                    document.getElementById('multiplier').textContent = "4x";

                    // Last Updated
                    const last = new Date(data.last_updated || Date.now());
                    document.getElementById('last-updated').textContent = 'Updated ' + last.toLocaleTimeString();

                    // Trend Indicator
                    const trendEl = document.getElementById('trend-indicator');
                    const trend = data.trend || 'stable';
                    trendEl.textContent = trend.toUpperCase();
                    trendEl.className = trend === 'rising' ? 'trend-up' : (trend === 'dropping' ? 'trend-down' : '');

                    // Countries
                    const countriesRow = document.getElementById('countries-row');
                    countriesRow.innerHTML = '';
                    const countries = data.countries || [];
                    if (countries.length === 0) {
                        countriesRow.innerHTML = '<div class="col-12 text-muted">No country data yet</div>';
                    } else {
                        countries.slice(0, 8).forEach(c => {
                            const html = `
                                <div class="col-md-3 col-sm-6 col-6 mb-3">
                                    <div class="d-flex align-items-center">
                                        <span class="country-flag me-2">🌍</span>
                                        <div>
                                            <div class="fw-bold">${c.country}</div>
                                            <small class="text-muted">${c.viewers} viewers (${c.percentage}%)</small>
                                        </div>
                                    </div>
                                </div>`;
                            countriesRow.innerHTML += html;
                        });
                    }

                    // Channel Cards
                    const container = document.getElementById('channel-cards');
                    container.innerHTML = '';

                    Object.keys(data.channels || {}).forEach(cid => {
                        const ch = data.channels[cid];
                        const viewers = ch.live_viewers || 0;
                        const watchHours = ch.total_watch_hours || 0;

                        const html = `
                            <div class="col-lg-4 col-md-6 mb-4">
                                <div class="card-custom p-4 channel-card">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div>
                                            <h5 class="mb-1">${ch.display_name || cid.toUpperCase()}</h5>
                                            <small class="text-muted">${cid}</small>
                                        </div>
                                        <span class="badge bg-success fs-5 live-dot px-3">
                                            <i class="bi bi-circle-fill"></i> LIVE
                                        </span>
                                    </div>
                                    <div class="mt-4 text-center">
                                        <h1 class="display-4 fw-bold text-white mb-0">${viewers}</h1>
                                        <small class="text-muted">Concurrent Viewers</small>
                                    </div>
                                    <div class="mt-3 pt-3 border-top border-secondary text-center">
                                        <small class="text-success">
                                            <i class="bi bi-clock-history"></i> ${watchHours.toFixed(1)} hours watched
                                        </small>
                                    </div>
                                </div>
                            </div>`;
                        container.innerHTML += html;
                    });

                    // Timeline Chart
                    if (data.timeline && data.timeline_data) {
                        if (!timelineChart) {
                            timelineChart = new Chart(document.getElementById('timelineChart'), {
                                type: 'line',
                                data: {
                                    labels: data.timeline,
                                    datasets: [{
                                        label: 'Concurrent Viewers',
                                        data: data.timeline_data,
                                        borderColor: '#22d3ee',
                                        backgroundColor: 'rgba(34, 211, 238, 0.15)',
                                        tension: 0.4,
                                        borderWidth: 3,
                                        pointRadius: 2
                                    }]
                                },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    plugins: { legend: { display: false } },
                                    scales: {
                                        y: { 
                                            beginAtZero: true, 
                                            grid: { color: '#334155' },
                                            ticks: { color: '#94a3b8' }
                                        },
                                        x: { 
                                            grid: { color: '#334155' },
                                            ticks: { color: '#94a3b8' }
                                        }
                                    }
                                }
                            });
                        } else {
                            timelineChart.data.labels = data.timeline;
                            timelineChart.data.datasets[0].data = data.timeline_data;
                            timelineChart.update();
                        }
                    }
                })
                .catch(err => console.error("Analytics fetch error:", err));
        }

        // Auto refresh
        setInterval(updateDashboard, 5000);
        window.onload = updateDashboard;
    </script>
</body>
</html>
"""

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
