FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg nginx curl procps openssl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask m3u8 requests waitress

VOLUME /data
ENV DATA_DIR=/data

# Clear out standard defaults and safely load configuration mappings
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Pre-create internal data maps
RUN mkdir -p /data

EXPOSE 80 443

# A clean, single-line sequential execution path that forces dummy fallback certificates 
# if your GitHub keys aren't mounted into the runtime space natively.
CMD ["sh", "-c", "cp -f /app/channels.json /data/channels.json 2>/dev/null || true; cp -f /app/*.pem /data/ 2>/dev/null || true; [ ! -f /data/fullchain.pem ] && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /data/privkey.pem -out /data/fullchain.pem -subj '/CN=fast.infopluto.com' || true; chmod 644 /data/*.pem 2>/dev/null || true; nginx -g 'daemon off;' & python tvmanager_final.py & python app_final.py & python yt_relay.py & wait"]
