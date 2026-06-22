const state = {
  sessionId: null,
  refreshTimer: null,
};

const STORAGE_KEY = "pydantic-ai-web-console:session-id";

const els = {
  sessionList: document.querySelector("#session-list"),
  toolLogs: document.querySelector("#tool-logs"),
  sessionTitle: document.querySelector("#log-session-title"),
};

init().catch((error) => {
  console.error(error);
  els.sessionTitle.textContent = "加载失败";
});

async function init() {
  const sessions = await fetchJson("/api/sessions");
  if (sessions.length === 0) {
    els.sessionTitle.textContent = "暂无会话日志";
    return;
  }
  const preferredId = localStorage.getItem(STORAGE_KEY);
  const target = sessions.find((session) => session.id === preferredId) || sessions[0];
  renderSessionList(sessions, target.id);
  await loadSession(target.id);
}

async function loadSession(sessionId) {
  state.sessionId = sessionId;
  stopRefresh();
  localStorage.setItem(STORAGE_KEY, sessionId);
  const session = await fetchJson(`/api/sessions/${sessionId}`);
  els.sessionTitle.textContent = buildSessionTitle(session);
  renderToolLogs(session.tool_logs);
  const sessions = await fetchJson("/api/sessions");
  renderSessionList(sessions, sessionId);
  if (session.run_status === "running") {
    startRefresh(sessionId);
  }
}

function renderSessionList(items, activeId) {
  els.sessionList.innerHTML = "";
  for (const item of items) {
    const button = document.createElement("button");
    button.className = `card session-item${item.id === activeId ? " active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <h3>${escapeHtml(item.title)}</h3>
      <p class="muted">${item.message_count} 条消息</p>
    `;
    button.addEventListener("click", () => loadSession(item.id));
    els.sessionList.appendChild(button);
  }
}

function renderToolLogs(logs) {
  els.toolLogs.innerHTML = "";
  if (logs.length === 0) {
    els.toolLogs.innerHTML = `<div class="empty-state">当前会话还没有工具调用日志。</div>`;
    return;
  }
  const sorted = [...logs].reverse();
  for (const log of sorted) {
    const div = document.createElement("div");
    div.className = "log-card";
    div.innerHTML = `
      <div class="log-meta">
        <strong>${escapeHtml(log.name)}</strong>
        <span>${translateLogEvent(log.event)}</span>
      </div>
      <div class="log-content">${escapeHtml(log.content)}</div>
    `;
    els.toolLogs.appendChild(div);
  }
}

function startRefresh(sessionId) {
  stopRefresh();
  state.refreshTimer = window.setInterval(async () => {
    if (state.sessionId !== sessionId) {
      stopRefresh();
      return;
    }
    try {
      const session = await fetchJson(`/api/sessions/${sessionId}`);
      els.sessionTitle.textContent = buildSessionTitle(session);
      renderToolLogs(session.tool_logs);
      if (session.run_status !== "running") {
        stopRefresh();
      }
    } catch (error) {
      console.error(error);
      stopRefresh();
    }
  }, 1000);
}

function stopRefresh() {
  if (state.refreshTimer) {
    window.clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
}

function buildSessionTitle(session) {
  if (session.run_status === "running") {
    return `当前会话: ${session.title}（执行中）`;
  }
  if (session.run_status === "error") {
    return `当前会话: ${session.title}（失败）`;
  }
  return `当前会话: ${session.title}`;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function escapeHtml(input) {
  return String(input ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function translateLogEvent(event) {
  const map = {
    tool_start: "工具开始",
    tool_end: "工具结束",
    tool_error: "工具报错",
    status: "状态",
    message: "消息",
  };
  return map[event] || event;
}
