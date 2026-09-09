# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ARG VERSION=2.0.0-beta.6
ARG BUILD=20260908.10
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Playlist Bridge" \
      org.opencontainers.image.description="Sync Spotify and Apple Music playlists to Plex" \
      org.opencontainers.image.source="https://github.com/rstuke82/playlist-bridge" \
      org.opencontainers.image.version="${VERSION}" \
      io.playlist-bridge.build="${BUILD}" \
      org.opencontainers.image.revision="${VCS_REF}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYLIST_BRIDGE_DATA_DIR=/data \
    PLAYLIST_BRIDGE_PORT=8173
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY playlist_bridge/ ./playlist_bridge/
COPY sync.py LICENSE ./
COPY --from=frontend /build/web/dist ./web/dist
RUN mkdir -p /data
EXPOSE 8173
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + (os.environ.get('PLAYLIST_BRIDGE_PORT') or '8173') + '/api/health', timeout=4).close()"]
CMD ["python", "-m", "playlist_bridge", "web"]
