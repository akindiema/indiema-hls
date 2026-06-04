import os
import json
import re
import requests
import subprocess
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "indiema_secret_key"

# === DOCKER COMPATIBLE PATH ===
DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

def load_channels():
    if not os.path.exists(CHANNELS_FILE): return {}
    try:
        with open(CHANNELS_FILE, "r") as f: 
            content = f.read().strip()
            if not content: return {}
            return json.loads(content)
    except Exception:
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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IndieMa TV Manager</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css">
    <style>
        .navbar { background-color: #1a1a1a !important; }
        .btn-monitor { background-color: #17a2b8; color: white !important; font-weight: bold; }
    </style>
</head>
<body class="container mt-4">
    <nav class="navbar navbar-dark mb-4 p-3 shadow-sm rounded">
        <a class="navbar-brand" href="/">📺 IndieMa TV Manager</a>
        <div>
            <a href="https://tv.infopluto.com/monitor" target="_blank" class="btn btn-monitor btn-sm mr-2">📊 MONITOR STATUS</a>
            <a href="/sync?auth=999999" class="btn btn-outline-warning btn-sm">⚡ FORCE SYNC ALL</a>
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
        <table class="table table-hover border">
            <thead class="thead-light">
                <tr><th>Icon</th><th>ID</th><th>Name</th><th>Progs</th><th>Actions</th></tr>
            </thead>
            <tbody>
                {% for cid, info in channels.items() %}
                <tr>
                    <td><img src="{{ info.icon }}" width="40" class="rounded"></td>
                    <td><code>{{ cid }}</code></td>
                    <td><strong>{{ info.name }}</strong></td>
                    <td>{{ info.programs|length }}</td>
                    <td>
                        <a href="/edit/{{ cid }}" class="btn btn-sm btn-primary">Edit</a>
                        <a href="/sync_channel/{{ cid }}" class="btn btn-sm btn-warning">Sync</a>
                        <a href="https://tv.infopluto.com/channel/{{ cid }}/master.m3u8" target="_blank" class="btn btn-sm btn-dark">Preview</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

    {% elif page == 'add' %}
        <div class="card shadow-sm p-4">
            <h3>Create New Channel</h3>
            <form method="POST">
                <input name="cid" placeholder="Channel ID (e.g. news-tv)" class="form-control mb-2" required>
                <input name="name" placeholder="Channel Name" class="form-control mb-2" required>
                <input name="icon" placeholder="Icon URL" class="form-control mb-2">
                <button class="btn btn-success btn-block mt-2">Create Now</button>
                <a href="/" class="btn btn-link btn-block">Back to Dashboard</a>
            </form>
        </div>

    {% elif page == 'edit' %}
        <div class="card shadow-sm p-4">
            <h3>Editing: {{ info.name }}</h3>
            <form method="POST">
                <div class="mb-3">
                    <label>Channel Name</label>
                    <input name="name" class="form-control" value="{{ info.name }}">
                </div>
                <div class="mb-3">
                    <label>Icon URL</label>
                    <input name="icon" class="form-control" value="{{ info.icon }}">
                </div>
                <div class="mb-3">
                    <label>Programs (Title | URL | Category)</label>
                    <textarea name="generic_list" class="form-control" rows="12">{% for p in info.programs %}{{ p.title }} | {{ p.url }} | {{ p.category }}&#10;{% endfor %}</textarea>
                </div>
                <button class="btn btn-primary btn-block">Save and Update Engine</button>
                <a href="/" class="btn btn-link btn-block">Cancel</a>
            </form>
        </div>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, page='index', channels=load_channels())

@app.route("/add", methods=["GET", "POST"])
def add_channel():
    if request.method == "POST":
        cid = re.sub(r'[^a-z0-9-]', '', request.form.get("cid").lower())
        channels = load_channels()
        channels[cid] = {"name": request.form.get("name"), "icon": request.form.get("icon", ""), "programs": [], "schedules": []}
        save_channels(channels)
        return redirect("/")
    return render_template_string(HTML_TEMPLATE, page='add')

@app.route("/edit/<cid>", methods=["GET", "POST"])
def edit_channel(cid):
    channels = load_channels()
    if cid not in channels: return "Not Found", 404
    if request.method == "POST":
        channels[cid]["name"] = request.form.get("name")
        channels[cid]["icon"] = request.form.get("icon")
        channels[cid]["programs"] = parse_playlist(request.form.get("generic_list", ""))
        save_channels(channels)
        try:
            # Increased timeout to 20s to account for large playlist mapping
            requests.get(f"http://127.0.0.1:5000/reload?cid={cid}", timeout=20)
            flash("Settings updated & Engine Synced!")
        except:
            time.sleep(2) # Safety delay before force-restart
            subprocess.run(["sudo", "systemctl", "restart", "hls-engine"])
            flash("Playlist saved. Engine restarting in background.")
        return redirect("/")
    return render_template_string(HTML_TEMPLATE, page='edit', cid=cid, info=channels[cid])

@app.route("/sync")
def sync():
    try:
        # Increased timeout to 30s for full engine reload
        requests.get("http://127.0.0.1:5000/reload", timeout=30)
        flash("All Channels Synced!")
    except:
        time.sleep(2) # Safety delay
        subprocess.run(["sudo", "systemctl", "restart", "hls-engine"])
        flash("Syncing initiated via background restart.")
    return redirect("/")

@app.route("/sync_channel/<cid>")
def sync_channel(cid):
    try:
        requests.get(f"http://127.0.0.1:5000/reload?cid={cid}", timeout=20)
        flash(f"Synced {cid} successfully.")
    except:
        time.sleep(2) # Safety delay
        subprocess.run(["sudo", "systemctl", "restart", "hls-engine"])
        flash(f"Syncing {cid} via background restart.")
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
