FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg nginx curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Create clean Nginx config
RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80 default_server;
    server_name _;

    access_log /data/nginx_access.log combined;
    error_log /data/nginx_error.log warn;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

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
    echo '=== Container Starting at $(date) ===' > /data/startup.log && \
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    echo 'Nginx starting...' >> /data/startup.log && \
    nginx -g 'daemon off;' >> /data/startup.log 2>&1 & \
    echo 'TV Manager starting on 5001...' >> /data/startup.log && \
    python tvmanager_final.py >> /data/manager.log 2>&1 & \
    echo 'HLS Engine starting on 5000...' >> /data/startup.log && \
    python app_final.py >> /data/hls.log 2>&1 & \
    echo 'All services started. Waiting...' >> /data/startup.log && \
    tail -f /data/startup.log"]
