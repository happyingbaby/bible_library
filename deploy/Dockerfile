FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.14-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/launcher.py ./launcher.py

ENV BIBLE_HOST=127.0.0.1 \
    BIBLE_PORT=8765 \
    BIBLE_DATA_DIR=/data \
    BIBLE_REQUIRE_APP_KEY=0 \
    BIBLE_ALLOW_CONNECTION_CONFIG=0 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
CMD [".venv/bin/python", "launcher.py"]
