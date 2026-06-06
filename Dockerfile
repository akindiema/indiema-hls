FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN mkdir -p /data/logs

EXPOSE 80 443

# DETAILED LOGGING CMD LOOP:
# Redirects output (> /data/logs/...) for every script so we can see why app_final.py is silent.
CMD ["sh", "-c", " \
mkdir -p /data/logs && \
cp -f /app/channels.json /data/channels.json 2>/dev/null || true; \
cp -f /app/privkey.pem /data/privkey.pem 2>/dev/null || true; \
cp -f /app/fullchain.pem /data/fullchain.pem 2>/dev/null || true; \
if [ ! -f /data/privkey.pem ]; then \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /data/privkey.pem -out /data/fullchain.pem -subj '/CN=fast.infopluto.com'; \
fi; \
chmod 644 /data/*.pem 2>/dev/null || true; \
echo 'Starting app_final.py...' > /data/logs/startup.log; \
python -u app_final.py > /data/logs/app.log 2>&1 & \
python -u tvmanager_final.py > /data/logs/tvmanager.log 2>&1 & \
python -u yt_relay.py > /data/logs/yt_relay.log 2>&1 & \
sleep 3; \
nginx -g 'daemon off;' > /data/logs/nginx_system.log 2>&1"]
