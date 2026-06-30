# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the CLI
uv run hm-api login                        # OAuth login with DevEco
uv run hm-api serve                        # Start proxy server (default :8000)
uv run hm-api serve --key <secret>         # With API key auth
uv run hm-api serve --proxy <url>          # Via upstream proxy
uv run hm-api status                       # Login status

# Lint & type-check
uv run ruff check src/                     # Lint
uv run pyright src/                        # Type check (strict)

# Shell alias
. .venv/Scripts/activate && hm-api serve   # Activated venv
```

There are no tests yet. If adding them, use `pytest` as the test runner with standard `tests/` structure.

## Architecture

This is a thin OpenAI-compatible reverse proxy for Huawei DevEco Code's MaaS API. It translates OpenAI chat completion calls into DevEco's internal API format.

```
          OpenAI API                     DevEco MaaS
  client ──────────► hm-api proxy ──────────────► Huawei Cloud
  (curl/IDE)       │                    │
                   │  cred/token.enc    │
                   │  cred/auth.json    │  (AES-GCM encrypted)
```

### Module layout (`src/hm_api/`)

| Module | Role |
|---|---|
| `cli.py` | Typer CLI — `login`, `serve`, `status` commands |
| `server.py` | FastAPI app — `/v1/models`, `/v1/chat/completions` (streaming + non-streaming) |
| `login.py` | OAuth flow — local callback server, temp token → JWT exchange, credential persistence |
| `crypto.py` | AES-GCM encryption layer for credentials on disk |
| `config.py` | Constants — DevEco URLs, ports, paths, User-Agent |

### Key design decisions

- **No database** — credentials stored as encrypted files under `./cred/`
- **Encryption** — per-machine AES-256-GCM key (`cred/.kek`), encrypted JSON blob per value
- **Streaming** — `httpx.AsyncClient.stream()` with passthrough SSE forwarding; upstream connection errors are currently unhandled (will propagate as 500)
- **Auth** — optional Bearer token middleware; when `--key` is set, all endpoints require matching `Authorization: Bearer <key>`
- **OAuth flow** — spins up a temporary `asyncio.start_server` on localhost to catch the OAuth redirect; supports port fallback (10101, 34567–34570)
- **Proxy** — supports upstream HTTP/HTTPS proxy via `httpx.AsyncHTTPTransport(proxy=...)`, applied to both transport mounts

### Data flow: chat completion request

```
curl POST /v1/chat/completions          OpenAI-compatible JSON
  │
  ├─ auth_middleware checks Bearer token (if --key set)
  │
  ├─ chat_completions()
  │   ├─ load_auth_data() → access_token from cred/auth.json
  │   ├─ detect stream=true/false → route to v2/chat/completions or v2/no-stream/...
  │   ├─ forward headers (Authorization, Session-Id, Chat-Id, etc.)
  │   │
  │   ├─ if stream:
  │   │   └─ StreamingResponse(client.stream(...))
  │   │       └─ iterates upstream response chunks via aiter_bytes()
  │   │
  │   └─ if not stream:
  │       └─ client.post() → JSONResponse
```

### DevEco API notes

- Base: `https://cn.devecostudio.huawei.com/sse/codeGenie/maas`
- Model list: `/codeGenie/modelConfig?localVersion=0&pluginVersion=CLI.0.1.0`
- Auth: Bearer token from OAuth (access_token in cred/auth.json)
- Only China site (`siteId=1`) is supported
- Session affinity: `x-deveco-session` or `x-session-affinity` headers forwarded upstream

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **hm-rev** (171 symbols, 296 relationships, 15 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/hm-rev/context` | Codebase overview, check index freshness |
| `gitnexus://repo/hm-rev/clusters` | All functional areas |
| `gitnexus://repo/hm-rev/processes` | All execution flows |
| `gitnexus://repo/hm-rev/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
