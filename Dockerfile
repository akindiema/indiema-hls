FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg nginx curl procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all repository contents
COPY . /app

# Install Python requirements (Added tailer for analytics)
RUN pip install --no-cache-dir flask m3u8 requests waitress tailer

# Persistent data volume
VOLUME /data
ENV DATA_DIR=/data

# Create required directories
RUN mkdir -p /data /var/log/nginx /etc/nginx/ssl \
    && chmod 755 /var/log/nginx

# Remove default Nginx configs
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf /etc/nginx/nginx.conf

# Copy custom configs and certificates
COPY nginx.conf /etc/nginx/nginx.conf
COPY fullchain.pem /etc/nginx/ssl/fullchain.pem
COPY privkey.pem /etc/nginx/ssl/privkey.pem

# Set proper permissions
RUN chmod 644 /etc/nginx/ssl/fullchain.pem \
    && chmod 600 /etc/nginx/ssl/privkey.pem \
    && chmod 644 /etc/nginx/nginx.conf

# Expose ports
EXPOSE 80 443 5000 5001 5020 5021

# Startup script
CMD ["sh", "-c", " \
    mkdir -p /data /var/log/nginx && \
    # Copy channels.json if needed \
    if [ -f /app/channels.json ] && [ ! -f /data/channels.json ]; then \
        cp /app/channels.json /data/channels.json; \
    fi; \
    # Start services \
    nginx & \
    python -u app_final.py & \
    python -u yt_relay.py & \
    python -u tvmonitor.py & \
    python -u analytics_collector.py & \
    if [ -f /app/tvmanager_final.py ]; then \
        python -u tvmanager_final.py & \
    else \
        python -u tvmanager.py & \
    fi; \
    wait \
"]
