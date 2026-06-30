"""Chinese management console HTML."""

from __future__ import annotations


def render_ui_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hm-api 管理控制台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f1ec;
      --surface: #fffefa;
      --surface-soft: #f9f6ef;
      --ink: #1f2428;
      --muted: #657078;
      --line: #d8d1c6;
      --green: #18745a;
      --blue: #285f8f;
      --amber: #9a5b1f;
      --red: #a9423a;
      --shadow: 0 12px 30px rgba(31, 36, 40, .08);
      font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    html, body { max-width: 100%; overflow-x: hidden; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-size: 14px;
    }
    button, input, textarea, select { font: inherit; }
    button {
      min-height: 38px;
      border: 1px solid var(--green);
      background: var(--green);
      color: #fff;
      padding: 0 13px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 700;
      white-space: nowrap;
    }
    button.secondary { background: transparent; color: var(--green); }
    button.ghost { border-color: var(--line); background: var(--surface); color: var(--ink); }
    button.danger { border-color: var(--red); background: var(--red); }
    button:disabled { opacity: .48; cursor: not-allowed; }
    input, textarea, select {
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 8px 10px;
    }
    textarea { min-height: 126px; resize: vertical; }
    label {
      display: block;
      margin: 10px 0 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 25px; line-height: 1.25; }
    h2 { font-size: 17px; line-height: 1.35; }
    h3 { font-size: 14px; line-height: 1.35; }
    pre {
      margin: 0;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f7f5ef;
      padding: 10px;
    }
    .shell {
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
      min-height: 100vh;
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 16px;
      min-width: 0;
      border-right: 1px solid var(--line);
      background: #e8e2d7;
      padding: 18px;
    }
    .brand {
      display: grid;
      gap: 4px;
      padding-bottom: 12px;
      border-bottom: 1px solid rgba(31, 36, 40, .12);
    }
    .brand strong { font-size: 20px; }
    .brand span, .muted { color: var(--muted); }
    .nav { display: grid; gap: 6px; min-width: 0; }
    .nav button {
      display: grid;
      gap: 2px;
      width: 100%;
      min-height: 52px;
      padding: 8px 10px;
      border-color: transparent;
      background: transparent;
      color: var(--ink);
      text-align: left;
      white-space: normal;
    }
    .nav button.active {
      border-color: var(--line);
      background: var(--surface);
      color: var(--green);
      box-shadow: var(--shadow);
    }
    .nav small { color: var(--muted); font-weight: 600; }
    .sidebar-note {
      margin-top: auto;
      border: 1px solid rgba(31, 36, 40, .12);
      border-radius: 8px;
      background: rgba(255, 254, 250, .58);
      padding: 12px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 12px;
    }
    .workspace {
      min-width: 0;
      padding: 18px;
    }
    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: start;
      margin-bottom: 14px;
    }
    .eyebrow {
      margin-bottom: 5px;
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
    }
    .subtitle {
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.6;
    }
    .top-actions, .toolbar, .segmented, .pill-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    .toolbar { margin: 10px 0; }
    .segmented button {
      min-height: 34px;
      border-color: var(--line);
      background: var(--surface);
      color: var(--muted);
    }
    .segmented button.active {
      border-color: var(--blue);
      color: var(--blue);
      background: #edf4fa;
    }
    .banner {
      display: none;
      margin-bottom: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff8e5;
      color: var(--amber);
      padding: 11px 12px;
      font-weight: 750;
    }
    .banner.active { display: block; }
    .banner.err {
      color: var(--red);
      background: #fff3f0;
      border-color: #e2b8b1;
    }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .status-card, .metric, .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      min-width: 0;
    }
    .status-card, .metric { padding: 12px; }
    .panel { padding: 14px; }
    .status-card {
      display: grid;
      gap: 5px;
      min-height: 76px;
    }
    .status-card .label, .metric .label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }
    .status-card .value {
      font-size: 15px;
      font-weight: 850;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .metric .value {
      margin-top: 7px;
      font-size: 25px;
      font-weight: 850;
      line-height: 1.1;
    }
    .metric .hint {
      margin-top: 7px;
      color: var(--muted);
      font-size: 12px;
    }
    .page { display: none; }
    .page.active { display: block; }
    .grid-2 {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(330px, .9fr);
      gap: 14px;
      align-items: start;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }
    .grid-2 > *, .grid-3 > *, .stack { min-width: 0; }
    .stack { display: grid; gap: 14px; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 10px;
    }
    .panel-sub {
      color: var(--muted);
      line-height: 1.55;
      font-size: 12px;
    }
    .pill {
      display: inline-flex;
      min-height: 26px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0 9px;
      background: var(--surface-soft);
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }
    .pill.ok { border-color: #bbd7cc; color: var(--green); background: #eef8f4; }
    .pill.bad { border-color: #e2b8b1; color: var(--red); background: #fff3f0; }
    .pill.warn { border-color: #e0c58e; color: var(--amber); background: #fff8e5; }
    .table-wrap {
      width: 100%;
      min-width: 0;
      max-width: 100%;
      overflow-x: auto;
    }
    .table {
      width: 100%;
      min-width: 560px;
      border-collapse: collapse;
      font-size: 13px;
    }
    .table th, .table td {
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }
    .table th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }
    .row-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .row-actions button { min-height: 30px; padding: 0 9px; font-size: 12px; }
    .empty {
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: #fffaf0;
      color: var(--muted);
      padding: 16px;
      line-height: 1.7;
    }
    .mono {
      font-family: "JetBrains Mono", Consolas, monospace;
      font-size: 12px;
      word-break: break-all;
    }
    .message {
      min-height: 24px;
      margin-top: 10px;
      font-size: 13px;
      font-weight: 800;
    }
    .message.ok { color: var(--green); }
    .message.err { color: var(--red); }
    .account-list {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }
    .account-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 10px;
      cursor: pointer;
    }
    .account-row.selected {
      border-color: var(--blue);
      background: #edf4fa;
    }
    .account-main {
      display: grid;
      gap: 5px;
      min-width: 0;
    }
    .account-title {
      display: flex;
      gap: 7px;
      align-items: center;
      flex-wrap: wrap;
      font-weight: 850;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .detail-item {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 10px;
      min-width: 0;
    }
    .detail-item span {
      display: block;
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
    }
    .steps {
      display: grid;
      gap: 8px;
      margin: 10px 0 12px;
      padding: 0;
      list-style: none;
      counter-reset: steps;
    }
    .steps li {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 9px;
      color: var(--muted);
      line-height: 1.55;
    }
    .steps li::before {
      counter-increment: steps;
      content: counter(steps);
      display: inline-flex;
      width: 24px;
      height: 24px;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      background: var(--blue);
      color: #fff;
      font-size: 12px;
      font-weight: 850;
    }
    .trend {
      display: grid;
      gap: 9px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: 96px minmax(80px, 1fr) 54px;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
    }
    .bar-track {
      height: 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f2eee5;
      overflow: hidden;
    }
    .bar {
      display: block;
      height: 100%;
      min-width: 3px;
      background: var(--blue);
    }
    .health-list {
      display: grid;
      gap: 8px;
    }
    .health-item {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding: 8px 0;
    }
    .health-item:last-child { border-bottom: 0; }
    .file-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .file-item {
      display: grid;
      gap: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 9px;
    }
    .kbd {
      display: inline-flex;
      min-height: 24px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 5px;
      background: #fff;
      padding: 0 7px;
      font-family: "JetBrains Mono", Consolas, monospace;
      font-size: 12px;
    }
    @media (max-width: 1120px) {
      .status-grid, .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid-2, .grid-3 { grid-template-columns: 1fr; }
    }
    @media (max-width: 820px) {
      .shell { grid-template-columns: 1fr; }
      .sidebar {
        width: 100%;
        max-width: 100vw;
        min-width: 0;
        border-right: 0;
        border-bottom: 1px solid var(--line);
        padding: 14px;
      }
      .sidebar-note { display: none; }
      .nav {
        display: flex;
        width: 100%;
        max-width: 100%;
        min-width: 0;
        overflow-x: auto;
        padding-bottom: 2px;
      }
      .nav button {
        flex: 0 0 auto;
        width: 128px;
        min-height: 48px;
      }
      .workspace {
        width: 100%;
        max-width: 100vw;
        padding: 14px;
      }
      .topbar { grid-template-columns: 1fr; }
      .top-actions { justify-content: flex-start; }
      .status-grid, .metrics, .detail-grid, .file-grid { grid-template-columns: 1fr; }
      .bar-row { grid-template-columns: 76px minmax(70px, 1fr) 42px; }
      h1 { font-size: 22px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <strong>hm-api 管理台</strong>
        <span>DevEco Code 本地代理控制面板</span>
      </div>
      <nav class="nav" aria-label="管理导航">
        <button class="active" data-tab="overview">总览<small>服务、账号、流量</small></button>
        <button data-tab="accounts">账号工作台<small>多账号、登录向导</small></button>
        <button data-tab="usage">请求透视<small>趋势、模型、错误</small></button>
        <button data-tab="logs">日志流<small>自动刷新、定位最新</small></button>
        <button data-tab="models">模型与能力<small>账号模型、复制 ID</small></button>
        <button data-tab="checks">连通性检测<small>批量检查、错误摘要</small></button>
        <button data-tab="settings">配置与安全<small>认证、持久化、示例</small></button>
      </nav>
      <div class="sidebar-note">
        控制台只展示账号元数据和健康状态，不展示 access token、refresh token、JWT 或回调临时凭证。
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <div class="eyebrow">管理控制台</div>
          <h1 id="pageTitle">总览</h1>
          <p class="subtitle" id="pageSubtitle">集中查看服务就绪度、当前账号、请求统计和最近调用。</p>
        </div>
        <div class="top-actions">
          <button id="reloadAll" class="secondary">刷新数据</button>
          <button id="clearBearer" class="ghost">清除 API Key</button>
        </div>
      </header>

      <div id="loadState" class="banner active">正在读取管理数据...</div>

      <div class="status-grid" aria-label="关键状态">
        <div class="status-card">
          <span class="label">登录状态</span>
          <span class="value" id="badgeLogin">账号状态加载中</span>
        </div>
        <div class="status-card">
          <span class="label">API 认证</span>
          <span class="value" id="badgeAuth">认证状态加载中</span>
        </div>
        <div class="status-card">
          <span class="label">凭据目录</span>
          <span class="value" id="badgeCred">凭据目录加载中</span>
        </div>
        <div class="status-card">
          <span class="label">数据持久化</span>
          <span class="value" id="badgePersist">持久化状态加载中</span>
        </div>
      </div>

      <section class="page active" id="page-overview">
        <div class="metrics">
          <div class="metric"><div class="label">今日请求</div><div class="value" id="mToday">0</div><div class="hint">来自本地 usage 记录</div></div>
          <div class="metric"><div class="label">成功率</div><div class="value" id="mSuccess">0%</div><div class="hint" id="mSuccessHint">暂无请求</div></div>
          <div class="metric"><div class="label">平均延迟</div><div class="value" id="mLatency">0ms</div><div class="hint">非空记录平均值</div></div>
          <div class="metric"><div class="label">账号数量</div><div class="value" id="mAccounts">0</div><div class="hint" id="mAccountHint">暂无账号</div></div>
          <div class="metric"><div class="label">错误请求</div><div class="value" id="mErrors">0</div><div class="hint">最近统计窗口</div></div>
        </div>
        <div class="grid-2">
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>服务就绪度</h2>
                  <p class="panel-sub">按管理 API、凭据、当前账号、认证和统计文件检查可用性。</p>
                </div>
              </div>
              <div id="readinessList" class="health-list"></div>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>7 日请求趋势</h2>
                  <p class="panel-sub">只展示已记录请求数量，不含聊天正文。</p>
                </div>
              </div>
              <div id="overviewTrend" class="trend"></div>
            </section>
          </div>
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>当前启用账号</h2>
                  <p class="panel-sub">代理请求会优先使用这个账号。</p>
                </div>
              </div>
              <div id="activeAccount" class="empty">暂无启用账号</div>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>最近请求</h2>
                  <p class="panel-sub">展示接口、状态、延迟和模型元数据。</p>
                </div>
              </div>
              <div id="recentRequests" class="empty">暂无请求记录</div>
            </section>
          </div>
        </div>
      </section>

      <section class="page" id="page-accounts">
        <div class="grid-2">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>账号列表</h2>
                <p class="panel-sub">可筛选、查看详情、启用、重命名、检测或删除账号。</p>
              </div>
              <button id="refreshAccounts" class="secondary">刷新</button>
            </div>
            <input id="accountSearch" placeholder="搜索显示名、用户或账号 ID">
            <div class="toolbar segmented" id="accountFilters">
              <button class="active" data-account-filter="all">全部</button>
              <button data-account-filter="active">当前启用</button>
              <button data-account-filter="ok">连通正常</button>
              <button data-account-filter="fail">连通失败</button>
              <button data-account-filter="unchecked">未检测</button>
            </div>
            <div id="accountsTable"></div>
          </section>

          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>账号详情</h2>
                  <p class="panel-sub">仅展示脱敏后的账号元数据和检测摘要。</p>
                </div>
              </div>
              <div id="accountDetail" class="empty">请选择一个账号查看详情。</div>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>登录向导</h2>
                  <p class="panel-sub">生成登录 URL 后，手动粘贴 OAuth 回调地址完成保存。</p>
                </div>
              </div>
              <ol class="steps">
                <li>选择新增账号或覆盖已有账号，设置回调端口（容器部署用宿主映射端口）。</li>
                <li>生成并复制登录 URL，在浏览器完成 DevEco 授权。</li>
                <li>授权成功后浏览器会自动回调 hm-api，无需手动粘贴。</li>
                <li>如果自动回调失败，可以手动粘贴回调地址。保存后账号会写入本地凭据目录，并自动设为当前启用。</li>
              </ol>
              <label for="accountTarget">保存方式</label>
              <select id="accountTarget">
                <option value="">新增账号</option>
              </select>
              <label for="displayName">显示名</label>
              <input id="displayName" placeholder="例如：生产账号">
              <label for="callbackPort">回调端口</label>
              <input id="callbackPort" type="number" min="1" max="65535" value="10101">
              <p class="panel-sub" style="margin-top:-6px; font-size:0.85em">容器部署时填宿主侧映射端口，DevEco 会回调到 hm-api 自身。</p>
              <div class="toolbar">
                <button id="createLogin">生成登录 URL</button>
                <button id="copyLogin" class="secondary" disabled>复制 URL</button>
              </div>
              <div id="loginUrlBox" class="empty">登录 URL 会显示在这里。</div>
              <label for="expectedCode">校验 Code</label>
              <input id="expectedCode" autocomplete="off">
              <label for="callbackUrl">OAuth 回调地址或 Query</label>
              <textarea id="callbackUrl" spellcheck="false" placeholder="例如：http://127.0.0.1:10101/callback?code=..."></textarea>
              <button id="saveAccount">保存账号</button>
              <div class="message" id="accountMessage"></div>
            </section>
          </div>
        </div>
      </section>

      <section class="page" id="page-usage">
        <div class="metrics">
          <div class="metric"><div class="label">总请求</div><div class="value" id="uTotal">0</div><div class="hint">usage.jsonl 记录</div></div>
          <div class="metric"><div class="label">错误率</div><div class="value" id="uError">0%</div><div class="hint" id="uErrorHint">暂无错误</div></div>
          <div class="metric"><div class="label">非流式/流式</div><div class="value" id="uStream">-</div><div class="hint">请求模式占比</div></div>
          <div class="metric"><div class="label">Token 用量</div><div class="value" id="uToken">上游未返回</div><div class="hint">只统计上游 usage 字段</div></div>
          <div class="metric"><div class="label">最近记录</div><div class="value" id="uRecent">0</div><div class="hint">最多展示 20 条</div></div>
        </div>
        <div class="grid-2">
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>趋势分析</h2>
                  <p class="panel-sub">7 日请求量分布，空窗口保持真实空态。</p>
                </div>
              </div>
              <div id="trendStats" class="trend"></div>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>按模型统计</h2>
                  <p class="panel-sub">按 model 字段聚合请求、成功、失败和平均延迟。</p>
                </div>
              </div>
              <div id="modelStats"></div>
            </section>
          </div>
          <div class="stack">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>按账号统计</h2>
                  <p class="panel-sub">把 usage 中的 account_id 映射到本地显示名。</p>
                </div>
              </div>
              <div id="accountUsageStats"></div>
            </section>
            <section class="panel">
              <div class="panel-head">
                <div>
                  <h2>请求流水</h2>
                  <p class="panel-sub">本地过滤，不上传或保存筛选词。</p>
                </div>
              </div>
              <div class="toolbar">
                <input id="requestSearch" placeholder="筛选接口、模型、账号或状态码">
                <select id="requestFilter" aria-label="请求状态筛选">
                  <option value="all">全部状态</option>
                  <option value="success">仅成功</option>
                  <option value="error">仅失败</option>
                  <option value="stream">仅流式</option>
                </select>
              </div>
              <div id="recentUsageTable"></div>
            </section>
          </div>
        </div>
      </section>

      <section class="page" id="page-logs">
        <div class="metrics">
          <div class="metric"><div class="label">日志总数</div><div class="value" id="logTotal">0</div><div class="hint">usage.jsonl 元数据</div></div>
          <div class="metric"><div class="label">当前展示</div><div class="value" id="logShown">0</div><div class="hint">最近记录窗口</div></div>
          <div class="metric"><div class="label">自动刷新</div><div class="value" id="logAutoState">关闭</div><div class="hint">定位到最新记录</div></div>
          <div class="metric"><div class="label">最新状态</div><div class="value" id="logLatestState">-</div><div class="hint">按最新一条计算</div></div>
          <div class="metric"><div class="label">轮询策略</div><div class="value" id="logStrategy">active_only</div><div class="hint">当前账号调度</div></div>
        </div>
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>日志流</h2>
              <p class="panel-sub">展示最近请求元数据，自动刷新时会保持定位到最新记录，不包含聊天正文。</p>
            </div>
            <div class="top-actions">
              <button id="refreshLogs" class="secondary">刷新日志</button>
              <button id="scrollLatestLog" class="ghost">定位最新</button>
            </div>
          </div>
          <div class="toolbar">
            <label class="pill"><input id="autoRefreshLogs" type="checkbox" style="width:auto; min-height:auto;"> 自动刷新</label>
            <input id="logSearch" placeholder="筛选账号、模型、接口或状态码">
            <select id="logFilter" aria-label="日志状态筛选">
              <option value="all">全部状态</option>
              <option value="success">仅成功</option>
              <option value="error">仅失败</option>
              <option value="stream">仅流式</option>
              <option value="nonstream">仅非流式</option>
            </select>
          </div>
          <div id="logStreamTable"></div>
          <div class="message" id="logMessage"></div>
        </section>
      </section>

      <section class="page" id="page-models">
        <div class="grid-2">
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>模型与能力</h2>
                <p class="panel-sub">按账号刷新 DevEco 模型配置，展示模型 ID、状态、延迟和错误摘要。</p>
              </div>
              <div class="top-actions">
                <button id="refreshModels">刷新能力</button>
                <button id="loadModels" class="secondary">读取缓存</button>
              </div>
            </div>
            <label for="modelAccountTarget">刷新范围</label>
            <select id="modelAccountTarget"><option value="">全部账号</option></select>
            <div id="modelCapabilities" style="margin-top: 10px;"></div>
            <div class="message" id="modelMessage"></div>
          </section>
          <section class="panel">
            <div class="panel-head">
              <div>
                <h2>账号调度策略</h2>
                <p class="panel-sub">控制 /v1/models 与 /v1/chat/completions 如何选择账号。</p>
              </div>
            </div>
            <label for="accountStrategy">当前策略</label>
            <select id="accountStrategy">
              <option value="active_only">仅当前启用账号</option>
              <option value="round_robin">多账号轮询</option>
              <option value="failover">失败自动切换</option>
            </select>
            <div class="toolbar">
              <button id="saveStrategy">保存策略</button>
            </div>
            <div class="health-list">
              <div class="health-item"><span>active_only</span><span class="pill">兼容旧行为</span></div>
              <div class="health-item"><span>round_robin</span><span class="pill warn">按请求轮询健康账号</span></div>
              <div class="health-item"><span>failover</span><span class="pill warn">失败后尝试备用账号</span></div>
            </div>
            <div class="message" id="strategyMessage"></div>
          </section>
        </div>
      </section>

      <section class="page" id="page-checks">
        <div class="metrics">
          <div class="metric"><div class="label">连通正常</div><div class="value" id="cOk">0</div><div class="hint">最近一次检测成功</div></div>
          <div class="metric"><div class="label">连通失败</div><div class="value" id="cFail">0</div><div class="hint">展示脱敏错误摘要</div></div>
          <div class="metric"><div class="label">未检测</div><div class="value" id="cUnchecked">0</div><div class="hint">不会自动发起网络请求</div></div>
          <div class="metric"><div class="label">账号总数</div><div class="value" id="cTotal">0</div><div class="hint">本地账号记录</div></div>
          <div class="metric"><div class="label">最近检测</div><div class="value" id="cLatest">-</div><div class="hint">按 checked_at 计算</div></div>
        </div>
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>连通性检测</h2>
              <p class="panel-sub">检测会请求 DevEco 模型配置接口；只有点击按钮才会执行。</p>
            </div>
            <div class="top-actions">
              <button id="checkAll">批量检测</button>
              <button id="refreshChecks" class="secondary">刷新状态</button>
            </div>
          </div>
          <div class="toolbar">
            <input id="checkSearch" placeholder="搜索账号、HTTP 状态或错误摘要">
            <select id="checkFilter" aria-label="连通性筛选">
              <option value="all">全部账号</option>
              <option value="ok">连通正常</option>
              <option value="fail">连通失败</option>
              <option value="unchecked">未检测</option>
            </select>
          </div>
          <div id="checkTable"></div>
          <div class="message" id="checkMessage"></div>
        </section>
      </section>

      <section class="page" id="page-settings">
        <div class="grid-3">
          <section class="panel">
            <div class="panel-head"><div><h2>认证边界</h2><p class="panel-sub">管理 API 与代理 API 共用 Bearer 验证。</p></div></div>
            <div id="settingsAuth" class="health-list"></div>
          </section>
          <section class="panel">
            <div class="panel-head"><div><h2>持久化文件</h2><p class="panel-sub">只显示文件是否存在，不读取或展示内容。</p></div></div>
            <div id="credentialFiles" class="file-grid"></div>
          </section>
          <section class="panel">
            <div class="panel-head"><div><h2>数据策略</h2><p class="panel-sub">控制台遵守最小展示原则。</p></div></div>
            <div class="health-list">
              <div class="health-item"><span>聊天内容</span><span class="pill ok">不保存</span></div>
              <div class="health-item"><span>请求统计</span><span class="pill warn">仅元数据</span></div>
              <div class="health-item"><span>凭证展示</span><span class="pill ok">禁止展示</span></div>
              <div class="health-item"><span>网络检测</span><span class="pill warn">手动触发</span></div>
            </div>
          </section>
        </div>
        <div class="grid-2" style="margin-top: 14px;">
          <section class="panel">
            <div class="panel-head"><div><h2>运行路径</h2><p class="panel-sub">用于确认容器卷或本地凭据目录是否挂载正确。</p></div></div>
            <div id="settingsCred" class="mono muted"></div>
          </section>
          <section class="panel">
            <div class="panel-head"><div><h2>本地调用示例</h2><p class="panel-sub">使用占位符，不包含真实密钥。</p></div></div>
            <pre class="mono">curl http://127.0.0.1:8000/v1/models \\
  -H "Authorization: Bearer &lt;HM_API_KEY&gt;"</pre>
          </section>
          <section class="panel">
            <div class="panel-head"><div><h2>接入配置</h2><p class="panel-sub">一键复制 OpenAI SDK 与 curl 使用文档，始终使用密钥占位符。</p></div></div>
            <div class="toolbar">
              <button id="copyPythonConfig" class="secondary">复制 Python SDK</button>
              <button id="copyJsConfig" class="secondary">复制 JavaScript SDK</button>
              <button id="copyModelsCurl" class="secondary">复制模型 curl</button>
              <button id="copyChatCurl" class="secondary">复制聊天 curl</button>
            </div>
            <pre id="integrationPreview" class="mono"></pre>
            <div class="message" id="integrationMessage"></div>
          </section>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = {
      overview: null,
      accounts: [],
      usage: null,
      loginUrl: "",
      selectedAccountId: null,
      accountFilter: "all",
      accountSearch: "",
      requestSearch: "",
      requestFilter: "all",
      logs: [],
      logSearch: "",
      logFilter: "all",
      autoRefreshLogs: false,
      logTimer: null,
      modelResults: [],
      checkSearch: "",
      checkFilter: "all",
    };
    const titles = {
      overview: ["总览", "集中查看服务就绪度、当前账号、请求统计和最近调用。"],
      accounts: ["账号工作台", "管理多个 DevEco 账号，并通过登录向导保存或覆盖账号。"],
      usage: ["请求透视", "按趋势、模型、账号和最近流水检查本地请求元数据。"],
      logs: ["日志流", "自动刷新最近请求流水，并快速定位到最新记录。"],
      models: ["模型与能力", "查看账号模型能力、刷新可用模型并配置账号调度策略。"],
      checks: ["连通性检测", "手动检测账号是否能访问 DevEco 模型配置，并查看脱敏错误摘要。"],
      settings: ["配置与安全", "查看认证、凭据目录、持久化文件和安全边界。"],
    };
    const $ = id => document.getElementById(id);

    function pct(value) {
      return `${Math.round((Number(value) || 0) * 100)}%`;
    }
    function esc(value) {
      const map = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
      return String(value ?? "").replace(/[&<>"']/g, ch => map[ch]);
    }
    function text(value, fallback = "-") {
      const normalized = value === null || value === undefined || value === "" ? fallback : value;
      return esc(normalized);
    }
    function shortTime(value) {
      if (!value) return "-";
      return String(value).replace("T", " ").replace("Z", "");
    }
    function pill(label, kind = "") {
      return `<span class="pill ${kind}">${esc(label)}</span>`;
    }
    function setMessage(id, content, ok) {
      const el = $(id);
      el.textContent = content;
      el.className = ok ? "message ok" : "message err";
    }
    function setLoadState(content, kind = "info") {
      const el = $("loadState");
      if (!content) {
        el.textContent = "";
        el.className = "banner";
        return;
      }
      el.textContent = content;
      el.className = kind === "err" ? "banner active err" : "banner active";
    }
    function table(rows, columns) {
      if (!rows.length) return '<div class="empty">暂无数据</div>';
      return `<div class="table-wrap"><table class="table"><thead><tr>${columns.map(c => `<th>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${c.render(row)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    function accountHealth(account) {
      if (!account.connectivity) return "unchecked";
      return account.connectivity.success ? "ok" : "fail";
    }
    function accountName(accountId) {
      const account = state.accounts.find(item => item.account_id === accountId);
      return account ? (account.display_name || account.user_name || account.account_id) : (accountId || "未关联账号");
    }
    function accountStatus(account) {
      if (account.is_active) return pill("当前启用", "ok");
      return pill("备用");
    }
    function healthPill(account) {
      const health = accountHealth(account);
      if (health === "ok") return pill("连通正常", "ok");
      if (health === "fail") return pill("连通失败", "bad");
      return pill("未检测", "warn");
    }
    function tagPills(tags) {
      const items = Array.isArray(tags) ? tags : [];
      if (!items.length) return pill("未加标签");
      return items.map(tag => pill(tag, "warn")).join("");
    }
    function baseUrl() {
      return `${window.location.origin}`;
    }
    function integrationSnippet(kind) {
      const url = baseUrl();
      const model = "GLM-5.1";
      if (kind === "python") {
        return `from openai import OpenAI

client = OpenAI(
    api_key="<HM_API_KEY>",
    base_url="${url}/v1",
)

response = client.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "你好"}],
)
print(response.choices[0].message.content)`;
      }
      if (kind === "js") {
        return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "<HM_API_KEY>",
  baseURL: "${url}/v1",
});

const response = await client.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "你好" }],
});
console.log(response.choices[0].message.content);`;
      }
      if (kind === "models") {
        return `curl ${url}/v1/models \\
  -H "Authorization: Bearer <HM_API_KEY>"`;
      }
      return `curl ${url}/v1/chat/completions \\
  -H "Authorization: Bearer <HM_API_KEY>" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"${model}","messages":[{"role":"user","content":"你好"}]}'`;
    }
    async function copyText(value) {
      if (!value) return;
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    async function api(path, options = {}) {
      const headers = Object.assign({"Content-Type": "application/json"}, options.headers || {});
      const token = window.sessionStorage.getItem("hmApiBearer") || "";
      if (token) headers.Authorization = `Bearer ${token}`;
      let response = await fetch(path, Object.assign({}, options, {headers}));
      if (response.status === 401) {
        const tokenInput = window.prompt("请输入 API Key");
        if (tokenInput) {
          window.sessionStorage.setItem("hmApiBearer", tokenInput);
          headers.Authorization = `Bearer ${tokenInput}`;
          response = await fetch(path, Object.assign({}, options, {headers}));
        }
      }
      return response;
    }
    async function readJson(response) {
      try {
        return await response.json();
      } catch (error) {
        return {};
      }
    }
    function renderStatusBadges() {
      const overview = state.overview || {};
      const files = overview.credential_files || {};
      $("badgeLogin").textContent = overview.active_account ? "已登录" : "未登录";
      $("badgeAuth").textContent = overview.auth_enabled ? "Bearer 已启用" : "Bearer 未启用";
      $("badgeCred").textContent = overview.credential_dir && overview.credential_dir.exists ? "凭据目录正常" : "凭据目录待创建";
      $("badgePersist").textContent = files.accounts_json ? "账号文件已持久化" : "账号文件未创建";
    }
    function renderMetrics() {
      const usage = state.usage || {};
      const ok = state.accounts.filter(account => accountHealth(account) === "ok").length;
      const fail = state.accounts.filter(account => accountHealth(account) === "fail").length;
      const unchecked = state.accounts.filter(account => accountHealth(account) === "unchecked").length;
      $("mToday").textContent = usage.today_requests || 0;
      $("mSuccess").textContent = pct(usage.success_rate);
      $("mSuccessHint").textContent = `${usage.success_count || 0} 成功 / ${usage.error_count || 0} 失败`;
      $("mLatency").textContent = `${usage.average_latency_ms || 0}ms`;
      $("mAccounts").textContent = state.accounts.length;
      $("mAccountHint").textContent = `${ok} 正常 / ${fail} 失败 / ${unchecked} 未检测`;
      $("mErrors").textContent = usage.error_count || 0;
    }
    function renderReadiness() {
      const overview = state.overview || {};
      const files = overview.credential_files || {};
      const items = [
        ["管理 API", true, "当前页面已成功读取 overview 数据"],
        ["API Bearer 认证", overview.auth_enabled, overview.auth_enabled ? "已启用" : "未启用，适合本机测试但不适合暴露服务"],
        ["凭据目录", Boolean(overview.credential_dir && overview.credential_dir.exists), overview.credential_dir ? overview.credential_dir.path : "-"],
        ["账号文件", Boolean(files.accounts_json), "accounts.json"],
        ["当前启用账号", Boolean(overview.active_account), overview.active_account ? overview.active_account.display_name : "暂无启用账号"],
        ["使用统计文件", Boolean(files.usage_jsonl), "usage.jsonl"],
      ];
      $("readinessList").innerHTML = items.map(([label, good, detail]) => `
        <div class="health-item">
          <span><strong>${esc(label)}</strong><br><span class="muted">${esc(detail)}</span></span>
          ${good ? pill("正常", "ok") : pill("待处理", "warn")}
        </div>
      `).join("");
    }
    function renderActive() {
      const active = state.overview && state.overview.active_account;
      $("activeAccount").innerHTML = active
        ? `<div class="account-main">
            <div class="account-title">${esc(active.display_name)} ${accountStatus(active)} ${healthPill(active)}</div>
            <span class="muted">${esc(active.user_name || active.user_id || "未知用户")}</span>
            <span class="mono">${esc(active.account_id)}</span>
            <div class="pill-row">${pill(`创建：${shortTime(active.created_at)}`)}${pill(`更新：${shortTime(active.updated_at)}`)}</div>
          </div>`
        : '<div class="empty">暂无启用账号，请在「账号工作台」中新增或启用账号。</div>';
    }
    function renderTrend(targetId) {
      const trend = (state.usage && state.usage.trend) || [];
      if (!trend.length) {
        $(targetId).innerHTML = '<div class="empty">暂无趋势数据。</div>';
        return;
      }
      const max = Math.max(1, ...trend.map(item => Number(item.requests) || 0));
      $(targetId).innerHTML = trend.map(item => {
        const requests = Number(item.requests) || 0;
        const width = Math.max(3, Math.round((requests / max) * 100));
        return `<div class="bar-row">
          <span>${esc(item.date)}</span>
          <span class="bar-track"><span class="bar" style="width:${width}%"></span></span>
          <strong>${requests}</strong>
        </div>`;
      }).join("");
    }
    function renderRecentOverview() {
      const recent = ((state.usage && state.usage.recent) || []).slice(0, 6);
      $("recentRequests").innerHTML = table(recent, [
        {label: "时间", render: row => text(shortTime(row.timestamp))},
        {label: "接口", render: row => text(row.endpoint)},
        {label: "状态", render: row => row.success ? pill("成功", "ok") : pill(`失败 ${row.status_code || ""}`, "bad")},
        {label: "延迟", render: row => `${text(row.latency_ms || 0)}ms`},
      ]);
    }
    function renderAccountTargetOptions() {
      const select = $("accountTarget");
      const current = select.value;
      const options = ['<option value="">新增账号</option>'].concat(
        state.accounts.map(account => `<option value="${esc(account.account_id)}">覆盖：${esc(account.display_name || account.user_name || account.account_id)}</option>`)
      );
      select.innerHTML = options.join("");
      if (state.accounts.some(account => account.account_id === current)) {
        select.value = current;
      }
    }
    function renderModelAccountOptions() {
      const select = $("modelAccountTarget");
      const current = select.value;
      const options = ['<option value="">全部账号</option>'].concat(
        state.accounts.map(account => `<option value="${esc(account.account_id)}">${esc(account.display_name || account.user_name || account.account_id)}</option>`)
      );
      select.innerHTML = options.join("");
      if (state.accounts.some(account => account.account_id === current)) {
        select.value = current;
      }
    }
    function filteredAccounts() {
      const query = state.accountSearch.trim().toLowerCase();
      return state.accounts.filter(account => {
        const matchesQuery = !query || [
          account.display_name,
          account.user_name,
          account.user_id,
          account.account_id,
          account.note,
          ...(account.tags || []),
        ].some(value => String(value || "").toLowerCase().includes(query));
        const health = accountHealth(account);
        const matchesFilter =
          state.accountFilter === "all" ||
          (state.accountFilter === "active" && account.is_active) ||
          state.accountFilter === health;
        return matchesQuery && matchesFilter;
      });
    }
    function renderAccounts() {
      renderAccountTargetOptions();
      if (!state.selectedAccountId && state.accounts.length) {
        const active = state.accounts.find(account => account.is_active);
        state.selectedAccountId = (active || state.accounts[0]).account_id;
      }
      const rows = filteredAccounts();
      if (!rows.length) {
        $("accountsTable").innerHTML = '<div class="empty">没有匹配的账号。可以清空搜索或切换筛选条件。</div>';
        renderAccountDetail();
        return;
      }
      $("accountsTable").innerHTML = `<div class="account-list">${rows.map(account => `
        <div class="account-row ${account.account_id === state.selectedAccountId ? "selected" : ""}" data-action="select" data-id="${esc(account.account_id)}">
          <div class="account-main">
            <div class="account-title">${esc(account.display_name || "DevEco 账号")} ${accountStatus(account)} ${healthPill(account)}</div>
            <span class="muted">${esc(account.user_name || account.user_id || "未知用户")}</span>
            <span class="pill-row">${tagPills(account.tags)}</span>
            <span class="mono">${esc(account.account_id)}</span>
          </div>
          <div class="row-actions">
            <button class="secondary" data-action="activate" data-id="${esc(account.account_id)}" ${account.is_active ? "disabled" : ""}>启用</button>
            <button class="secondary" data-action="rename" data-id="${esc(account.account_id)}">重命名</button>
            <button class="secondary" data-action="check" data-id="${esc(account.account_id)}">检测</button>
            <button class="danger" data-action="delete" data-id="${esc(account.account_id)}">删除</button>
          </div>
        </div>
      `).join("")}</div>`;
      renderAccountDetail();
    }
    function renderAccountDetail() {
      const account = state.accounts.find(item => item.account_id === state.selectedAccountId);
      if (!account) {
        $("accountDetail").innerHTML = '<div class="empty">请选择一个账号查看详情。</div>';
        return;
      }
      const check = account.connectivity || {};
      $("accountDetail").innerHTML = `
        <div class="account-main">
          <div class="account-title">${esc(account.display_name || "DevEco 账号")} ${accountStatus(account)} ${healthPill(account)}</div>
          <span class="muted">${esc(account.user_name || account.user_id || "未知用户")}</span>
          <span class="pill-row">${tagPills(account.tags)}</span>
          <span class="mono">${esc(account.account_id)}</span>
        </div>
        <div class="detail-grid">
          <div class="detail-item"><span>创建时间</span>${text(shortTime(account.created_at))}</div>
          <div class="detail-item"><span>更新时间</span>${text(shortTime(account.updated_at))}</div>
          <div class="detail-item"><span>最近使用</span>${text(shortTime(account.last_used_at))}</div>
          <div class="detail-item"><span>最近检测</span>${text(shortTime(check.checked_at))}</div>
          <div class="detail-item"><span>HTTP 状态</span>${text(check.status_code)}</div>
          <div class="detail-item"><span>模型数</span>${text(check.model_count)}</div>
          <div class="detail-item"><span>延迟</span>${check.latency_ms === undefined || check.latency_ms === null ? "-" : `${esc(check.latency_ms)}ms`}</div>
          <div class="detail-item"><span>错误摘要</span>${text(check.error)}</div>
        </div>
        <label for="profileDisplayName">显示名</label>
        <input id="profileDisplayName" value="${esc(account.display_name || "")}">
        <label for="profileTags">账号标签</label>
        <input id="profileTags" value="${esc((account.tags || []).join(", "))}" placeholder="例如：生产, 主力">
        <label for="profileNote">备注</label>
        <textarea id="profileNote" spellcheck="false" placeholder="仅保存本地说明，不参与上游请求">${esc(account.note || "")}</textarea>
        <button data-action="saveProfile" data-id="${esc(account.account_id)}">保存标签与备注</button>
      `;
    }
    function renderUsage() {
      const usage = state.usage || {};
      $("uTotal").textContent = usage.total_requests || 0;
      $("uError").textContent = pct(usage.error_rate);
      $("uErrorHint").textContent = `${usage.error_count || 0} 失败 / ${usage.success_count || 0} 成功`;
      $("uStream").textContent = `${usage.non_streaming_count || 0}/${usage.streaming_count || 0}`;
      $("uToken").textContent = usage.token_usage ? String(usage.token_usage.total_tokens || "已记录") : "上游未返回";
      $("uRecent").textContent = ((usage.recent || []).length);
      renderTrend("trendStats");
      const modelRows = Object.entries(usage.by_model || {}).map(([model, value]) => Object.assign({model}, value));
      $("modelStats").innerHTML = table(modelRows, [
        {label: "模型", render: row => text(row.model)},
        {label: "请求", render: row => text(row.requests)},
        {label: "成功/失败", render: row => `${text(row.success || 0)} / ${text(row.errors || 0)}`},
        {label: "平均延迟", render: row => `${text(row.average_latency_ms || 0)}ms`},
      ]);
      const accountRows = Object.entries(usage.by_account || {}).map(([account_id, value]) => Object.assign({account_id, account_name: accountName(account_id)}, value));
      $("accountUsageStats").innerHTML = table(accountRows, [
        {label: "账号", render: row => `${text(row.account_name)}<br><span class="mono muted">${text(row.account_id)}</span>`},
        {label: "请求", render: row => text(row.requests)},
        {label: "成功/失败", render: row => `${text(row.success || 0)} / ${text(row.errors || 0)}`},
        {label: "平均延迟", render: row => `${text(row.average_latency_ms || 0)}ms`},
      ]);
      renderRecentUsageTable();
    }
    function renderRecentUsageTable() {
      const query = state.requestSearch.trim().toLowerCase();
      const recent = ((state.usage && state.usage.recent) || []).filter(row => {
        const matchesFilter =
          state.requestFilter === "all" ||
          (state.requestFilter === "success" && row.success) ||
          (state.requestFilter === "error" && !row.success) ||
          (state.requestFilter === "stream" && row.stream);
        const haystack = [
          row.timestamp,
          row.endpoint,
          row.model,
          row.status_code,
          row.account_id,
          accountName(row.account_id),
        ].join(" ").toLowerCase();
        return matchesFilter && (!query || haystack.includes(query));
      });
      $("recentUsageTable").innerHTML = table(recent, [
        {label: "时间", render: row => text(shortTime(row.timestamp))},
        {label: "接口", render: row => text(row.endpoint)},
        {label: "账号", render: row => text(accountName(row.account_id))},
        {label: "模型", render: row => text(row.model || "上游未返回")},
        {label: "状态", render: row => row.success ? pill(`成功 ${row.status_code || ""}`, "ok") : pill(`失败 ${row.status_code || ""}`, "bad")},
        {label: "模式", render: row => row.stream ? pill("流式") : pill("非流式")},
        {label: "延迟", render: row => `${text(row.latency_ms || 0)}ms`},
      ]);
    }
    function filteredLogs() {
      const query = state.logSearch.trim().toLowerCase();
      return state.logs.filter(row => {
        const matchesFilter =
          state.logFilter === "all" ||
          (state.logFilter === "success" && row.success) ||
          (state.logFilter === "error" && !row.success) ||
          (state.logFilter === "stream" && row.stream) ||
          (state.logFilter === "nonstream" && !row.stream);
        const haystack = [
          row.timestamp,
          row.endpoint,
          row.model,
          row.status_code,
          row.account_id,
          accountName(row.account_id),
        ].join(" ").toLowerCase();
        return matchesFilter && (!query || haystack.includes(query));
      });
    }
    function renderLogs() {
      const logs = filteredLogs();
      $("logTotal").textContent = state.logTotal || state.logs.length || 0;
      $("logShown").textContent = logs.length;
      $("logAutoState").textContent = state.autoRefreshLogs ? "开启" : "关闭";
      $("logStrategy").textContent = (state.overview && state.overview.account_strategy) || "active_only";
      const latest = state.logs[0];
      $("logLatestState").textContent = latest ? (latest.success ? "成功" : "失败") : "-";
      $("logStreamTable").innerHTML = table(logs, [
        {label: "时间", render: row => text(shortTime(row.timestamp))},
        {label: "账号", render: row => text(accountName(row.account_id))},
        {label: "接口", render: row => text(row.endpoint)},
        {label: "模型", render: row => text(row.model || "上游未返回")},
        {label: "状态", render: row => row.success ? pill(`成功 ${row.status_code || ""}`, "ok") : pill(`失败 ${row.status_code || ""}`, "bad")},
        {label: "模式", render: row => row.stream ? pill("流式") : pill("非流式")},
        {label: "延迟", render: row => `${text(row.latency_ms || 0)}ms`},
      ]);
    }
    function scrollLatestLog() {
      const table = $("logStreamTable");
      if (table) table.scrollIntoView({block: "start", behavior: "smooth"});
    }
    function renderModels() {
      renderModelAccountOptions();
      $("accountStrategy").value = (state.overview && state.overview.account_strategy) || "active_only";
      const rows = state.modelResults.length
        ? state.modelResults
        : state.accounts.map(account => ({
            account_id: account.account_id,
            account_name: account.display_name || account.user_name || account.account_id,
            success: account.connectivity && account.connectivity.success,
            status_code: account.connectivity && account.connectivity.status_code,
            latency_ms: account.connectivity && account.connectivity.latency_ms,
            checked_at: account.connectivity && account.connectivity.checked_at,
            model_count: account.connectivity && account.connectivity.model_count,
            models: [],
            error: account.connectivity && account.connectivity.error,
          }));
      $("modelCapabilities").innerHTML = table(rows, [
        {label: "账号", render: row => `${text(row.account_name)}<br><span class="mono muted">${text(row.account_id)}</span>`},
        {label: "结果", render: row => row.success ? pill("可用", "ok") : (row.checked_at ? pill("异常", "bad") : pill("未刷新", "warn"))},
        {label: "HTTP", render: row => text(row.status_code)},
        {label: "延迟", render: row => row.latency_ms === undefined || row.latency_ms === null ? "-" : `${text(row.latency_ms)}ms`},
        {label: "最近检测", render: row => text(shortTime(row.checked_at))},
        {label: "模型", render: row => (row.models || []).length
          ? (row.models || []).map(model => `<button class="secondary" data-action="copyModel" data-id="${esc(model.id)}">${esc(model.id)}</button>`).join(" ")
          : text(row.model_count || 0)},
        {label: "错误摘要", render: row => text(row.error)},
      ]);
    }
    function renderIntegration() {
      $("integrationPreview").textContent = integrationSnippet("python");
    }
    function renderChecks() {
      const ok = state.accounts.filter(account => accountHealth(account) === "ok").length;
      const fail = state.accounts.filter(account => accountHealth(account) === "fail").length;
      const unchecked = state.accounts.filter(account => accountHealth(account) === "unchecked").length;
      const latest = state.accounts
        .map(account => account.connectivity && account.connectivity.checked_at)
        .filter(Boolean)
        .sort()
        .pop();
      $("cOk").textContent = ok;
      $("cFail").textContent = fail;
      $("cUnchecked").textContent = unchecked;
      $("cTotal").textContent = state.accounts.length;
      $("cLatest").textContent = latest ? shortTime(latest).slice(5, 16) : "-";
      const query = state.checkSearch.trim().toLowerCase();
      const rows = state.accounts.filter(account => {
        const health = accountHealth(account);
        const check = account.connectivity || {};
        const matchesFilter = state.checkFilter === "all" || state.checkFilter === health;
        const haystack = [
          account.display_name,
          account.user_name,
          account.user_id,
          account.account_id,
          check.status_code,
          check.error,
        ].join(" ").toLowerCase();
        return matchesFilter && (!query || haystack.includes(query));
      });
      $("checkTable").innerHTML = table(rows, [
        {label: "账号", render: account => `<strong>${text(account.display_name)}</strong><br><span class="mono muted">${text(account.account_id)}</span>`},
        {label: "结果", render: account => healthPill(account)},
        {label: "最近检测", render: account => text(shortTime(account.connectivity && account.connectivity.checked_at))},
        {label: "HTTP", render: account => text(account.connectivity && account.connectivity.status_code)},
        {label: "延迟", render: account => account.connectivity ? `${text(account.connectivity.latency_ms)}ms` : "-"},
        {label: "模型数", render: account => text(account.connectivity && account.connectivity.model_count)},
        {label: "错误摘要", render: account => text(account.connectivity && account.connectivity.error)},
        {label: "操作", render: account => `<div class="row-actions"><button class="secondary" data-action="check" data-id="${esc(account.account_id)}">检测</button></div>`},
      ]);
    }
    function renderSettings() {
      if (!state.overview) return;
      const overview = state.overview;
      const files = overview.credential_files || {};
      $("settingsAuth").innerHTML = `
        <div class="health-item"><span>Bearer 认证</span>${overview.auth_enabled ? pill("已启用", "ok") : pill("未启用", "warn")}</div>
        <div class="health-item"><span>浏览器缓存 API Key</span>${window.sessionStorage.getItem("hmApiBearer") ? pill("本会话已保存", "warn") : pill("未保存")}</div>
        <div class="health-item"><span>/ui 页面</span>${pill("可公开加载", "warn")}</div>
        <div class="health-item"><span>/ui/api/*</span>${overview.auth_enabled ? pill("需要 Bearer", "ok") : pill("未加锁", "warn")}</div>
      `;
      const fileLabels = {
        accounts_json: "accounts.json",
        usage_jsonl: "usage.jsonl",
        auth_json: "auth.json",
        token_enc: "token.enc",
        kek: ".kek",
      };
      $("credentialFiles").innerHTML = Object.entries(fileLabels).map(([key, label]) => `
        <div class="file-item">
          <strong>${esc(label)}</strong>
          ${files[key] ? pill("存在", "ok") : pill("未创建", "warn")}
        </div>
      `).join("");
      $("settingsCred").textContent = overview.credential_dir ? overview.credential_dir.path : "-";
    }
    function renderAll() {
      renderStatusBadges();
      renderMetrics();
      renderReadiness();
      renderActive();
      renderTrend("overviewTrend");
      renderRecentOverview();
      renderAccounts();
      renderUsage();
      renderLogs();
      renderModels();
      renderChecks();
      renderSettings();
      renderIntegration();
    }
    async function loadOverview() {
      setLoadState("正在读取管理数据...");
      try {
        const response = await api("/ui/api/overview", {method: "GET", headers: {}});
        if (!response.ok) {
          const message = response.status === 401
            ? "需要正确的 API Key 才能读取管理数据。"
            : `管理数据读取失败：HTTP ${response.status}`;
          setLoadState(message, "err");
          $("badgeLogin").textContent = "账号状态未知";
          $("badgeAuth").textContent = response.status === 401 ? "API 认证未通过" : "认证状态未知";
          $("badgeCred").textContent = "凭据目录未知";
          $("badgePersist").textContent = "持久化状态未知";
          return;
        }
        state.overview = await response.json();
        state.usage = state.overview.usage || {};
        state.accounts = state.overview.accounts || [];
        const selectedStillExists = state.accounts.some(account => account.account_id === state.selectedAccountId);
        if (!selectedStillExists) {
          const active = state.accounts.find(account => account.is_active);
          state.selectedAccountId = (active || state.accounts[0] || {}).account_id || null;
        }
        setLoadState("");
        renderAll();
      } catch (error) {
        setLoadState(`管理数据读取失败：${error.message || "网络错误"}`, "err");
      }
    }
    async function loadAccounts() {
      const response = await api("/ui/api/accounts", {method: "GET", headers: {}});
      if (!response.ok) return;
      const data = await readJson(response);
      state.accounts = data.accounts || [];
      renderAccounts();
      renderChecks();
      renderAccountTargetOptions();
      renderModelAccountOptions();
    }
    async function loadLogs(keepPosition = false) {
      const response = await api("/ui/api/usage/events?limit=100", {method: "GET", headers: {}});
      if (!response.ok) {
        setMessage("logMessage", "日志读取失败", false);
        return;
      }
      const data = await readJson(response);
      state.logs = data.events || [];
      state.logTotal = data.total || state.logs.length;
      renderLogs();
      if (!keepPosition) scrollLatestLog();
    }
    async function loadModels() {
      const response = await api("/ui/api/models", {method: "GET", headers: {}});
      if (!response.ok) {
        setMessage("modelMessage", "模型能力缓存读取失败", false);
        return;
      }
      state.modelResults = [];
      renderModels();
    }
    async function refreshModels() {
      setMessage("modelMessage", "正在刷新模型能力...", true);
      const response = await api("/ui/api/models/refresh", {
        method: "POST",
        body: JSON.stringify({account_id: $("modelAccountTarget").value || null}),
      });
      const data = await readJson(response);
      if (!response.ok) {
        setMessage("modelMessage", data.detail || "模型能力刷新失败", false);
        return;
      }
      state.modelResults = data.results || [];
      renderModels();
      setMessage("modelMessage", "模型能力刷新完成", true);
      await loadOverview();
    }
    async function saveStrategy() {
      const response = await api("/ui/api/account-strategy", {
        method: "PUT",
        body: JSON.stringify({strategy: $("accountStrategy").value}),
      });
      const data = await readJson(response);
      if (!response.ok) {
        setMessage("strategyMessage", data.detail || "策略保存失败", false);
        return;
      }
      if (state.overview) state.overview.account_strategy = data.strategy;
      setMessage("strategyMessage", "账号调度策略已保存", true);
      renderModels();
      renderLogs();
    }
    async function activateAccount(id) {
      await api(`/ui/api/accounts/${encodeURIComponent(id)}/activate`, {method: "POST"});
      state.selectedAccountId = id;
      await loadOverview();
    }
    async function renameAccount(id) {
      const displayName = window.prompt("新的账号显示名");
      if (!displayName || !displayName.trim()) return;
      await api(`/ui/api/accounts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({display_name: displayName.trim()}),
      });
      state.selectedAccountId = id;
      await loadOverview();
    }
    async function saveAccountProfile(id) {
      const tags = $("profileTags").value
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);
      const response = await api(`/ui/api/accounts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          display_name: $("profileDisplayName").value,
          tags,
          note: $("profileNote").value,
        }),
      });
      setMessage("accountMessage", response.ok ? "账号标签与备注已保存" : "账号标签与备注保存失败", response.ok);
      state.selectedAccountId = id;
      await loadOverview();
    }
    async function deleteAccount(id) {
      if (!window.confirm("确认删除这个账号？")) return;
      await api(`/ui/api/accounts/${encodeURIComponent(id)}`, {method: "DELETE"});
      if (state.selectedAccountId === id) state.selectedAccountId = null;
      await loadOverview();
    }
    async function checkOne(id) {
      setMessage("checkMessage", "正在检测账号连通性...", true);
      const response = await api(`/ui/api/accounts/${encodeURIComponent(id)}/check`, {method: "POST"});
      const data = await readJson(response);
      const ok = Boolean(data.result && data.result.success);
      setMessage("checkMessage", response.ok ? (ok ? "检测完成：连通正常" : "检测完成：连通失败") : "检测请求失败", response.ok && ok);
      state.selectedAccountId = id;
      await loadOverview();
    }
    document.querySelectorAll(".nav button").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".nav button").forEach(item => item.classList.remove("active"));
        document.querySelectorAll(".page").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        const tab = button.dataset.tab;
        $(`page-${tab}`).classList.add("active");
        $("pageTitle").textContent = titles[tab][0];
        $("pageSubtitle").textContent = titles[tab][1];
      });
    });
    document.addEventListener("click", event => {
      const target = event.target.closest("[data-action]");
      if (!target) return;
      const id = target.dataset.id;
      if (!id) return;
      if (target.dataset.action === "select") {
        state.selectedAccountId = id;
        renderAccounts();
        return;
      }
      if (target.dataset.action === "activate") activateAccount(id);
      if (target.dataset.action === "rename") renameAccount(id);
      if (target.dataset.action === "saveProfile") saveAccountProfile(id);
      if (target.dataset.action === "check") checkOne(id);
      if (target.dataset.action === "copyModel") {
        copyText(id);
        setMessage("modelMessage", "模型 ID 已复制", true);
      }
      if (target.dataset.action === "delete") deleteAccount(id);
    });
    $("reloadAll").addEventListener("click", loadOverview);
    $("clearBearer").addEventListener("click", () => {
      window.sessionStorage.removeItem("hmApiBearer");
      renderSettings();
      setLoadState("已清除本浏览器会话里的 API Key。");
    });
    $("refreshAccounts").addEventListener("click", loadAccounts);
    $("refreshChecks").addEventListener("click", loadOverview);
    $("accountSearch").addEventListener("input", event => {
      state.accountSearch = event.target.value;
      renderAccounts();
    });
    $("accountFilters").addEventListener("click", event => {
      const button = event.target.closest("button[data-account-filter]");
      if (!button) return;
      state.accountFilter = button.dataset.accountFilter;
      $("accountFilters").querySelectorAll("button").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      renderAccounts();
    });
    $("requestSearch").addEventListener("input", event => {
      state.requestSearch = event.target.value;
      renderRecentUsageTable();
    });
    $("requestFilter").addEventListener("change", event => {
      state.requestFilter = event.target.value;
      renderRecentUsageTable();
    });
    $("refreshLogs").addEventListener("click", () => loadLogs(false));
    $("scrollLatestLog").addEventListener("click", scrollLatestLog);
    $("autoRefreshLogs").addEventListener("change", event => {
      state.autoRefreshLogs = event.target.checked;
      if (state.logTimer) {
        window.clearInterval(state.logTimer);
        state.logTimer = null;
      }
      if (state.autoRefreshLogs) {
        state.logTimer = window.setInterval(() => loadLogs(true), 5000);
        loadLogs(false);
      }
      renderLogs();
    });
    $("logSearch").addEventListener("input", event => {
      state.logSearch = event.target.value;
      renderLogs();
    });
    $("logFilter").addEventListener("change", event => {
      state.logFilter = event.target.value;
      renderLogs();
    });
    $("loadModels").addEventListener("click", loadModels);
    $("refreshModels").addEventListener("click", refreshModels);
    $("saveStrategy").addEventListener("click", saveStrategy);
    function copyIntegration(kind) {
      const snippet = integrationSnippet(kind);
      $("integrationPreview").textContent = snippet;
      copyText(snippet);
      setMessage("integrationMessage", "接入配置已复制", true);
    }
    $("copyPythonConfig").addEventListener("click", () => copyIntegration("python"));
    $("copyJsConfig").addEventListener("click", () => copyIntegration("js"));
    $("copyModelsCurl").addEventListener("click", () => copyIntegration("models"));
    $("copyChatCurl").addEventListener("click", () => copyIntegration("chat"));
    $("checkSearch").addEventListener("input", event => {
      state.checkSearch = event.target.value;
      renderChecks();
    });
    $("checkFilter").addEventListener("change", event => {
      state.checkFilter = event.target.value;
      renderChecks();
    });
    $("checkAll").addEventListener("click", async () => {
      setMessage("checkMessage", "正在批量检测账号连通性...", true);
      const response = await api("/ui/api/accounts/check-all", {method: "POST"});
      setMessage("checkMessage", response.ok ? "批量检测完成" : "批量检测失败", response.ok);
      await loadOverview();
    });
    $("createLogin").addEventListener("click", async () => {
      const response = await api("/ui/api/accounts/login-url", {
        method: "POST",
        body: JSON.stringify({callback_port: Number($("callbackPort").value)}),
      });
      const data = await readJson(response);
      if (!response.ok) {
        setMessage("accountMessage", data.detail || "生成失败", false);
        return;
      }
      state.loginUrl = data.login_url;
      $("expectedCode").value = data.code || "";
      $("loginUrlBox").innerHTML = `<a href="${esc(data.login_url)}" target="_blank" rel="noreferrer">打开 DevEco 登录</a><br><span class="mono">${esc(data.login_url)}</span>`;
      $("copyLogin").disabled = false;
      setMessage("accountMessage", "登录 URL 已生成", true);
    });
    $("copyLogin").addEventListener("click", async () => {
      await copyText(state.loginUrl);
      setMessage("accountMessage", "已复制登录 URL", true);
    });
    $("saveAccount").addEventListener("click", async () => {
      const response = await api("/ui/api/accounts/manual-callback", {
        method: "POST",
        body: JSON.stringify({
          callback_url: $("callbackUrl").value,
          expected_code: $("expectedCode").value,
          display_name: $("displayName").value,
          account_id: $("accountTarget").value || null,
        }),
      });
      const data = await readJson(response);
      if (!response.ok || !data.success) {
        setMessage("accountMessage", data.error || "保存失败", false);
        return;
      }
      state.selectedAccountId = data.account_id || state.selectedAccountId;
      $("callbackUrl").value = "";
      setMessage("accountMessage", "账号已保存并启用", true);
      await loadOverview();
    });
    loadOverview();
    // Auto-fill callback port from current page's port
    if (window.location.port) {
      $("callbackPort").value = window.location.port;
    }
    // Check for login callback result (redirected from /callback)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("login_success")) {
      setMessage("accountMessage", "账号登录成功并已保存", true);
      loadAccounts();
      window.history.replaceState(null, "", window.location.pathname);
    } else if (urlParams.has("login_error")) {
      const errors = {
        expired: "登录链接已过期，请重新生成",
        cancelled: "用户取消了登录",
        missing: "回调缺少必要参数",
        region: "仅支持中国站点账号",
        failed: "登录失败，请重试",
      };
      setMessage("accountMessage", errors[urlParams.get("login_error")] || "登录失败", false);
      window.history.replaceState(null, "", window.location.pathname);
    }
  </script>
</body>
</html>"""
