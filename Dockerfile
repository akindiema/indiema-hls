FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /data

EXPOSE 80 443

# Standard safe initialization loop:
CMD ["sh", "-c", " \
mkdir -p /data && \
cp -f /app/channels.json /data/channels.json 2>/dev/null || true; \
cp -f /app/fullchain.pem /data/fullchain.pem 2>/dev/null || true; \
cp -f /app/privkey.pem /data/privkey.pem 2>/dev/null || true; \
chmod 600 /data/privkey.pem 2>/dev/null || true; \
chmod 644 /data/fullchain.pem 2>/dev/null || true; \
nginx -g 'daemon off;' & \
python -u tvmanager_final.py & \
python -u app_final.py & \
python -u yt_relay.py & \
wait" \
]
