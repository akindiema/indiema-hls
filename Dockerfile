FROM python:3.11-slim

# Install openssl along with other utilities for safety generation
RUN apt-get update && apt-get install -y ffmpeg nginx curl procps openssl && rm -rf /var/lib/apt/lists/*

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

# BULLETPROOF CMD LOOP:
# 1. Copies your custom files if they exist.
# 2. IF they are missing, it automatically creates dummy self-signed files so Nginx CANNOT crash.
# 3. Sets permissions and launches the stack.
CMD ["sh", "-c", "\
mkdir -p /data && \
cp -f /app/channels.json /data/ 2>/dev/null || true && \
cp -f /app/*.pem /data/ 2>/dev/null || true && \
if [ ! -f /data/fullchain.pem ] || [ ! -s /data/fullchain.pem ]; then \
    echo 'SSL missing! Generating temporary safety fallback certs...'; \
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 -keyout /data/privkey.pem -out /data/fullchain.pem -subj '/CN=fast.infopluto.com'; \
fi && \
chmod 644 /data/*.pem 2>/dev/null || true && \
nginx -g 'daemon off;' & \
python tvmanager_final.py & \
python app_final.py & \
python yt_relay.py & \
wait"]
