# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    HM_API_HOST=0.0.0.0 \
    HM_API_PORT=8000 \
    HM_API_ACCOUNT_STRATEGY=active_only \
    HM_API_CRED_DIR=/data/cred

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN uv sync --frozen --no-dev \
    && useradd --system --uid 10001 --home-dir /app hmapi \
    && mkdir -p /data/cred \
    && chown -R hmapi /app /data

USER hmapi

VOLUME ["/data/cred"]
EXPOSE 8000

CMD ["hm-api", "serve"]
