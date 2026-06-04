FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg nginx curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Create Nginx config
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    # TV Manager Dashboard
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # HLS Streaming (important for SSAI)
    location /channel/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

RUN mkdir -p /data && cp /app/channels.json /data/ 2>/dev/null || true

EXPOSE 80

CMD ["sh", "-c", "\
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    nginx -g 'daemon off;' & \
    python app_final.py & \
    python tvmanager_final.py & \
    python yt_relay.py & \
    wait"]
