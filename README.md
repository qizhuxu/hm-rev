# hm-api

`hm-api` 是面向 Huawei DevEco Code 的本地 OpenAI 兼容代理服务。它提供 CLI 登录、FastAPI 代理、多账号凭据管理、中文管理控制台、Docker 部署文件和 GitHub Actions 镜像构建工作流。

服务暴露以下核心入口：

- `/v1/models`：OpenAI 兼容模型列表接口。
- `/v1/chat/completions`：OpenAI 兼容聊天补全接口。
- `/ui`：中文管理控制台，用于登录、账号管理、使用统计和连通性检测。

## 功能特性

- DevEco OAuth 登录，支持本地回调和手动粘贴回调地址。
- 多账号管理：新增、覆盖、启用、重命名、删除账号，并支持标签与备注。
- 多账号调度：支持仅当前账号、轮询账号、失败自动切换三种策略。
- 本地 AES-GCM 加密保存凭据。
- OpenAI 兼容 `/v1/models` 与 `/v1/chat/completions`。
- 中文管理 UI：总览、账号工作台、请求统计、日志流、模型与能力、连通性检测、配置与安全信息。
- 本地使用统计：只记录请求元数据，不保存聊天正文。
- Dockerfile、docker-compose 和 GHCR 镜像构建工作流。

## 快速开始

### 环境要求

- Python 3.12+
- uv

### 安装依赖

```bash
uv sync
```

### 查看状态

```bash
uv run hm-api status
```

### 登录 DevEco 账号

推荐先使用不自动打开浏览器的方式，便于复制登录地址：

```bash
uv run hm-api login --no-browser
```

如果在容器或远程环境中使用，也可以启动服务后通过 `/ui` 的“登录向导”生成登录 URL，再手动粘贴 OAuth 回调地址完成登录。

## 启动服务

```bash
uv run hm-api serve --host 127.0.0.1 --port 8000 --key replace-with-local-key
```

打开管理控制台：

```text
http://127.0.0.1:8000/ui
```

当配置了 `--key` 或 `HM_API_KEY` 时，`/ui` 静态页面仍可在浏览器中加载，但它调用的后端管理 API 仍需要 `Authorization: Bearer <HM_API_KEY>`。

## API 使用示例

查询模型：

```bash
curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer replace-with-local-key"
```

发送非流式聊天请求：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer replace-with-local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "GLM-5.1",
    "messages": [
      {"role": "user", "content": "你好，请用一句话介绍 hm-api。"}
    ]
  }'
```

发送流式聊天请求：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer replace-with-local-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "GLM-5.1",
    "stream": true,
    "messages": [
      {"role": "user", "content": "请分三点说明如何安全保存本地凭据。"}
    ]
  }'
```

示例中的 Key 和模型名都是占位内容。不要把真实 API Key、DevEco 凭据、JWT、临时回调参数或其他敏感信息写入文档、日志或 Git。

## 中文管理控制台 `/ui`

启动服务后访问：

```text
http://127.0.0.1:8000/ui
```

管理控制台包含：

- **总览**：查看服务就绪度、当前启用账号、请求数量、成功率、平均延迟和最近请求。
- **账号工作台**：生成登录 URL，粘贴 OAuth 回调地址，新增账号或覆盖已有账号，启用、重命名、删除账号，编辑账号标签与备注。
- **请求透视**：按日期、模型、账号查看本地请求元数据。
- **日志流**：查看最近请求流水，支持自动刷新、定位到最新、按状态/流式/账号/模型筛选。
- **模型与能力**：按账号刷新 DevEco 模型配置，复制模型 ID，并切换账号调度策略。
- **连通性检测**：手动检测单个或全部账号是否能访问 DevEco 模型配置接口。
- **配置与安全**：查看 Bearer 认证状态、凭据目录和持久化文件是否存在，并一键复制 OpenAI SDK/curl 接入配置。

控制台不会展示真实 access token、refresh token、JWT、回调临时凭证或 Authorization 头。

## 多账号调度策略

默认策略是 `active_only`，保持旧版本行为：所有 `/v1/models` 和 `/v1/chat/completions` 请求都使用当前启用账号。

可以通过环境变量或 `/ui` 的“模型与能力”页切换策略：

| 策略 | 行为 |
| --- | --- |
| `active_only` | 只使用当前启用账号。 |
| `round_robin` | 在可用账号之间按请求轮询。显式检测失败的账号会被降级；如果全部账号都失败，会退回到所有有凭据的账号中尝试。 |
| `failover` | 优先当前启用账号；上游失败时尝试后续可用账号。 |

使用统计会记录实际发起请求的 `account_id`。策略不会改变凭据保存方式，也不会把 token 写入日志或 UI。

## Docker 部署

默认镜像发布在 GHCR：`ghcr.io/qizhuxu/hm-rev:latest`（每次推送到 `main` 时重新构建）。

```bash
docker run --rm \
  -p 8000:8000 \
  -e HM_API_HOST=0.0.0.0 \
  -e HM_API_PORT=8000 \
  -e HM_API_KEY=replace-with-local-key \
  -e HM_API_CRED_DIR=/data/cred \
  -v hm_api_cred:/data/cred \
  ghcr.io/qizhuxu/hm-rev:latest
```

