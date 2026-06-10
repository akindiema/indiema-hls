FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg nginx curl procps && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all repository contents into the container
COPY . /app

# Install Python requirements
RUN pip install --no-cache-dir flask m3u8 requests waitress

# Setup persistent storage volume configuration
VOLUME /data
ENV DATA_DIR=/data

# Clean default Nginx files and prepare directories
RUN mkdir -p /etc/nginx/ssl /data
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf /etc/nginx/nginx.conf

# Copy customized web-server layout configurations
COPY nginx.conf /etc/nginx/nginx.conf
COPY fullchain.pem /etc/nginx/ssl/fullchain.pem
COPY privkey.pem /etc/nginx/ssl/privkey.pem

# Apply restrictive security permissions for certificates
RUN chmod 644 /etc/nginx/ssl/fullchain.pem && chmod 600 /etc/nginx/ssl/privkey.pem

# Open web-routing container ports (Added 5020 for tvmonitor)
EXPOSE 80 443 5001 5010 5020

# Boot all layers in the background safely and use wait to keep the container open
CMD ["sh", "-c", " \
mkdir -p /data && \
if [ -f /app/channels.json ] && [ ! -f /data/channels.json ]; then cp /app/channels.json /data/channels.json; fi; \
nginx & \
python -u app_final.py & \
python -u yt_relay.py & \
python -u tvmonitor.py & \
if [ -f /app/tvmanager_final.py ]; then python -u tvmanager_final.py & else python -u tvmanager.py & fi; \
wait \
"]
