import requests
import json
import os
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

def load_channels():
    print(f"DEBUG: Looking for channels.json at {CHANNELS_FILE}")  # For debugging
    if not os.path.exists(CHANNELS_FILE):
        print("DEBUG: channels.json not found!")
        return {}
    try:
        with open(CHANNELS_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                print("DEBUG: channels.json is empty!")
                return {}
            data = json.loads(content)
            print(f"DEBUG: Loaded {len(data)} channels")
            return data
    except Exception as e:
        print(f"DEBUG: Error loading channels.json: {e}")
        return {}

def generate_report():
    channels = load_channels()
    report = []
    for cid, info in channels.items():
        try:
            r = requests.get(f"http://127.0.0.1:5000/channel/{cid}/master.m3u8", 
                           timeout=3, headers={'User-Agent': 'Monitor'})
            status = "ONLINE" if r.status_code == 200 else "OFFLINE"
        except:
            status = "OFFLINE"
        
        report.append({
            "id": cid,
            "name": info.get("name", cid),
            "status": status,
            "clip_count": len(info.get("programs", [])),
            "viewers": 0
        })
    return report

@app.route("/api/stats")
def api_stats():
    return jsonify(generate_report())

@app.route("/")
def dashboard():
    report = generate_report()
    return render_template_string(HTML_TEMPLATE, report=report)

# Your HTML_TEMPLATE stays the same (you can keep it)
HTML_TEMPLATE = """ ... your existing HTML ... """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
