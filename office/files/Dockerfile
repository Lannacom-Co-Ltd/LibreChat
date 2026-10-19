FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-core fonts-noto-mono fonts-noto-color-emoji graphviz \
    && rm -rf /var/lib/apt/lists/*

# Build context is office/ so the image shares office/fonts with the Word templates.
COPY fonts/*.ttf /usr/share/fonts/truetype/sarabun/
# Build the font cache as root; the server runs as nobody and cannot write one.
RUN fc-cache -f
ENV MPLCONFIGDIR=/tmp/matplotlib XDG_CACHE_HOME=/tmp/cache

WORKDIR /app
COPY files/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY files/*.py ./

USER nobody
EXPOSE 8959
CMD ["python", "server.py"]
