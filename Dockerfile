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
    HM_API_CRED_DIR=/data/cred \
    PUID=1000 \
    PGID=1000

WORKDIR /app

# gosu lets the entrypoint drop root before running hm-api.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev \
    && mkdir -p /data/cred

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

VOLUME ["/data/cred"]
EXPOSE 8000

# The entrypoint runs as root, chowns the cred dir to PUID/PGID, then drops to
# that uid/gid via gosu before exec'ing the CMD. This makes bind-mounted cred
# directories work without a manual chown -- the app writes 0600 files, so the
# dir must be owned by the uid the process runs as.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["hm-api", "serve"]
