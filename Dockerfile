FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Simple Nginx config
RUN echo 'server { listen 80; server_name _; location / { proxy_pass http://127.0.0.1:5001; proxy_set_header Host $host; } location /channel/ { proxy_pass http://127.0.0.1:5000; proxy_set_header Host $host; } }' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["sh", "-c", "\
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    nginx && \
    python app_final.py & \
    python tvmanager_final.py & \
    python yt_relay.py & \
    wait"]
