import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# === CONFIGURATIONS ===
DATA_DIR = os.getenv("DATA_DIR", "/data")
ANALYTICS_FILE = os.path.join(DATA_DIR, "monitor_analytics.json")

# In-memory real-time state cache
LIVE_CONNECTIONS = {}

# Mock generator helper for visualization if live data stream hasn't filled yet
def get_analytics_data(filter_range="today"):
    # Real implementation would query SQL/NoSQL database matching timestamps
    return {
        "summary": {
            "total_watch_time_hours": 1420 if filter_range == "today" else 9840,
            "avg_watch_time_mins": 24.5,
            "peak_concurrent": 340
        },
        "countries": [
            {"country": "Singapore", "city": "Singapore", "viewers": 120, "percentage": 40},
            {"country": "India", "city": "Chennai", "viewers": 90, "percentage": 30},
            {"country": "United States", "city": "New York", "viewers": 60, "percentage": 20},
            {"country": "Malaysia", "city": "Kuala Lumpur", "viewers": 30, "percentage": 10}
        ],
        "timeline": ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"],
        "timeline_data": [50, 45, 110, 290, 340, 210]
    }

MONITOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IndieMa TV - Live Advanced Analytics</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <style>
        body { background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }
        .card-custom { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .status-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
        .status-online { background-color: #10b981; box-shadow: 0 0 8px #10b981; }
        .status-offline { background-color: #ef4444; }
        .filter-btn.active { background-color: #3b82f6 !important; color: white; border-color: #3b82f6; }
        .text-accent { color: #3b82f6; }
    </style>
</head>
<body>
    <div class="container-fluid py-4 px-4">
        <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
            <div>
                <h2 class="fw-bold m-0 text-white"><i class="bi bi-speedometer2 me-2 text-accent"></i>IndieMa TV Monitor</h2>
                <small class="text-muted">Real-time Node Architecture & Viewer Data Stream</small>
            </div>
            <div>
                <a href="http://fast.infopluto.com" class="btn btn-outline-light btn-sm"><i class="bi bi-arrow-left me-1"></i> Back to Dashboard</a>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="card-custom p-3 d-flex flex-wrap gap-2 align-items-center">
                    <span class="text-muted small fw-bold text-uppercase me-2"><i class="bi bi-funnel me-1"></i> Historical Filters:</span>
                    <a href="?range=1h" class="btn btn-sm btn-dark filter-btn {% if selected_range == '1h' %}active{% endif %}">Last 1 Hour</a>
                    <a href="?range=today" class="btn btn-sm btn-dark filter-btn {% if selected_range == 'today' %}active{% endif %}">Full Day (Today)</a>
                    <a href="?range=7d" class="btn btn-sm btn-dark filter-btn {% if selected_range == '7d' %}active{% endif %}">Last 7 Days</a>
                    <a href="?range=15d" class="btn btn-sm btn-dark filter-btn {% if selected_range == '15d' %}active{% endif %}">Last 15 Days</a>
                    <a href="?range=30d" class="btn btn-sm btn-dark filter-btn {% if selected_range == '30d' %}active{% endif %}">Last 30 Days</a>
                    <a href="?range=3m" class="btn btn-sm btn-dark filter-btn {% if selected_range == '3m' %}active{% endif %}">Last 3 Months</a>
                    <a href="?range=6m" class="btn btn-sm btn-dark filter-btn {% if selected_range == '6m' %}active{% endif %}">Last 6 Months</a>
                    <a href="?range=1y" class="btn btn-sm btn-dark filter-btn {% if selected_range == '1y' %}active{% endif %}">Last 1 Year</a>
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card-custom p-4 text-center">
                    <span class="text-muted d-block uppercase small fw-bold">Accumulated Watch Time</span>
                    <h1 class="display-5 fw-bold text-white my-2">{{ report.summary.total_watch_time_hours }} <small class="fs-4 text-muted">Hrs</small></h1>
                    <span class="text-success small"><i class="bi bi-graph-up-arrow"></i> Active Consumption</span>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card-custom p-4 text-center">
                    <span class="text-muted d-block uppercase small fw-bold">Avg Session Duration</span>
                    <h1 class="display-5 fw-bold text-white my-2">{{ report.summary.avg_watch_time_mins }} <small class="fs-4 text-muted">Mins</small></h1>
                    <span class="text-muted small">Per connected dynamic user context</span>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card-custom p-4 text-center">
                    <span class="text-muted d-block uppercase small fw-bold">Peak Viewership Matrix</span>
                    <h1 class="display-5 fw-bold text-accent my-2">{{ report.summary.peak_concurrent }}</h1>
                    <span class="text-muted small">Simultaneous concurrent streaming limits</span>
                </div>
            </div>
        </div>

        <h4 class="mb-3 text-white fw-semibold">Live Channel Matrix Matrix</h4>
        <div class="row mb-4">
            <div class="col-lg-4 col-md-6 mb-3">
                <div class="card-custom p-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <h5 class="m-0 fw-bold text-white">astropluto</h5>
                        </div>
                        <span class="badge bg-dark d-flex align-items-center gap-1">
                            <span class="status-dot status-online"></span> ONLINE
                        </span>
                    </div>
                    <div class="row text-center g-2 bg-black bg-opacity-25 rounded p-2">
                        <div class="col-6 border-end border-secondary">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">Live Viewers</small>
                            <span class="fs-4 fw-bold text-white">142</span>
                        </div>
                        <div class="col-6">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">1H Watchtime</small>
                            <span class="fs-4 fw-bold text-white">38.4 Hr</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4 col-md-6 mb-3">
                <div class="card-custom p-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <h5 class="m-0 fw-bold text-white">saathvigam</h5>
                        </div>
                        <span class="badge bg-dark d-flex align-items-center gap-1">
                            <span class="status-dot status-online"></span> ONLINE
                        </span>
                    </div>
                    <div class="row text-center g-2 bg-black bg-opacity-25 rounded p-2">
                        <div class="col-6 border-end border-secondary">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">Live Viewers</small>
                            <span class="fs-4 fw-bold text-white">98</span>
                        </div>
                        <div class="col-6">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">1H Watchtime</small>
                            <span class="fs-4 fw-bold text-white">22.1 Hr</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-4 col-md-6 mb-3">
                <div class="card-custom p-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="d-flex align-items-center gap-2">
                            <h5 class="m-0 fw-bold text-white">indiematv</h5>
                        </div>
                        <span class="badge bg-dark d-flex align-items-center gap-1">
                            <span class="status-dot status-online"></span> ONLINE
                        </span>
                    </div>
                    <div class="row text-center g-2 bg-black bg-opacity-25 rounded p-2">
                        <div class="col-6 border-end border-secondary">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">Live Viewers</small>
                            <span class="fs-4 fw-bold text-white">60</span>
                        </div>
                        <div class="col-6">
                            <small class="text-muted d-block text-uppercase" style="font-size:0.75rem;">1H Watchtime</small>
                            <span class="fs-4 fw-bold text-white">14.5 Hr</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-5 mb-4">
                <div class="card-custom p-4 h-100">
                    <h5 class="fw-bold mb-3 text-white"><i class="bi bi-geo-alt me-2 text-danger"></i>Geographic Distribution (City/Country)</h5>
                    <div class="table-responsive">
                        <table class="table table-dark table-hover m-0 align-middle">
                            <thead>
                                <tr class="text-muted border-secondary small">
                                    <th>COUNTRY</th>
                                    <th>PRIMARY CITY</th>
                                    <th class="text-end">LIVE CONCURRENT</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for item in report.countries %}
                                <tr class="border-secondary">
                                    <td class="fw-semibold text-white"><i class="bi bi-globe me-2 text-muted"></i>{{ item.country }}</td>
                                    <td class="text-muted">{{ item.city }}</td>
                                    <td class="text-end fw-bold text-accent">{{ item.viewers }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-7 mb-4">
                <div class="card-custom p-4 h-100 d-flex flex-column justify-content-between">
                    <div>
                        <h5 class="fw-bold mb-1 text-white"><i class="bi bi-activity me-2 text-success"></i>Audience Density Distribution Curve</h5>
                        <p class="text-muted small">Timeline trend analysis across the selected evaluation range</p>
                    </div>
                    <div class="bg-black bg-opacity-50 border border-secondary rounded p-3 text-center d-flex align-items-center justify-content-center" style="height: 220px;">
                        <span class="text-muted small"><i class="bi bi-bar-chart-line me-1"></i> [Chart Component Workspace - Processing Stream Metrics: {{ report.timeline_data }}]</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/monitor")
@app.route("/")
def monitor_dashboard():
    selected_range = request.args.get("range", "today")
    report_data = get_analytics_data(selected_range)
    return render_template_string(MONITOR_HTML, selected_range=selected_range, report=report_data)

# API endpoint for player tracking hooks to feed telemetry data down the pipeline
@app.route("/api/ping", methods=["POST"])
def client_ping():
    # Payload elements parsing: user_ip, channel_id, view_duration_seconds
    return {"status": "recorded"}, 200

if __name__ == "__main__":
    # Binding cleanly onto port 5020 to separate completely from the core engine layers
    app.run(host="0.0.0.0", port=5020, debug=False)
