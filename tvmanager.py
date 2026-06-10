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
    except Exception:
        return {}

def save_channels(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        temp_file = CHANNELS_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, CHANNELS_FILE)
    except Exception:
        pass

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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa TV Pro</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        .navbar { background-color: #1a1a1a !important; }
        .btn-monitor { background-color: #17a2b8; color: white !important; font-weight: bold; }
        .badge-playing { background-color: #28a745; animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
    <script>
        function checkPin(actionUrl, correctPin) {
            let userPin = prompt("Enter 6-digit Management PIN:");
            if (userPin === correctPin) window.location.href = actionUrl;
            else if (userPin !== null) alert("Incorrect PIN!");
        }
        function checkGlobalSync() {
            let userPin = prompt("Enter MASTER PIN for Global Sync:");
            if (userPin !== null) window.location.href = "/sync?auth=" + userPin;
        }
        function logout() {
            if(confirm("Logout?")) window.location.href = "/logout";
        }
    </script>
</head>
<body class="container mt-4">
    <nav class="navbar navbar-dark mb-4 p-3 shadow-sm rounded">
        <a class="navbar-brand" href="/">📺 IndieMa TV Pro</a>
        <div>
            <a href="/monitor" target="_blank" class="btn btn-monitor btn-sm mr-2">📊 MONITOR STATUS</a>
            <button onclick="checkGlobalSync()" class="btn btn-warning btn-sm">⚡ SYNC ALL</button>
            <button onclick="logout()" class="btn btn-outline-danger btn-sm">Logout</button>
        </div>
    </nav>

    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for msg in messages %}<div class="alert alert-info">{{ msg }}</div>{% endfor %}
      {% endif %}
    {% endwith %}

    {% if page == 'index' %}
        <div class="row mb-3">
            <div class="col"><h2>Channel Dashboard</h2></div>
            <div class="col text-right">
                <a href="/add" class="btn btn-success">➕ New Channel</a>
            </div>
        </div>
        <div class="row">
            {% for cid, info in channels.items() %}
            <div class="col-md-6 col-lg-4 mb-4">
                <div class="card h-100 shadow-sm">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <img src="{{ info.icon or 'https://via.placeholder.com/50' }}" width="50" class="rounded me-3">
                            <div>
                                <h5 class="card-title mb-0">{{ info.name }}</h5>
                                <small class="text-muted"><code>{{ cid }}</code></small>
                            </div>
                        </div>
                        {% set active_sch = False %}
                        {% for sch in info.get('schedules', []) %}
                            {% if sch.status == 'playing' %}
                                <span class="badge badge-playing">LIVE: {{ sch.name }}</span>
                                {% set active_sch = True %}
                            {% endif %}
                        {% endfor %}
                        {% if not active_sch %}
                            <span class="badge bg-secondary">Mode: Generic Rotation</span>
                        {% endif %}
                        <hr>
                        <button onclick="checkPin('/edit/{{ cid }}', '{{ info.pin }}')" class="btn btn-primary w-100 mb-2">Manage Playlists & Schedules</button>
                        <button onclick="checkPin('/sync_channel/{{ cid }}', '{{ info.pin }}')" class="btn btn-warning w-100">🔄 Force Sync</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>

    {% elif page == 'add' %}
        <div class="card shadow-sm p-4">
            <h3>Create New Channel</h3>
            <form method="POST">
                <input name="cid" placeholder="Channel ID (e.g. news-tv)" class="form-control mb-2" required>
                <input name="name" placeholder="Channel Name" class="form-control mb-2" required>
                <input name="icon" placeholder="Icon URL (Optional)" class="form-control mb-2">
                <input name="pin" placeholder="Management PIN (6 digits)" class="form-control mb-2" pattern="[0-9]{6}" required>
                <button class="btn btn-success btn-block mt-3">Create Channel</button>
                <a href="/" class="btn btn-link btn-block">Back to Dashboard</a>
            </form>
        </div>

    {% elif page == 'edit' %}
        <div class="card shadow-sm p-4">
            <h3>Control: {{ info.name }}</h3>
            <form method="POST">
                <div class="row">
                    <div class="col-md-7 mb-3">
                        <label class="fw-bold">Generic Playlist (Default Rotation)</label>
                        <textarea name="generic_list" class="form-control" rows="10">{% for p in info.programs %}{{ p.title }} | {{ p.url }} | {{ p.category }}
{% endfor %}</textarea>
                    </div>
                    <div class="col-md-5 mb-3">
                        <label class="fw-bold">Add New Schedule</label>
                        <div class="p-3 border rounded bg-light">
                            <input type="text" name="sch_name" class="form-control mb-2" placeholder="Schedule Name">
                            <textarea name="sch_list" class="form-control mb-2" rows="4" placeholder="Title | URL | Category"></textarea>
                            <input type="datetime-local" name="sch_start" class="form-control mb-2">
                            <select name="sch_mode" class="form-select">
                                <option value="once">Play Once</option>
                                <option value="rotate">Rotate</option>
                            </select>
                        </div>
                    </div>
                </div>
                <button type="submit" class="btn btn-success btn-block">Save & Update Engine</button>
                <a href="/" class="btn btn-link btn-block">Cancel</a>
            </form>

            <h5 class="mt-4">Active Schedules</h5>
            <table class="table table-sm">
                <thead><tr><th>Name</th><th>Start Time</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                    {% for idx in range(info.get('schedules', [])|length) %}
                    {% set sch = info.schedules[idx] %}
                    <tr>
                        <td>{{ sch.name }}</td>
                        <td>{{ sch.start_time or 'N/A' }}</td>
                        <td>{{ sch.status }}</td>
                        <td><a href="/del_schedule/{{ cid }}/{{ idx }}" class="btn btn-outline-danger btn-sm">Delete</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    {% endif %}
</body>
</html>
"""

# ====================== LOGIN PROTECTION ======================
@app.before_request
def require_login():
    allowed_endpoints = ['login', 'logout', 'monitor', 'monitor_internal', 'static', 'health']
    if request.endpoint in allowed_endpoints or request.path.startswith('/static') or request.path == '/health':
        return
    if not session.get('logged_in'):
        return redirect("/login")

# ====================== MONITOR / HEALTH ======================
@app.route("/health")
def health():
    return {"status": "healthy"}, 200

@app.route("/monitor")
def monitor():
    return redirect("/monitor_internal", code=302)

@app.route("/monitor_internal")
def monitor_internal():
    return """
    <div style="padding:40px; font-family:Arial; text-align:center; background:#0f172a; color:white; min-height:100vh;">
        <h2>📊 IndieMa Monitor</h2>
        <p><a href="/" class="btn btn-light">← Back to Dashboard</a></p>
        <hr>
        <p><strong>Monitor page is under development.</strong></p>
        <p>You can check the HLS Engine directly here:</p>
        <a href="http://127.0.0.1:5000" target="_blank" class="btn btn-info">Open HLS Engine (Port 5000)</a>
    </div>
    """

# ====================== ROUTES ======================
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
            requests.get(f"http://127.0.0.1:5000/reload?cid={cid}", timeout=5)
            flash("Settings saved & Engine synced!")
        except requests.exceptions.RequestException:
            flash("Settings saved. Engine connection timed out.")
        return redirect(url_for('edit_channel', cid=cid))

    return render_template_string(HTML_TEMPLATE, page='edit', cid=cid, info=channels[cid])

@app.route("/sync")
def sync():
    auth = request.args.get("auth")
    channels = load_channels()
    valid_pins = [c.get("pin") for c in channels.values() if c.get("pin")]
    if auth not in valid_pins:
        flash("Invalid PIN!")
        return redirect("/")
    try:
        requests.get("http://127.0.0.1:5000/reload", timeout=10)
        flash("All channels synced successfully!")
    except requests.exceptions.RequestException:
        flash("Sync timed out. Engine engine might be offline.")
    return redirect("/")

@app.route("/sync_channel/<cid>")
def sync_channel(cid):
    try:
        requests.get(f"http://127.0.0.1:5000/reload?cid={cid}", timeout=5)
        flash(f"Sync triggered for {cid}")
    except requests.exceptions.RequestException:
        flash("Sync failed. Check engine availability.")
    return redirect("/")

@app.route("/del_schedule/<cid>/<int:idx>")
def del_schedule(cid, idx):
    channels = load_channels()
    if cid in channels and len(channels[cid].get("schedules", [])) > idx:
        channels[cid]["schedules"].pop(idx)
        save_channels(channels)
        flash("Schedule deleted.")
    return redirect(url_for('edit_channel', cid=cid))

# ====================== FORCE BIND TO 5001 ======================
if __name__ == "__main__":
    # This hard-forces the app execution context onto Port 5001
    app.run(host="0.0.0.0", port=5001)
