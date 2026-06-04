import os
import time
import json
import m3u8
import requests
import threading
import gc

gc.set_threshold(1000, 50, 50)

from datetime import datetime, timedelta
from urllib.parse import urljoin
from flask import Flask, Response, request
from collections import OrderedDict

# === DOCKER + BUNNY COMPATIBLE ===
DATA_DIR = os.getenv("DATA_DIR", "/data")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")

# Global Locks
JSON_LOCK = threading.Lock()
SEGMENT_CACHE_LOCK = threading.Lock()

http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=200, pool_maxsize=500)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

app = Flask(__name__)

active_engines = {}
URL_MAP = {}
SEGMENT_CACHE = OrderedDict()
MAX_CACHE_SEGMENTS = 400

def get_closest_variant(playlists, target_bw):
    return min(playlists, key=lambda p: abs(p.stream_info.bandwidth - target_bw))

def get_scte35():
    return "/DA0AAAAAAAAAAAABQb+AAAAAABfAhpDVUVJAAAAAH+fCAgAAAAAALN4buYBAAAh749W"

def load_and_prepare_all(target_cid=None):
    global active_engines, URL_MAP
    if not os.path.exists(CHANNELS_FILE):
        print("ALERT: channels.json is missing.")
        return
        
    try:
        with JSON_LOCK:
            with open(CHANNELS_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return 
                data = json.loads(content)
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load channels.json: {e}")
        return 

    channels_to_process = {target_cid: data[target_cid]} if (target_cid and target_cid in data) else data

    for cid, info in channels_to_process.items():
        active_program_list = info.get("programs", [])
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M")
        
        schedules = info.get("schedules", [])
        for sch in schedules:
            if sch.get("start_time") and sch["start_time"] <= now_str:
                active_program_list = sch.get("programs", [])
                sch["status"] = "playing"
            else:
                sch["status"] = "scheduled"
        
        if not target_cid: 
            with JSON_LOCK:
                with open(CHANNELS_FILE, "w") as f:
                    json.dump(data, f, indent=4)

        if not active_program_list: continue

        try:
            master = None
            for _ in range(3):
                try:
                    master = m3u8.load(active_program_list[0]['url'].split('|')[0].strip())
                    if master: break
                except:
                    time.sleep(2)
            
            if not master:
                print(f"SKIP: Could not reach CDN for {cid} after 3 tries.")
                continue

            output_bws = sorted([p.stream_info.bandwidth for p in master.playlists], reverse=True)
            bw_to_info = {p.stream_info.bandwidth: p.stream_info for p in master.playlists}

            videos = []
            timeline = []
            total_dur = 0
            total_segs = 0
            timeline_time = 0

            for v_idx, entry in enumerate(active_program_list):
                url = entry.get('url', '').split('|')[0].strip()
                try:
                    vod = None
                    for _ in range(3):
                        try:
                            vod = m3u8.load(url)
                            if vod: break
                        except:
                            time.sleep(1)
                    
                    if not vod: continue

                    v_map = {}
                    for bw in output_bws:
                        closest = get_closest_variant(vod.playlists, bw)
                        v_url = urljoin(url, closest.uri)
                        media = m3u8.load(v_url)
                        for s_idx, s in enumerate(media.segments):
                            real_uri = urljoin(v_url, s.uri)
                            seg_id = f"{cid}_{v_idx}_{bw}_{s_idx}.ts"
                            
                            URL_MAP[seg_id] = real_uri
                            s.uri = f"segments/{seg_id}"
                        v_map[bw] = media

                    sample = next(iter(v_map.values()))
                    duration = sum(s.duration for s in sample.segments)
                    for seg in sample.segments:
                        timeline.append(timeline_time)
                        timeline_time += seg.duration

                    videos.append({
                        "v_map": v_map,
                        "duration": duration,
                        "seg_count": len(sample.segments),
                        "title": entry.get('title', 'Untitled'),
                        "category": entry.get('category', 'General'),
                        "original_url": url
                    })
                    total_dur += duration
                    total_segs += len(sample.segments)
                except Exception as inner_e:
                    print(f"Error loading URL {url}: {inner_e}")
                    continue

            active_engines[cid] = {
                "videos": videos,
                "display_name": info.get("name", cid.upper()),
                "icon": info.get("icon", "https://Indiema-images.b-cdn.net/indiema%20iconpng.png"),
                "timeline": timeline,
                "output_bws": output_bws,
                "bw_to_info": bw_to_info,
                "total_loop_duration": total_dur,
                "total_segments_per_loop": total_segs,
                "start_time": time.time()
            }
            print(f"SUCCESS: {'Reloaded' if target_cid else 'Started'} Channel '{cid}'")
        except Exception as e:
            print(f"Error processing channel {cid}: {e}")

@app.route("/channel/<cid>/master.m3u8")
def master(cid):
    engine = active_engines.get(cid)
    if not engine: return "Offline", 404
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-INDEPENDENT-SEGMENTS"]
    for b in engine["output_bws"]:
        s_info = engine["bw_to_info"][b]
        res = f"{s_info.resolution[0]}x{s_info.resolution[1]}" if s_info.resolution else "1280x720"
        lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={b},RESOLUTION={res}")
        lines.append(f"variant_{b}.m3u8")
    return Response("\n".join(lines) + "\n", mimetype="application/vnd.apple.mpegurl", headers={"Access-Control-Allow-Origin": "*"})

@app.route("/channel/<cid>/variant_<int:bw>.m3u8")
def variant(cid, bw):
    try:
        engine = active_engines.get(cid)
        if not engine: return "Offline", 404
        
        loop_dur = engine["total_loop_duration"]
        now_offset = time.time() - engine["start_time"]
        loop_count = int(now_offset // loop_dur)
        time_in_loop = now_offset % loop_dur

        timeline = engine["timeline"]
        found_idx = 0
        for i, start in enumerate(timeline):
            if start > time_in_loop: break
            found_idx = i

        abs_seq = loop_count * engine["total_segments_per_loop"]
        start_seq = max(0, abs_seq + found_idx - 4)
        cue = get_scte35()
        ad_break_duration = 32.0

        m_lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            "#EXT-X-TARGETDURATION:6",
            f"#EXT-X-MEDIA-SEQUENCE:{start_seq}",
            "#EXT-X-DISCONTINUITY-SEQUENCE:0",
            "#EXT-X-START:TIME-OFFSET=-12"
        ]

        elapsed_ad_time = 0.0
        is_in_ad_break = False

        for i in range(12):
            target_abs = start_seq + i
            l_idx = target_abs % engine["total_segments_per_loop"]
            
            curr_pos = 0
            for v_idx, v in enumerate(engine["videos"]):
                if curr_pos <= l_idx < curr_pos + v["seg_count"]:
                    seg_idx = l_idx - curr_pos
                    seg = v["v_map"][bw].segments[seg_idx]

                    if seg_idx == 0 and v_idx > 0 and not is_in_ad_break:
                        m_lines.append("#EXT-X-DISCONTINUITY")
                        m_lines.append(f"#EXT-OATCLS-SCTE35:{cue}")
                        m_lines.append(f"#EXT-X-CUE-OUT:{ad_break_duration}")
                        is_in_ad_break = True
                        elapsed_ad_time = 0.0

                    if is_in_ad_break:
                        m_lines.append(f"#EXT-X-CUE-OUT-CONT:ElapsedTime={elapsed_ad_time},Duration={ad_break_duration},SCTE35={cue}")

                    m_lines.append(f"#EXTINF:{seg.duration},")
                    m_lines.append(seg.uri)

                    if is_in_ad_break:
                        elapsed_ad_time += seg.duration
                        if elapsed_ad_time >= ad_break_duration:
                            m_lines.append("#EXT-X-CUE-IN")
                            is_in_ad_break = False
                    break
                curr_pos += v["seg_count"]

        return Response("\n".join(m_lines), mimetype="application/vnd.apple.mpegurl", 
                        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})
    except Exception as e:
        return str(e), 500

