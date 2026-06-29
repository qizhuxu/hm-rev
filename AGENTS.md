# Repository Guidelines

## Project Snapshot

- `hm-api` is a Python 3.12+ CLI and FastAPI reverse proxy that exposes OpenAI-compatible endpoints for Huawei DevEco Code.
- Package code lives in `src/hm_api/`. The root `main.py` is only a placeholder entry point.
- Use `uv` for dependency management and command execution. Runtime and dev dependencies are declared in `pyproject.toml`.
- The app has real network side effects during OAuth login and proxy serving. Do not run login flows, open browsers, or call DevEco endpoints unless the user explicitly asks.

## Source Map

| Path | Responsibility |
|------|----------------|
| `src/hm_api/cli.py` | Typer CLI commands: `login`, `serve`, and `status`. |
| `src/hm_api/login.py` | DevEco OAuth flow, localhost callback server, JWT parsing, and session loading. |
| `src/hm_api/server.py` | FastAPI app with `/v1/models` and `/v1/chat/completions`, including streaming passthrough. |
| `src/hm_api/crypto.py` | AES-GCM helpers for encrypted local credential storage. |
| `src/hm_api/config.py` | DevEco URLs, default ports, credential paths, and User-Agent constants. |

## Common Commands

```bash
uv sync
uv run hm-api status
uv run hm-api login --no-browser
uv run hm-api serve --host 127.0.0.1 --port 8000 --key <secret>
uv run ruff check src/
uv run pyright src/
```

- Prefer `uv run ...` over calling Python tools directly.
- Use `--no-browser` for manual login testing so browser launch is explicit and visible.
- Do not use a real API key, access token, refresh token, JWT, or DevEco credential in examples.

## Tests And Verification

- There is no committed test suite yet. When changing code, add focused tests under `tests/` and introduce `pytest` as a dev dependency if needed.
- Good first test targets: `_parse_request`, `_parse_callback`, `_parse_jwt`, auth middleware behavior in `build_app`, model-list response shaping, and credential encrypt/decrypt round trips using a temporary credential directory.
- Mock `httpx`/DevEco network calls in tests. Avoid tests that require a Huawei account, browser, or live OAuth callback.
- For code changes, run at least `uv run ruff check src/` and `uv run pyright src/`. Run any added tests as well.

## Security And Data Handling

- `cred/`, `*.enc`, `*.kek`, and `*.key` are sensitive local artifacts. Never print, stage, commit, or include their contents in logs or docs.
- Never log raw `access_token`, `refresh_token`, `jwt_token`, `tempToken`, API keys, or Authorization headers. Prefer booleans, redacted prefixes, or lengths only.
- Keep bearer-token auth behavior in `server.py` conservative. When `--key` is set, every endpoint must require `Authorization: Bearer <key>`.
- Validate and fail clearly at boundaries: CLI options, JSON request bodies, callback parameters, proxy URLs, and upstream responses.
- Preserve local-only callback binding (`127.0.0.1`) for OAuth unless there is an explicit, reviewed reason to change it.

## Coding Conventions

- Follow the existing Python style: `from __future__ import annotations`, explicit type hints, small helpers, and async I/O via `asyncio`/`httpx`.
- Keep FastAPI route definitions inside `build_app` unless a refactor has a clear test-backed benefit.
- Prefer returning new dictionaries/records over mutating caller-provided data, especially in credential and request-shaping code.
- Preserve OpenAI-compatible response shapes for `/v1/models` and `/v1/chat/completions`.
- Keep README-facing examples safe and local; use placeholders for secrets.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **hm-rev** (153 symbols, 279 relationships, 15 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
