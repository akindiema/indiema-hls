FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Clean up default configurations and cleanly link your custom setup
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN mkdir -p /data && cp /app/channels.json /data/ 2>/dev/null || true

# Open both standard web routing ports natively 
EXPOSE 80 443

# The runtime loop grants explicit read permissions to certificates before Nginx boots up
CMD ["sh", "-c", "mkdir -p /data && cp -f /data/channels.json /app/channels.json 2>/dev/null || true && chmod 644 /data/*.pem 2>/dev/null || true && nginx -g 'daemon off;' & python tvmanager_final.py & python app_final.py & python yt_relay.py & wait"]