容器默认以 root 启动 entrypoint，把 `/data/cred` chown 成 `PUID`/`PGID`（默认 1000:1000）再用 gosu 降权运行 hm-api，这样应用写的 `0600` 凭据文件能被容器读取。命名卷场景默认即可工作。

要把凭据直接落在宿主目录（便于备份/查看），改用 bind mount 并把 `PUID`/`PGID` 设成你宿主用户的 uid/gid（宿主跑 `id` 查看）：

```bash
docker run --rm \
  -p 8000:8000 \
  -e HM_API_KEY=replace-with-local-key \
  -e PUID=$(id -u) \
  -e PGID=$(id -g) \
  -v "$(pwd)/cred:/data/cred" \
  ghcr.io/qizhuxu/hm-rev:latest
```

如需本地构建（`Dockerfile` 基于 Python 3.12 和 uv）：

```bash
docker build -t hm-api:local .
docker run --rm -p 8000:8000 -e HM_API_KEY=replace-with-local-key -v hm_api_cred:/data/cred hm-api:local
```

容器启动后访问：

```text
http://127.0.0.1:8000/ui
```

本地开发环境可能没有 Docker。除非已经实际运行过 `docker build` 或 `docker compose` 并成功，否则不要声称 Docker 构建已在本机验证。

## Docker Compose

复制 `.env.example` 为 `.env`，设置本地 API Key 后启动：

```bash
docker compose up -d
```

默认拉取 `ghcr.io/qizhuxu/hm-rev:latest`（`pull_policy: always`）。如需本地构建，取消 `docker-compose.yml` 中 `build: .` 的注释。

`docker-compose.yml` 会把命名卷 `hm_api_cred` 挂载到 `/data/cred`，用于持久化账号凭据、使用统计和本地加密密钥。

## GitHub Actions 镜像构建

`.github/workflows/docker-image.yml` 用于构建 Docker 镜像：

- Pull Request：只构建，不推送。
- `main` 分支和 `v*.*.*` 标签：构建并发布到 GHCR。
- `main` 分支额外打 `latest` 标签，即 `ghcr.io/qizhuxu/hm-rev:latest`。
- 使用 `docker/metadata-action` 与 `docker/build-push-action`。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HM_API_HOST` | `127.0.0.1` | `hm-api serve` 默认监听地址。 |
| `HM_API_PORT` | `8000` | `hm-api serve` 默认监听端口。 |
| `HM_API_KEY` | 空 | 可选 Bearer API Key。设置后 API 和 UI API 都需要认证。 |
| `HM_API_PROXY` | 空 | 可选上游 HTTP/HTTPS 代理。 |
| `HM_API_ACCOUNT_STRATEGY` | `active_only` | 多账号调度策略：`active_only`、`round_robin` 或 `failover`。 |
| `HM_API_CRED_DIR` | `./cred` | 本地凭据、账号状态、使用统计和加密密钥目录。 |
| `PUID` / `PGID` | `1000` / `1000` | 仅 Docker：容器降权后的 uid/gid，entrypoint 会把凭据目录 chown 成它。bind mount 时设成宿主用户 uid/gid。 |
| `HM_API_CRED_DIR_HOST` | 空 | 仅 Docker：留空用命名卷；设成宿主路径（如 `./cred`）则改为 bind mount。 |

## 数据持久化

`HM_API_CRED_DIR` 下会保存本地关键数据。常见文件包括：

- `accounts.json`：多账号状态与加密后的凭据数据。
- `auth.json`：兼容旧登录流程的加密认证数据。
- `token.enc`：兼容旧登录流程的加密 token 文件。
- `usage.jsonl`：本地请求元数据统计。
- `.kek`：本地 AES-GCM 加密密钥。

`usage.jsonl` 只记录请求元数据，例如时间、接口、实际使用的账号 ID、模型名、是否流式、状态码、延迟、成功状态和上游返回的 token usage。它不保存聊天正文、原始凭据或 Authorization 头。

这些文件必须持久化，但不能提交到 Git，也不能烘焙进 Docker 镜像层。

## 安全说明

- 不要提交 `cred/`、`.env`、`*.enc`、`*.kek`、`*.key`。
- 不要在 README、测试、日志或截图里放入真实 API Key、DevEco 凭据、JWT、回调临时参数或 Authorization 头。
- `/ui` 静态页面可以公开加载，真正的管理 API 和代理 API 仍由 Bearer 认证保护。
- 账号连通性检测只有点击按钮时才会发起网络请求。
- OAuth 回调仍应保持本地绑定，除非经过明确评审。

## 测试与开发命令

```bash
uv run ruff check src/ tests/
uv run pyright src/
uv run pytest
```

测试会隔离凭据目录，并 mock 或绕开需要真实 Huawei 账号、浏览器登录、Docker daemon 或 live OAuth callback 的行为。

## 项目结构

```text
src/hm_api/
  cli.py       Typer CLI 命令：login、serve、status
  server.py    FastAPI 应用、OpenAI 兼容代理、UI 路由
  login.py     DevEco OAuth、回调解析、会话加载
  accounts.py  多账号存储、迁移、连通性检测
  usage.py     本地请求元数据统计
  ui.py        中文管理控制台 HTML/CSS/JS
  crypto.py    AES-GCM 加密辅助函数
  config.py    常量、默认端口和环境变量解析
tests/         pytest 测试
```

## 许可证

本项目使用 AGPL-3.0，并附加非商业限制。详情见 `LICENSE`。
