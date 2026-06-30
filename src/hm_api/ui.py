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
      --bg: #f5f3ef;
      --panel: #fffefa;
      --ink: #20211f;
      --muted: #6d706a;
      --line: #ded8ce;
      --accent: #276f5d;
      --accent-2: #9a5b2f;
      --danger: #a33a35;
      --ok: #237554;
      --warn: #94621f;
      font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    html, body { max-width: 100%; overflow-x: hidden; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--ink); }
    button, input, textarea { font: inherit; }
    button {
      min-height: 40px; border: 1px solid var(--accent); background: var(--accent);
      color: white; padding: 0 14px; border-radius: 6px; cursor: pointer; font-weight: 650;
    }
    button.secondary { background: transparent; color: var(--accent); }
    button.danger { border-color: var(--danger); background: var(--danger); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    input, textarea {
      width: 100%; border: 1px solid var(--line); background: #fff; color: var(--ink);
      border-radius: 6px; padding: 9px 10px; min-height: 40px;
    }
    textarea { min-height: 112px; resize: vertical; }
    label { display: block; font-size: 13px; font-weight: 650; color: var(--muted); margin: 10px 0 5px; }
    .shell { display: grid; grid-template-columns: 230px minmax(0, 1fr); min-height: 100vh; }
    aside { border-right: 1px solid var(--line); padding: 18px; background: #ebe6dc; }
    main { min-width: 0; padding: 20px; }
    .brand { font-size: 20px; font-weight: 800; margin-bottom: 4px; }
    .sub { color: var(--muted); font-size: 13px; line-height: 1.6; margin-bottom: 18px; }
    .nav { display: grid; gap: 6px; }
    .nav button {
      background: transparent; color: var(--ink); border: 1px solid transparent;
      justify-content: flex-start; text-align: left; width: 100%;
    }
    .nav button.active { background: var(--panel); border-color: var(--line); color: var(--accent); }
    .topline { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16px; align-items: start; margin-bottom: 16px; }
    h1 { margin: 0; font-size: 24px; line-height: 1.25; }
    h2 { margin: 0 0 12px; font-size: 17px; line-height: 1.35; }
    .badges { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .badge {
      min-height: 30px; display: inline-flex; align-items: center; border: 1px solid var(--line);
      border-radius: 999px; padding: 0 10px; background: var(--panel); color: var(--muted); font-size: 13px;
    }
    .page { display: none; }
    .page.active { display: block; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
    .metric, section {
      background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px;
    }
    .metric .label { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
    .metric .value { font-size: 25px; font-weight: 800; line-height: 1.1; }
    .grid-2 { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); gap: 14px; }
    .grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 10px 0; }
    .table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .table th, .table td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }
    .table th { color: var(--muted); font-weight: 700; font-size: 12px; }
    .status-ok { color: var(--ok); font-weight: 700; }
    .status-bad { color: var(--danger); font-weight: 700; }
    .status-warn { color: var(--warn); font-weight: 700; }
    .muted { color: var(--muted); }
    .message { min-height: 24px; margin-top: 10px; font-size: 14px; font-weight: 650; }
    .message.ok { color: var(--ok); }
    .message.err { color: var(--danger); }
    .mono { font-family: "JetBrains Mono", Consolas, monospace; font-size: 12px; }
    .empty { border: 1px dashed var(--line); padding: 18px; border-radius: 8px; color: var(--muted); background: #fffbf3; }
    @media (max-width: 900px) {
      .shell { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); min-width: 0; max-width: 100vw; }
      .nav { display: flex; overflow-x: auto; padding-bottom: 2px; width: 100%; max-width: 100%; }
      .nav button { flex: 0 0 auto; width: auto; min-width: auto; padding: 0 8px; text-align: center; white-space: nowrap; font-size: 14px; }
      .metrics, .grid-2, .grid-3 { grid-template-columns: 1fr; }
      .topline { grid-template-columns: 1fr; }
      .badges { justify-content: flex-start; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <div class="brand">hm-api 管理台</div>
      <div class="sub">账号、连通性和使用统计集中管理。页面不会展示原始凭据。</div>
      <div class="nav">
        <button class="active" data-tab="overview">总览</button>
        <button data-tab="accounts">账号管理</button>
        <button data-tab="usage">使用统计</button>
        <button data-tab="checks">连通性检测</button>
        <button data-tab="settings">配置</button>
      </div>
    </aside>
    <main>
      <div class="topline">
        <div>
          <h1 id="pageTitle">总览</h1>
          <div class="sub" id="pageSubtitle">当前服务与账号健康状态</div>
        </div>
        <div class="badges">
          <span class="badge" id="badgeLogin">未登录</span>
          <span class="badge" id="badgeAuth">API 认证未知</span>
          <span class="badge" id="badgeCred">凭据目录未知</span>
        </div>
      </div>

      <section class="page active" id="page-overview">
        <div class="metrics">
          <div class="metric"><div class="label">今日请求数</div><div class="value" id="mToday">0</div></div>
          <div class="metric"><div class="label">成功率</div><div class="value" id="mSuccess">0%</div></div>
          <div class="metric"><div class="label">平均延迟</div><div class="value" id="mLatency">0ms</div></div>
          <div class="metric"><div class="label">账号数量</div><div class="value" id="mAccounts">0</div></div>
        </div>
        <div class="grid-2">
          <section><h2>当前启用账号</h2><div id="activeAccount" class="empty">暂无启用账号</div></section>
          <section><h2>最近请求</h2><div id="recentRequests" class="empty">暂无请求记录</div></section>
        </div>
      </section>

      <section class="page" id="page-accounts">
        <div class="grid-2">
          <section>
            <h2>账号列表</h2>
            <div class="toolbar"><button id="refreshAccounts" class="secondary">刷新</button></div>
            <div id="accountsTable"></div>
          </section>
          <section>
            <h2>新增或覆盖账号</h2>
            <label for="displayName">显示名</label>
            <input id="displayName" placeholder="例如：生产账号">
            <label for="callbackPort">回调端口</label>
            <input id="callbackPort" type="number" min="1" max="65535" value="10101">
            <div class="toolbar">
              <button id="createLogin">生成登录 URL</button>
              <button id="copyLogin" class="secondary" disabled>复制 URL</button>
            </div>
            <div id="loginUrlBox" class="empty">登录 URL 会显示在这里</div>
            <label for="expectedCode">校验 Code</label>
            <input id="expectedCode" autocomplete="off">
            <label for="callbackUrl">OAuth 回调地址或 Query</label>
            <textarea id="callbackUrl" spellcheck="false"></textarea>
            <button id="saveAccount">保存账号</button>
            <div class="message" id="accountMessage"></div>
          </section>
        </div>
      </section>

      <section class="page" id="page-usage">
        <div class="metrics">
          <div class="metric"><div class="label">总请求数</div><div class="value" id="uTotal">0</div></div>
          <div class="metric"><div class="label">错误率</div><div class="value" id="uError">0%</div></div>
          <div class="metric"><div class="label">非流式/流式</div><div class="value" id="uStream">-</div></div>
          <div class="metric"><div class="label">Token 用量</div><div class="value" id="uToken">上游未返回</div></div>
        </div>
        <div class="grid-2">
          <section><h2>按模型统计</h2><div id="modelStats"></div></section>
          <section><h2>7 日趋势</h2><div id="trendStats"></div></section>
        </div>
      </section>

      <section class="page" id="page-checks">
        <section>
          <h2>账号连通性检测</h2>
          <div class="toolbar">
            <button id="checkAll">批量检测</button>
            <button id="refreshChecks" class="secondary">刷新状态</button>
          </div>
          <div id="checkTable"></div>
          <div class="message" id="checkMessage"></div>
        </section>
      </section>

      <section class="page" id="page-settings">
        <div class="grid-3">
          <section><h2>认证</h2><div id="settingsAuth" class="muted"></div></section>
          <section><h2>凭据目录</h2><div id="settingsCred" class="muted"></div></section>
          <section><h2>数据策略</h2><div class="muted">仅记录请求元数据，不保存聊天内容。</div></section>
        </div>
      </section>
    </main>
  </div>
  <script>
    const state = { overview: null, accounts: [], usage: null, loginUrl: "" };
    const titles = {
      overview: ["总览", "当前服务与账号健康状态"],
      accounts: ["账号管理", "新增、切换、重命名和删除 DevEco 账号"],
      usage: ["使用统计", "只统计请求元数据，不保存聊天内容"],
      checks: ["连通性检测", "检测账号是否能访问 DevEco 模型配置"],
      settings: ["配置", "运行环境、认证和持久化数据说明"],
    };
    function pct(value) { return `${Math.round((Number(value) || 0) * 100)}%`; }
    function esc(value) {
      const map = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
      return String(value ?? "").replace(/[&<>"']/g, ch => map[ch]);
    }
    function setMessage(id, text, ok) {
      const el = document.getElementById(id);
      el.textContent = text;
      el.className = ok ? "message ok" : "message err";
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
    function table(rows, columns) {
      if (!rows.length) return '<div class="empty">暂无数据</div>';
      return `<table class="table"><thead><tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(c => `<td>${c.render(row)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    }
    async function loadOverview() {
      const response = await api("/ui/api/overview", {method: "GET", headers: {}});
      if (!response.ok) return;
      state.overview = await response.json();
      state.usage = state.overview.usage;
      state.accounts = state.overview.accounts || [];
      document.getElementById("badgeLogin").textContent = state.overview.active_account ? "已登录" : "未登录";
      document.getElementById("badgeAuth").textContent = state.overview.auth_enabled ? "API 认证已启用" : "API 认证未启用";
      document.getElementById("badgeCred").textContent = state.overview.credential_dir.exists ? "凭据目录正常" : "凭据目录待创建";
      document.getElementById("mToday").textContent = state.usage.today_requests;
      document.getElementById("mSuccess").textContent = pct(state.usage.success_rate);
      document.getElementById("mLatency").textContent = `${state.usage.average_latency_ms}ms`;
      document.getElementById("mAccounts").textContent = state.accounts.length;
      renderActive();
      renderRecent();
      renderAccounts();
      renderUsage();
      renderSettings();
    }
    function renderActive() {
      const active = state.overview && state.overview.active_account;
      document.getElementById("activeAccount").innerHTML = active
        ? `<strong>${esc(active.display_name)}</strong><br><span class="muted">${esc(active.user_name || active.user_id)}</span><br><span class="mono">${esc(active.account_id)}</span>`
        : '<div class="empty">暂无启用账号，请在「账号管理」中新增账号。</div>';
    }
    function renderRecent() {
      const recent = (state.usage && state.usage.recent) || [];
      document.getElementById("recentRequests").innerHTML = table(recent.slice(0, 5), [
        {label: "时间", render: r => esc(r.timestamp || "-")},
        {label: "接口", render: r => esc(r.endpoint || "-")},
        {label: "状态", render: r => r.success ? '<span class="status-ok">成功</span>' : '<span class="status-bad">失败</span>'},
      ]);
    }
    async function loadAccounts() {
      const response = await api("/ui/api/accounts", {method: "GET", headers: {}});
      if (!response.ok) return;
      state.accounts = (await response.json()).accounts || [];
      renderAccounts();
    }
    function renderAccounts() {
      const cols = [
        {label: "账号", render: a => `<strong>${esc(a.display_name)}</strong><br><span class="muted">${esc(a.user_name || a.user_id || "未知用户")}</span>`},
        {label: "状态", render: a => a.is_active ? '<span class="status-ok">当前启用</span>' : '<span class="muted">备用</span>'},
        {label: "最近使用", render: a => esc(a.last_used_at || "-")},
        {label: "连通性", render: a => a.connectivity ? (a.connectivity.success ? '<span class="status-ok">连通正常</span>' : '<span class="status-bad">连通失败</span>') : '<span class="status-warn">未检测</span>'},
        {label: "操作", render: a => `<button class="secondary" data-action="activate" data-id="${esc(a.account_id)}">启用</button> <button class="secondary" data-action="rename" data-id="${esc(a.account_id)}">重命名</button> <button class="secondary" data-action="check" data-id="${esc(a.account_id)}">检测</button> <button class="danger" data-action="delete" data-id="${esc(a.account_id)}">删除</button>`},
      ];
      document.getElementById("accountsTable").innerHTML = table(state.accounts, cols);
      document.getElementById("checkTable").innerHTML = table(state.accounts, cols.slice(0, 4).concat([{label: "检测", render: a => `<button class="secondary" data-action="check" data-id="${esc(a.account_id)}">检测</button>`}]));
    }
    function renderUsage() {
      const usage = state.usage || {};
      document.getElementById("uTotal").textContent = usage.total_requests || 0;
      document.getElementById("uError").textContent = pct(usage.error_rate);
      document.getElementById("uStream").textContent = `${usage.non_streaming_count || 0}/${usage.streaming_count || 0}`;
      document.getElementById("uToken").textContent = usage.token_usage ? String(usage.token_usage.total_tokens || "已记录") : "上游未返回";
      const modelRows = Object.entries(usage.by_model || {}).map(([model, v]) => Object.assign({model}, v));
      document.getElementById("modelStats").innerHTML = table(modelRows, [
        {label: "模型", render: r => esc(r.model)},
        {label: "请求", render: r => esc(r.requests)},
        {label: "平均延迟", render: r => `${esc(r.average_latency_ms)}ms`},
      ]);
      document.getElementById("trendStats").innerHTML = table(usage.trend || [], [
        {label: "日期", render: r => esc(r.date)},
        {label: "请求数", render: r => esc(r.requests)},
      ]);
    }
    function renderSettings() {
      if (!state.overview) return;
      document.getElementById("settingsAuth").textContent = state.overview.auth_enabled ? "Bearer 认证已启用" : "Bearer 认证未启用";
      document.getElementById("settingsCred").textContent = state.overview.credential_dir.path;
    }
    async function activateAccount(id) {
      await api(`/ui/api/accounts/${encodeURIComponent(id)}/activate`, {method: "POST"});
      await loadOverview();
    }
    async function renameAccount(id) {
      const displayName = window.prompt("新的账号显示名");
      if (!displayName || !displayName.trim()) return;
      await api(`/ui/api/accounts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({display_name: displayName.trim()})
      });
      await loadOverview();
    }
    async function deleteAccount(id) {
      if (!window.confirm("确认删除这个账号？")) return;
      await api(`/ui/api/accounts/${encodeURIComponent(id)}`, {method: "DELETE"});
      await loadOverview();
    }
    async function checkOne(id) {
      const response = await api(`/ui/api/accounts/${encodeURIComponent(id)}/check`, {method: "POST"});
      const data = await response.json();
      setMessage("checkMessage", data.result && data.result.success ? "检测完成：连通正常" : "检测完成：连通失败", Boolean(data.result && data.result.success));
      await loadOverview();
    }
    document.querySelectorAll(".nav button").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".nav button").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
        button.classList.add("active");
        const tab = button.dataset.tab;
        document.getElementById(`page-${tab}`).classList.add("active");
        document.getElementById("pageTitle").textContent = titles[tab][0];
        document.getElementById("pageSubtitle").textContent = titles[tab][1];
      });
    });
    document.addEventListener("click", event => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const id = button.dataset.id;
      if (!id) return;
      if (button.dataset.action === "activate") activateAccount(id);
      if (button.dataset.action === "rename") renameAccount(id);
      if (button.dataset.action === "check") checkOne(id);
      if (button.dataset.action === "delete") deleteAccount(id);
    });
    document.getElementById("refreshAccounts").addEventListener("click", loadAccounts);
    document.getElementById("refreshChecks").addEventListener("click", loadOverview);
    document.getElementById("checkAll").addEventListener("click", async () => {
      const response = await api("/ui/api/accounts/check-all", {method: "POST"});
      setMessage("checkMessage", response.ok ? "批量检测完成" : "批量检测失败", response.ok);
      await loadOverview();
    });
    document.getElementById("createLogin").addEventListener("click", async () => {
      const response = await api("/ui/api/accounts/login-url", {
        method: "POST",
        body: JSON.stringify({callback_port: Number(document.getElementById("callbackPort").value)})
      });
      const data = await response.json();
      if (!response.ok) return setMessage("accountMessage", data.detail || "生成失败", false);
      state.loginUrl = data.login_url;
      document.getElementById("expectedCode").value = data.code;
      document.getElementById("loginUrlBox").innerHTML = `<a href="${esc(data.login_url)}" target="_blank" rel="noreferrer">打开 DevEco 登录</a><br><span class="mono">${esc(data.login_url)}</span>`;
      document.getElementById("copyLogin").disabled = false;
      setMessage("accountMessage", "登录 URL 已生成", true);
    });
    document.getElementById("copyLogin").addEventListener("click", async () => {
      if (!state.loginUrl) return;
      await navigator.clipboard.writeText(state.loginUrl);
      setMessage("accountMessage", "已复制登录 URL", true);
    });
    document.getElementById("saveAccount").addEventListener("click", async () => {
      const response = await api("/ui/api/accounts/manual-callback", {
        method: "POST",
        body: JSON.stringify({
          callback_url: document.getElementById("callbackUrl").value,
          expected_code: document.getElementById("expectedCode").value,
          display_name: document.getElementById("displayName").value
        })
      });
      const data = await response.json();
      if (!response.ok || !data.success) return setMessage("accountMessage", data.error || "保存失败", false);
      setMessage("accountMessage", "账号已保存并启用", true);
      await loadOverview();
    });
    loadOverview();
  </script>
</body>
</html>"""
