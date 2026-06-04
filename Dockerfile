FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all files
COPY . /app

# Install Python packages
RUN pip install --no-cache-dir flask m3u8 requests waitress

# Persistent data volume
VOLUME /data
ENV DATA_DIR=/data

# Prepare data directory
RUN mkdir -p /data && cp /app/channels.json /data/ 2>/dev/null || true

EXPOSE 5000 5001 5010

CMD ["sh", "-c", "\
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    python app_final.py & \
    python tvmanager_final.py & \
    python yt_relay.py & \
    wait"]
