# hm-api

DevEco Code OpenAI-compatible API CLI and Chinese Web management console.

`hm-api` exposes `/v1/models` and `/v1/chat/completions` for OpenAI-compatible clients, stores DevEco credentials locally with AES-GCM encryption, and provides a browser UI for container-friendly login, multi-account management, usage statistics, and account connectivity checks.

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

## 中文 Web 管理台

Open `/ui` after starting the server. The first screen is a Chinese management console with these areas:

- 总览: service status, current active account, today's request count, success rate, average latency, and recent requests.
- 账号管理: create DevEco login URL, paste manual OAuth callback, save as a new account, activate, rename, or delete accounts.
- 使用统计: local request metadata grouped by model and day.
- 连通性检测: run a low-risk DevEco model-config check for one account or all accounts.
- 配置: API auth state, credential directory, and data policy.

The UI supports manual callback login for local and Docker deployments.

1. Start the server.
2. Open `/ui`.
3. In `账号管理`, create a DevEco login URL.
4. Open the URL and complete DevEco login.
5. If the browser lands on a localhost callback page, copy the full callback URL from the address bar.
6. Paste the callback URL or raw query string into the UI and save the account.

The UI never displays `access_token`, `refresh_token`, `jwt_token`, `tempToken`, or Authorization headers.

When `--key` or `HM_API_KEY` is configured, `/ui` can still load in the browser, but all `/ui/api/*` management calls require `Authorization: Bearer <key>`. The UI prompts for the key and stores it only in browser `sessionStorage`.

## Management API

The console uses stable JSON endpoints under `/ui/api/*`:

- `GET /ui/api/overview`
- `GET /ui/api/accounts`
- `POST /ui/api/accounts/login-url`
- `POST /ui/api/accounts/manual-callback`
- `POST /ui/api/accounts/{account_id}/activate`
- `PATCH /ui/api/accounts/{account_id}`
- `DELETE /ui/api/accounts/{account_id}`
- `POST /ui/api/accounts/{account_id}/check`
- `POST /ui/api/accounts/check-all`
- `GET /ui/api/usage`

Older UI endpoints remain available for compatibility: `GET /ui/api/status`, `POST /ui/api/login-url`, and `POST /ui/api/manual-callback`.

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

Credential and local statistics data are stored under `HM_API_CRED_DIR`.

This directory contains encrypted auth data, multi-account state, request metadata, and the local AES key:

- `token.enc`
- `auth.json`
- `accounts.json`
- `usage.jsonl`
- `.kek`

`accounts.json` stores account metadata plus encrypted access, refresh, and JWT tokens. `usage.jsonl` stores request metadata only: timestamp, endpoint, account ID, model, stream flag, status code, latency, success/error state, and upstream token usage if the upstream returned it. It does not store prompt text, message content, raw tokens, or Authorization headers.

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

The same volume also persists `accounts.json`, `usage.jsonl`, and `.kek`. If you override `HM_API_CRED_DIR`, keep it mounted to a persistent volume.

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

This local workspace may not have Docker installed. In that case, verify Docker support by reviewing `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and `.github/workflows/docker-image.yml`; do not claim a local Docker build unless `docker build` or `docker compose` actually ran successfully.

## Project Structure

```text
src/hm_api/
  cli.py       Typer CLI commands
  server.py    FastAPI API proxy and Web UI
  login.py     OAuth helpers and credential persistence
  accounts.py  Multi-account credential state and connectivity checks
  usage.py     Local request metadata statistics
  ui.py        Chinese management console HTML/CSS/JS
  crypto.py    AES-GCM credential encryption
  config.py    Constants and environment configuration
tests/         Focused pytest coverage
```

## License

This project is licensed under AGPL-3.0 with additional non-commercial restrictions. See `LICENSE` for details.
