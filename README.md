# hm-api

DevEco Code OpenAI-compatible API CLI and lightweight Web UI.

`hm-api` exposes `/v1/models` and `/v1/chat/completions` for OpenAI-compatible clients, stores DevEco credentials locally with AES-GCM encryption, and provides a browser UI for container-friendly login.

## Requirements

- Python 3.12+
- uv

## Local Setup

```bash
uv sync
uv run hm-api status
uv run hm-api login --no-browser
uv run hm-api serve --host 127.0.0.1 --port 8000 --key replace-with-a-local-api-key
```

Open the Web UI at:

```text
http://127.0.0.1:8000/ui
```

When `--key` or `HM_API_KEY` is configured, the UI API prompts for that key and sends it as a Bearer token. The static `/ui` page does not expose credentials.

## Web UI Login

The Web UI supports manual callback login for local and Docker deployments.

1. Start the server.
2. Open `/ui`.
3. Create a DevEco login URL.
4. Open the URL and complete DevEco login.
5. If the browser lands on a localhost callback page, copy the full callback URL from the address bar.
6. Paste the callback URL or raw query string into the UI and save the login.

The UI never displays `access_token`, `refresh_token`, `jwt_token`, `tempToken`, or Authorization headers.

## API Usage

```bash
curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer replace-with-a-local-api-key"
```

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer replace-with-a-local-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "GLM-5.1",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `HM_API_HOST` | `127.0.0.1` | Bind host used by `hm-api serve` when `--host` is omitted. |
| `HM_API_PORT` | `8000` | Bind port used by `hm-api serve` when `--port` is omitted. |
| `HM_API_KEY` | empty | Optional Bearer token for API and UI API authentication. |
| `HM_API_PROXY` | empty | Optional upstream HTTP/HTTPS proxy for DevEco requests. |
| `HM_API_CRED_DIR` | `./cred` | Directory for encrypted credentials and the local key file. |

## Persistent Data

Credential data is stored under `HM_API_CRED_DIR`.

This directory contains encrypted auth data and the local AES key:

- `token.enc`
- `auth.json`
- `.kek`

Keep these files persistent across container restarts and never commit them.

## Docker

This repository includes a Dockerfile for Python 3.12 with uv.

```bash
docker build -t hm-api:local .
docker run --rm \
  -p 8000:8000 \
  -e HM_API_HOST=0.0.0.0 \
  -e HM_API_PORT=8000 \
  -e HM_API_KEY=replace-with-a-local-api-key \
  -e HM_API_CRED_DIR=/data/cred \
  -v hm_api_cred:/data/cred \
  hm-api:local
```

Open:

```text
http://127.0.0.1:8000/ui
```

## Docker Compose

Copy `.env.example` to `.env` and set a local API key.

```bash
docker compose up -d
```

Compose mounts the named volume `hm_api_cred` to `/data/cred` so credentials survive container replacement.

## GitHub Actions

`.github/workflows/docker-image.yml` builds the Docker image on pull requests, pushes to `main`, and version tags matching `v*.*.*`.

- Pull requests build the image but do not push it.
- `main` and tag pushes publish to GHCR as `ghcr.io/<owner>/<repo>`.
- The workflow uses `docker/metadata-action` and `docker/build-push-action`.

## Development Checks

```bash
uv run ruff check src/ tests/
uv run pyright src/
uv run pytest
```

Tests mock or isolate credential and DevEco behavior. They should not require a Huawei account, browser, Docker daemon, or live OAuth callback.

## Project Structure

```text
src/hm_api/
  cli.py       Typer CLI commands
  server.py    FastAPI API proxy and Web UI
  login.py     OAuth helpers and credential persistence
  crypto.py    AES-GCM credential encryption
  config.py    Constants and environment configuration
tests/         Focused pytest coverage
```

## License

This project is licensed under AGPL-3.0 with additional non-commercial restrictions. See `LICENSE` for details.