@app.route("/channel/<cid>/segments/<seg_id>")
@app.route("/segments/<seg_id>")
def handle_segment(seg_id, cid=None):
    real_url = URL_MAP.get(seg_id)
    if not real_url: return "Not Found", 404
    
    with SEGMENT_CACHE_LOCK:
        if seg_id in SEGMENT_CACHE:
            SEGMENT_CACHE.move_to_end(seg_id)
            return Response(SEGMENT_CACHE[seg_id], content_type="video/mp2t", 
                            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600"})
    
    try:
        req = http_session.get(real_url, timeout=(0.5, 1.5), stream=False)
        if req.status_code == 200:
            with SEGMENT_CACHE_LOCK:
                if seg_id not in SEGMENT_CACHE:
                    SEGMENT_CACHE[seg_id] = req.content
                    if len(SEGMENT_CACHE) > MAX_CACHE_SEGMENTS:
                        SEGMENT_CACHE.popitem(last=False)
            return Response(req.content, content_type="video/mp2t", headers={"Access-Control-Allow-Origin": "*"})
        return "Origin Error", 502
    except:
        return "Timeout", 504

@app.route("/epg.xml")
def generate_epg():
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']
    for cid, engine in active_engines.items():
        disp_name = engine.get("display_name", cid.upper())
        icon_url = engine.get("icon")
        xml.append(f'   <channel id="{cid}">')
        xml.append(f'     <display-name>{disp_name}</display-name>')
        xml.append(f'     <icon src="{icon_url}" />') 
        xml.append('   </channel>')

    for cid, engine in active_engines.items():
        loop_dur = engine["total_loop_duration"]
        if loop_dur <= 0: continue
        now = time.time()
        start_of_current_loop = engine["start_time"] + ((now - engine["start_time"]) // loop_dur) * loop_dur
        current_video_start = start_of_current_loop
        end_of_24h = now + 86400 

        while current_video_start < end_of_24h:
            for v in engine["videos"]:
                video_end = current_video_start + v["duration"]
                if video_end > now:
                    clean_title = v.get("title", "Untitled Program")
                    category = v.get("category", "General")
                    start_time_str = datetime.fromtimestamp(current_video_start).strftime('%Y%m%d%H%M%S +0530')
                    end_time_str = datetime.fromtimestamp(video_end).strftime('%Y%m%d%H%M%S +0530')
                    xml.append(f'   <programme start="{start_time_str}" stop="{end_time_str}" channel="{cid}">')
                    xml.append(f'     <title lang="en">{clean_title}</title>')
                    xml.append(f'     <category lang="en">{category}</category>')
                    xml.append(f'     <desc lang="en">Now streaming {clean_title} on {engine.get("display_name")}.</desc>')
                    xml.append('   </programme>')
                current_video_start = video_end
                if current_video_start >= end_of_24h: break

    xml.append('</tv>')
    return Response("\n".join(xml), mimetype="application/xml", headers={"Access-Control-Allow-Origin": "*"})

@app.route("/reload")
def reload_engine():
    try:
        global SEGMENT_CACHE, URL_MAP
        target_cid = request.args.get('cid')
        
        with SEGMENT_CACHE_LOCK:
            if target_cid:
                keys_to_remove = [k for k in URL_MAP.keys() if k.startswith(f"{target_cid}_")]
                for k in keys_to_remove:
                    URL_MAP.pop(k, None)
                    SEGMENT_CACHE.pop(k, None)
            else:
                URL_MAP.clear()
                SEGMENT_CACHE.clear()
        
        load_and_prepare_all(target_cid=target_cid)
        
        msg = f"Channel {target_cid} Reloaded" if target_cid else "All Engines Reloaded"
        return f"{msg} & Cache Cleaned Successfully", 200
    except Exception as e:
        return f"Reload Failed: {str(e)}", 500

def background_prefetcher():
    while True:
        try:
            for cid, engine in list(active_engines.items()):
                now_offset = time.time() - engine["start_time"]
                time_in_loop = now_offset % engine["total_loop_duration"]
                
                timeline = engine["timeline"]
                found_idx = 0
                for i, start in enumerate(timeline):
                    if start > time_in_loop: break
                    found_idx = i
                
                for lookahead in range(1, 7):
                    target_idx = (found_idx + lookahead) % engine["total_segments_per_loop"]
                    
                    for bw in engine["output_bws"]:
                        curr_pos = 0
                        for v_idx, v in enumerate(engine["videos"]):
                            if curr_pos <= target_idx < curr_pos + v["seg_count"]:
                                seg_idx = target_idx - curr_pos
                                seg_id = f"{cid}_{v_idx}_{bw}_{seg_idx}.ts"
                                
                                if seg_id not in SEGMENT_CACHE:
                                    real_url = URL_MAP.get(seg_id)
                                    if real_url:
                                        try:
                                            r = http_session.get(real_url, timeout=(0.5, 2.0))
                                            if r.status_code == 200:
                                                with SEGMENT_CACHE_LOCK:
                                                    if seg_id not in SEGMENT_CACHE:
                                                        SEGMENT_CACHE[seg_id] = r.content
                                                        SEGMENT_CACHE.move_to_end(seg_id)
                                                        if len(SEGMENT_CACHE) > MAX_CACHE_SEGMENTS:
                                                            SEGMENT_CACHE.popitem(last=False)
                                            time.sleep(0.05) 
                                            
                                        except:
                                            pass
                                break
                        curr_pos += v["seg_count"]
            
            time.sleep(1) 
            
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    load_and_prepare_all()
    threading.Thread(target=background_prefetcher, daemon=True).start()
    
    from waitress import serve
    # Optimized waitress settings for HLS streaming
    serve(app, host="0.0.0.0", port=5000, threads=120, channel_timeout=10, 
          connection_limit=500, outbuf_overflow=2097152, inbuf_overflow=2097152)
