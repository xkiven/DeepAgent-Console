const state = {
  sessionId: null,
  streamingAssistantId: null,
};

const STORAGE_KEY = "pydantic-ai-web-console:session-id";

const els = {
  runtimeMode: document.querySelector("#runtime-mode"),
  sessionList: document.querySelector("#session-list"),
  skillsList: document.querySelector("#skills-list"),
  mcpList: document.querySelector("#mcp-list"),
  messages: document.querySelector("#messages"),
  chatStatus: document.querySelector("#chat-status"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  newSessionBtn: document.querySelector("#new-session-btn"),
  resetSessionBtn: document.querySelector("#reset-session-btn"),
};

init().catch((error) => {
  console.error(error);
  setStatus("error", "启动失败");
});

async function init() {
  const [config, skills, mcpServers, sessions] = await Promise.all([
    fetchJson("/__config"),
    fetchJson("/api/skills"),
    fetchJson("/api/mcp/servers"),
    fetchJson("/api/sessions"),
  ]);

  els.runtimeMode.textContent = `运行模式：${config.llm_mode}`;
  renderSkills(skills);
  renderMcpServers(mcpServers);

  if (sessions.length === 0) {
    const created = await createSession();
    await loadSession(created.id);
  } else {
    renderSessionList(sessions);
    const preferredId = localStorage.getItem(STORAGE_KEY);
    const target = sessions.find((session) => session.id === preferredId) || sessions[0];
    await loadSession(target.id);
  }

  els.chatForm.addEventListener("submit", onSubmit);
  els.newSessionBtn.addEventListener("click", async () => {
    const created = await createSession();
    await refreshSessions(created.id);
    await loadSession(created.id);
  });
  els.resetSessionBtn.addEventListener("click", async () => {
    if (!state.sessionId) return;
    await fetchJson(`/api/sessions/${state.sessionId}/reset`, { method: "POST" });
    await loadSession(state.sessionId);
    await refreshSessions(state.sessionId);
  });
}

async function onSubmit(event) {
  event.preventDefault();
  if (!state.sessionId) return;

  const message = els.chatInput.value.trim();
  if (!message) return;

  appendMessage({ role: "user", content: message });
  els.chatInput.value = "";
  setStatus("running", "执行中");
  startStreamingAssistant();

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, message }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!raw.startsWith("data: ")) continue;
      const payload = JSON.parse(raw.slice(6));
      handleStreamEvent(payload);
    }
  }

  await refreshSessions(state.sessionId);
}

function handleStreamEvent(event) {
  if (event.type === "token") {
    appendAssistantToken(event.content);
    return;
  }
  if (event.type === "message") {
    replaceStreamingAssistant(event.content.content);
    return;
  }
  if (event.type === "status") {
    setStatus("running", toChineseStatus(event.content));
    return;
  }
  if (event.type === "done") {
    setStatus("idle", "空闲");
    state.streamingAssistantId = null;
    return;
  }
  if (event.type === "error") {
    setStatus("error", String(event.content));
  }
}

async function createSession() {
  return fetchJson("/api/sessions", { method: "POST" });
}

async function loadSession(sessionId) {
  state.sessionId = sessionId;
  state.streamingAssistantId = null;
  localStorage.setItem(STORAGE_KEY, sessionId);
  const session = await fetchJson(`/api/sessions/${sessionId}`);
  renderMessages(session.messages);
  await refreshSessions(sessionId);
}

async function refreshSessions(activeId) {
  const sessions = await fetchJson("/api/sessions");
  renderSessionList(sessions, activeId);
}

function renderSessionList(items, activeId = state.sessionId) {
  els.sessionList.innerHTML = "";
  for (const item of items) {
    const div = document.createElement("button");
    div.className = `card session-item${item.id === activeId ? " active" : ""}`;
    div.innerHTML = `
      <h3>${escapeHtml(item.title)}</h3>
      <p class="muted">${item.message_count} 条消息</p>
    `;
    div.addEventListener("click", () => loadSession(item.id));
    els.sessionList.appendChild(div);
  }
}

function renderSkills(skills) {
  els.skillsList.innerHTML = "";
  for (const skill of skills) {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <h3>${escapeHtml(skill.name)}</h3>
      <p>${escapeHtml(skill.description)}</p>
      <p class="muted">${escapeHtml(skill.path)}</p>
    `;
    els.skillsList.appendChild(div);
  }
}

function renderMcpServers(servers) {
  els.mcpList.innerHTML = "";
  for (const server of servers) {
    const div = document.createElement("div");
    div.className = "card";
    div.innerHTML = `
      <h3>${escapeHtml(server.name)}</h3>
      <p>
        <span class="${server.connected ? "connected" : "disconnected"}">
          ${server.connected ? "已连接" : "未连接"}
        </span>
        · ${escapeHtml(server.transport)}
      </p>
      <p class="muted">${escapeHtml(server.detail || "")}</p>
      <p>${server.tools.map((tool) => `<span class="tool-badge">${escapeHtml(tool)}</span>`).join(" ")}</p>
    `;
    els.mcpList.appendChild(div);
  }
}

function renderMessages(messages) {
  els.messages.innerHTML = "";
  for (const message of messages) {
    appendMessage(message);
  }
}

function appendMessage(message) {
  const div = document.createElement("div");
  div.className = `message ${message.role}`;
  div.textContent = message.content;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function startStreamingAssistant() {
  const div = document.createElement("div");
  state.streamingAssistantId = `assistant-${Date.now()}`;
  div.dataset.id = state.streamingAssistantId;
  div.className = "message assistant";
  div.textContent = "";
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function appendAssistantToken(token) {
  const node = document.querySelector(`[data-id="${state.streamingAssistantId}"]`);
  if (!node) return;
  node.textContent += token;
  els.messages.scrollTop = els.messages.scrollHeight;
}

function replaceStreamingAssistant(content) {
  const node = document.querySelector(`[data-id="${state.streamingAssistantId}"]`);
  if (!node) return;
  node.textContent = content;
  els.messages.scrollTop = els.messages.scrollHeight;
}

function setStatus(kind, text) {
  els.chatStatus.className = `status-pill ${kind}`;
  els.chatStatus.textContent = text;
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

function toChineseStatus(status) {
  const map = {
    running: "执行中",
    complete: "已完成",
  };
  return map[status] || String(status);
}
