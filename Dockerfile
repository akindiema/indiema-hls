FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Clean up default configurations and cleanly link your custom setup
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /data

# Open both standard web routing ports natively 
EXPOSE 80 443

# SECURE PRODUCTION BOOT LOOP:
# 1. Copies channels data
# 2. Safely copies your exact privkey.pem and fullchain.pem files to the persistent volume
# 3. Runs an absolute safety check: if files fail to copy, auto-creates self-signed certificates so Nginx CANNOT crash
# 4. Corrects file read permissions and boots up Nginx + your Python streaming applications
CMD ["sh", "-c", " \
mkdir -p /data && \
cp -f /app/channels.json /data/channels.json 2>/dev/null || true; \
cp -f /app/privkey.pem /data/privkey.pem 2>/dev/null || true; \
cp -f /app/fullchain.pem /data/fullchain.pem 2>/dev/null || true; \
if [ ! -f /data/privkey.pem ] || [ ! -s /data/privkey.pem ] || [ ! -f /data/fullchain.pem ] || [ ! -s /data/fullchain.pem ]; then \
    echo 'SSL missing or empty! Generating temporary safety fallback certs...'; \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /data/privkey.pem -out /data/fullchain.pem -subj '/CN=fast.infopluto.com'; \
fi; \
chmod 644 /data/*.pem 2>/dev/null || true; \
nginx -g 'daemon off;' & \
python -u tvmanager_final.py & \
python -u app_final.py & \
python -u yt_relay.py & \
wait"]
