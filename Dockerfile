FROM python:3.11-slim

# Install system dependencies including Nginx
RUN apt-get update && apt-get install -y \
    ffmpeg nginx curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all your files
COPY . /app

# Install Python packages
RUN pip install --no-cache-dir flask m3u8 requests waitress

# Persistent volume
VOLUME /data
ENV DATA_DIR=/data

# Prepare directories
RUN mkdir -p /data /etc/nginx/conf.d && \
    cp /app/channels.json /data/ 2>/dev/null || true

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["sh", "-c", "\
    mkdir -p /data && \
    cp -f /data/channels.json /app/channels.json 2>/dev/null || true && \
    nginx && \
    python app_final.py & \
    python tvmanager_final.py & \
    python yt_relay.py & \
    wait"]
