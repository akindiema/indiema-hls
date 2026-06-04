FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

RUN mkdir -p /data && cp /app/channels.json /data/ 2>/dev/null || true

EXPOSE 80

# Run TV Manager on port 80 + other services
CMD ["sh", "-c", "\
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    python tvmanager_final.py & \
    python app_final.py & \
    python yt_relay.py & \
    wait"]
