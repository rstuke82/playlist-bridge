# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime
ARG VERSION=3.0.0-beta7
ARG BUILD=20261011.9
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Harmonia" \
      org.opencontainers.image.description="Sync Spotify and Apple Music playlists to Plex" \
      org.opencontainers.image.source="https://github.com/rstuke82/playlist-bridge" \
      org.opencontainers.image.version="${VERSION}" \
      io.playlist-bridge.build="${BUILD}" \
      org.opencontainers.image.revision="${VCS_REF}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HARMONIA_DATA_DIR=/data \
    HARMONIA_PORT=8173 \
    HARMONIA_UPDATE_CHANNEL=beta
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip uninstall -y pip
COPY playlist_bridge/ ./playlist_bridge/
COPY LICENSE ./
COPY --from=frontend /build/web/dist ./web/dist
RUN groupadd --gid 10001 harmonia && useradd --uid 10001 --gid harmonia --no-create-home --shell /usr/sbin/nologin harmonia && mkdir -p /data && chown harmonia:harmonia /data
USER 10001:10001
EXPOSE 8173
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + (os.environ.get('HARMONIA_PORT') or '8173') + '/api/health', timeout=4).close()"]
CMD ["python", "-m", "playlist_bridge", "web"]
