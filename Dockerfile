FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg nginx curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

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
