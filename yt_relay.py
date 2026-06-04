from flask import Flask, render_template_string, request, redirect
import subprocess, threading, time

app = Flask(__name__)
relays = {}

def ffmpeg_worker(c_id):
    while c_id in relays and relays[c_id]['active']:
        r = relays[c_id]
        cmd = ["ffmpeg", "-re", "-i", r['src'], "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ab", "128k", "-f", "flv", f"rtmp://a.rtmp.youtube.com/live2/{r['key']}"]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        relays[c_id]['proc'] = p
        p.wait()
        if relays[c_id].get('active'): time.sleep(5)

@app.route('/')
def index():
    return render_template_string('''
    <body style="background:#121212;color:#eee;font-family:sans-serif;padding:40px;">
        <h2>Master YouTube Relay</h2>
        <form action="/add" method="post" style="background:#1e1e1e;padding:20px;border-radius:10px;border:1px solid #333;">
            <input name="name" placeholder="Channel Name" required>
            <input name="src" placeholder="HLS URL (http://...)" style="width:300px;" required>
            <input name="key" type="password" placeholder="YT Stream Key" required>
            <button type="submit">Add Channel</button>
        </form>
        <table style="width:100%;margin-top:20px;border-collapse:collapse;background:#1e1e1e;">
            <tr style="background:#252525;text-align:left;">
                <th style="padding:10px;">Channel</th><th style="padding:10px;">Status</th><th style="padding:10px;">Action</th>
            </tr>
            {% for id, r in relays.items() %}
            <tr style="border-bottom:1px solid #333;">
                <td style="padding:10px;">{{r.name}}<br><small style="color:#666;">{{r.src}}</small></td>
                <td style="padding:10px;color:{{ 'green' if r.active else 'red' }};">{{ 'LIVE' if r.active else 'OFFLINE' }}</td>
                <td style="padding:10px;">
                    <a href="/{{ 'stop' if r.active else 'start' }}/{{id}}">
                        <button style="padding:5px 15px;">{{ 'STOP' if r.active else 'START' }}</button>
                    </a>
                    <a href="/delete/{{id}}" style="color:#555;margin-left:10px;text-decoration:none;">Delete</a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    ''', relays=relays)

@app.route('/add', methods=['POST'])
def add():
    c_id = str(int(time.time()))
    relays[c_id] = {'name':request.form['name'],'src':request.form['src'],'key':request.form['key'],'proc':None,'active':False}
    return redirect('/')

@app.route('/<action>/<c_id>')
def control(action, c_id):
    if c_id in relays:
        if action == 'start':
            relays[c_id]['active'] = True
            threading.Thread(target=ffmpeg_worker, args=(c_id,), daemon=True).start()
        elif action == 'stop':
            relays[c_id]['active'] = False
            if relays[c_id]['proc']: relays[c_id]['proc'].terminate()
        elif action == 'delete':
            relays[c_id]['active'] = False
            if relays[c_id]['proc']: relays[c_id]['proc'].terminate()
            del relays[c_id]
    return redirect('/')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010)
