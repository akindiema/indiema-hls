FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN mkdir -p /data

EXPOSE 80 443

# DIAGNOSTIC FOREGROUND LOOP:
# Spawns background tasks quietly, but leaves app_final.py fully exposed in the foreground.
# If app_final.py crashes, Bunny will print the exact Python error traceback here!
CMD ["sh", "-c", " \
mkdir -p /data && \
cp -f /app/channels.json /data/channels.json 2>/dev/null || true; \
cp -f /app/privkey.pem /data/privkey.pem 2>/dev/null || true; \
cp -f /app/fullchain.pem /data/fullchain.pem 2>/dev/null || true; \
if [ ! -f /data/privkey.pem ]; then \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /data/privkey.pem -out /data/fullchain.pem -subj '/CN=fast.infopluto.com'; \
fi; \
chmod 644 /data/*.pem 2>/dev/null || true; \
nginx -g 'daemon off;' & \
python tvmanager_final.py & \
python yt_relay.py & \
echo '--- LAUNCHING MAIN STREAM APP ---'; \
python -u app_final.py"]
