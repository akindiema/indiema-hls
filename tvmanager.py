import os
import json
import re
import requests
from flask import Flask, render_template_string, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = "indiema_secret_key"

# === MASTER PASSWORD ===
MASTER_PASSWORD = "MasterMind@1986"

# === DOCKER COMPATIBLE ===
DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return {}
    try:
        with open(CHANNELS_FILE, "r") as f:
            content = f.read().strip()
            if not content: return {}
            return json.loads(content)
    except:
        return {}

def save_channels(data):
    temp_file = CHANNELS_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(data, f, indent=4)
    os.replace(temp_file, CHANNELS_FILE)

def parse_playlist(raw_text):
    progs = []
    if not raw_text: return progs
    for line in raw_text.splitlines():
        line = line.strip()
        if '|' in line:
            parts = [i.strip() for i in line.split('|')]
            if len(parts) >= 2:
                progs.append({
                    "title": parts[0],
                    "url": parts[1],
                    "category": parts[2] if len(parts) > 2 else "General"
                })
    return progs

# ====================== TEMPLATES ======================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa TV Pro - Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>body { background: #1a1a1a; color: white; } .login-box { max-width: 420px; margin: 120px auto; }</style>
</head>
<body>
    <div class="container">
        <div class="login-box card p-5 shadow">
            <h3 class="text-center mb-4">🔐 IndieMa TV Pro</h3>
            <form method="POST">
                <input type="password" name="password" class="form-control mb-3" placeholder="Enter Master Password" required autofocus>
                <button type="submit" class="btn btn-primary w-100">Login</button>
            </form>
            {% if error %}<div class="alert alert-danger mt-3">{{ error }}</div>{% endif %}
        </div>
    </div>
</body>
</html>
"""

# ====================== MONITOR HTML TEMPLATE ======================
MONITOR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa Analytics</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <meta http-equiv="refresh" content="30">
    <style>
        body { background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; border: none; }
        .navbar { background-color: #1a1a1a !important; }
    </style>
</head>
<body class="p-4">
    <nav class="navbar navbar-dark mb-4 p-3 rounded">
        <a class="navbar-brand" href="/">← Back to Dashboard</a>
        <h3 class="text-center text-light m-0">📊 IndieMa Analytics</h3>
    </nav>

    <div class="container">
        <div class="row">
            {% for channel in stats %}
            <div class="col-lg-6 col-xl-4 mb-4">
                <div class="card p-4 h-100">
                    <h4>{{ channel.name }}</h4>
                    <span class="badge {{ 'bg-success' if channel.status == 'ONLINE' else 'bg-danger' }}">
                        ● {{ channel.status }}
                    </span>

                    <div class="row text-center my-4">
                        <div class="col-6">
                            <small>Live Viewers</small><br>
                            <h2 class="text-info">{{ channel.viewers }}</h2>
                        </div>
                        <div class="col-6">
                            <small>Clips</small><br>
                            <h2>{{ channel.clip_count }}</h2>
                        </div>
                    </div>
                    <canvas id="chart-{{ channel.id }}" height="180"></canvas>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
    document.querySelectorAll('canvas').forEach(canvas => {
        const channelId = canvas.id.replace('chart-', '');
        fetch(`/api/analytics?channel=${channelId}&days=30`)
            .then(r => r.json())
            .then(data => {
                new Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: data.map(item => item.time.substring(11,16)),
                        datasets: [{
                            label: 'Viewers',
                            data: data.map(item => item.viewers),
                            borderColor: '#60a5fa',
                            tension: 0.4,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: { y: { beginAtZero: true } }
                    }
                });
            });
    });
    </script>
</body>
</html>
"""

# ====================== LOGIN PROTECTION ======================
@app.before_request
def require_login():
    if request.endpoint in ['login', 'logout', 'monitor', 'monitor_internal', 'static', 'api_stats', 'api_analytics'] or request.path.startswith('/static'):
        return
    if not session.get('logged_in'):
        return redirect("/login")

# ====================== MONITOR ROUTES ======================
@app.route("/monitor")
def monitor():
    return redirect("/monitor_internal", code=302)

@app.route("/monitor_internal")
def monitor_internal():
    try:
        stats = requests.get("http://127.0.0.1:5001/api/stats", timeout=5).json()
    except:
        stats = []
    return render_template_string(MONITOR_TEMPLATE, stats=stats)

# ====================== API ROUTES (from your monitor.py) ======================
@app.route("/api/stats")
def api_stats():
    try:
        return requests.get("http://127.0.0.1:5001/api/stats", timeout=5).content
    except:
        return json.dumps([])

@app.route("/api/analytics")
def api_analytics():
    try:
        return requests.get(f"http://127.0.0.1:5001/api/analytics?{request.query_string.decode()}", timeout=5).content
    except:
        return json.dumps([])

# ====================== OTHER ROUTES ======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == MASTER_PASSWORD:
            session['logged_in'] = True
            return redirect("/")
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Incorrect Password!")
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, page='index', channels=load_channels())

# ... [Keep your /add, /edit, /sync, /sync_channel, /del_schedule routes as they are]

@app.route("/add", methods=["GET", "POST"])
def add_channel():
    if request.method == "POST":
        cid = re.sub(r'[^a-z0-9-]', '', request.form.get("cid", "").lower())
        channels = load_channels()
        channels[cid] = {
            "name": request.form.get("name"),
            "icon": request.form.get("icon", ""),
            "pin": request.form.get("pin", "000000"),
            "programs": [],
            "schedules": []
        }
        save_channels(channels)
        flash(f"Channel {cid} created successfully!")
        return redirect("/")
    return render_template_string(HTML_TEMPLATE, page='add')

@app.route("/edit/<cid>", methods=["GET", "POST"])
def edit_channel(cid):
    channels = load_channels()
    if cid not in channels:
        return "Channel Not Found", 404

    if request.method == "POST":
        channels[cid]["programs"] = parse_playlist(request.form.get("generic_list", ""))
        sch_name = request.form.get("sch_name")
        sch_list = request.form.get("sch_list")
        if sch_name and sch_list:
            new_sch = {
                "name": sch_name,
                "programs": parse_playlist(sch_list),
                "start_time": request.form.get("sch_start"),
                "mode": request.form.get("sch_mode", "once"),
                "status": "scheduled"
            }
            if "schedules" not in channels[cid]:
                channels[cid]["schedules"] = []
            channels[cid]["schedules"].append(new_sch)

        save_channels(channels)
        try:
            requests.get(f"http://127.0.0.1:5000/reload?cid={cid}", timeout=15)
            flash("Settings saved & Engine synced!")
        except:
            flash("Settings saved. Engine restart may be needed.")
        return redirect(url_for('edit_channel', cid=cid))

    return render_template_string(HTML_TEMPLATE, page='edit', cid=cid, info=channels[cid])

# (Add your remaining routes: /sync, /sync_channel, /del_schedule if missing)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
