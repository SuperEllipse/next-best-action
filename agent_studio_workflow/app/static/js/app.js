const sessionState = {
  window: "1d",
  selectedFilter: "all",
  scenario1Rows: [],
  scenario2Rows: [],
  scenario1RunAt: null,
  scenario2RunAt: null,
  scenario2CaseId: null,
  chatHistory: [],
  scenario2Running: false,
  segmentsLoaded: false,
  comparisonLoaded: false,
};

let loadingCount = 0;

const FILTER_LABELS = {
  all: "All operations",
  successful: "Successful resolutions",
  autorebook: "Auto-rebooks",
  hold_prompt: "Hold & prompt",
  staged: "Staged for concierge",
  failed: "Failed actions",
};

const WINDOW_LABELS = { "1h": "1 hour", "4h": "4 hours", "1d": "1 day", "1w": "1 week" };

function showLoading() {
  loadingCount += 1;
  const bar = document.getElementById("loading-bar");
  if (bar) {
    bar.classList.add("active");
    bar.setAttribute("aria-hidden", "false");
  }
}

function hideLoading() {
  loadingCount = Math.max(0, loadingCount - 1);
  if (loadingCount === 0) {
    const bar = document.getElementById("loading-bar");
    if (bar) {
      bar.classList.remove("active");
      bar.setAttribute("aria-hidden", "true");
    }
  }
}

async function withLoading(fn) {
  showLoading();
  try {
    return await fn();
  } finally {
    hideLoading();
  }
}

async function apiFetch(url, options = {}) {
  return withLoading(async () => {
    const resp = await fetch(url, options);
    const contentType = resp.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      await resp.text();
      throw new Error(`Unexpected response (${resp.status}). Expected JSON.`);
    }
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    return data;
  });
}

function escapeHtml(text) {
  return String(text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status-msg");
  if (el) {
    el.textContent = msg;
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }
}

function segmentClass(name) {
  if (!name) return "";
  const n = name.toUpperCase();
  if (n.includes("SURE")) return "sure-thing";
  if (n.includes("PERSUADABLE")) return "persuadable";
  if (n.includes("SLEEPING")) return "sleeping-dog";
  if (n.includes("CHOICE")) return "choice-oriented";
  return "";
}

function parseProfileFields(profileText) {
  const fields = {};
  if (!profileText) return fields;
  for (const line of profileText.split("\n")) {
    const match = line.match(/^\s*[-•*]?\s*([^:]+):\s*(.+)$/);
    if (match) fields[match[1].trim()] = match[2].trim();
  }
  return fields;
}

function renderProfileSummary(profileText) {
  const fields = parseProfileFields(profileText);
  const highlights = [
    ["Name", fields["Full Name"]],
    ["Tier", fields["Loyalty Tier"]],
    ["Spend", fields["Lifetime Spend (USD)"] ? `$${Number(fields["Lifetime Spend (USD)"]).toLocaleString()}` : null],
    ["Propensity", fields["Base Retention Propensity"]],
    ["Last outcome", fields["Last Disruption Outcome"]],
  ].filter(([, v]) => v);

  if (!highlights.length) {
    return `<div class="profile-panel">${escapeHtml(profileText || "No profile returned")}</div>`;
  }

  return `
    <dl class="profile-dl">
      ${highlights.map(([k, v]) => `<div class="profile-row"><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join("")}
    </dl>
  `;
}

function renderSkeletonSegmentCard(customerId) {
  return `
    <div class="archetype-card skeleton-card" id="segment-${customerId}">
      <div class="skeleton-line w40"></div>
      <div class="skeleton-line w25"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line"></div>
      <p class="hint skeleton-label">Loading Snowflake profile…</p>
    </div>
  `;
}

function renderSegmentCard(customerId, segment, profileHtml, note) {
  return `
    <div class="archetype-card" id="segment-${customerId}">
      <div class="archetype-header">
        <h3>${escapeHtml(customerId)}</h3>
        <span class="archetype-label ${segmentClass(segment)}">${escapeHtml(segment)}</span>
      </div>
      ${note ? `<p class="archetype-note">${escapeHtml(note)}</p>` : ""}
      ${profileHtml}
    </div>
  `;
}

function renderBrainLog(container, steps) {
  if (!container || !steps || !steps.length) {
    if (container) container.innerHTML = "<p class='hint'>No brain log steps yet.</p>";
    return;
  }
  container.innerHTML = steps.map(s => `
    <div class="brain-step">
      <div class="brain-phase">${escapeHtml(s.phase)}</div>
      <div class="brain-detail">${escapeHtml(s.detail || "")}</div>
      ${s.source ? `<div class="brain-source">${escapeHtml(s.source)}</div>` : ""}
    </div>
  `).join("");
}

function formatAuditReasoning(reasoning) {
  if (!reasoning) return "";
  try {
    const obj = JSON.parse(reasoning);
    const parts = [];
    if (obj.archetype) parts.push(`Segment: ${obj.archetype}`);
    if (obj.held_flights) parts.push(`Held: ${obj.held_flights.join(", ")}`);
    if (obj.chosen_flight) parts.push(`Chosen: ${obj.chosen_flight}`);
    if (obj.handoff) parts.push(`Handoff: ${obj.handoff}`);
    return parts.join(" · ") || reasoning;
  } catch {
    return reasoning;
  }
}

function statusBadgeClass(status) {
  const s = (status || "").toUpperCase();
  if (s.includes("SUCCESS") || s.includes("CONFIRMED") || s.includes("COMPLETED")) return "badge-success";
  if (s.includes("STAGED") || s.includes("AWAIT")) return "badge-staged";
  if (s.includes("FAIL")) return "badge-fail";
  return "badge-neutral";
}

function renderAuditRows(rows, emptyMessage) {
  if (!rows.length) {
    return `<p class='hint'>${escapeHtml(emptyMessage)}</p>`;
  }
  return rows.map(r => `
    <div class="audit-row">
      <div class="audit-top">
        <span class="audit-customer">${escapeHtml(r.customer_id)}</span>
        <span class="audit-badge ${statusBadgeClass(r.status)}">${escapeHtml(r.status)}</span>
      </div>
      <div class="audit-action">${escapeHtml(r.action_taken)}</div>
      <div class="audit-detail">${escapeHtml(formatAuditReasoning(r.reasoning))}</div>
      <div class="audit-meta">${escapeHtml(r.executed_at)} · ${escapeHtml(r.scenario)} · ${escapeHtml(r.pnr)}${r.case_id ? ` · ${escapeHtml(r.case_id)}` : ""}</div>
    </div>
  `).join("");
}

function renderSessionAuditLog(scenario) {
  const isA = scenario === "PUSH_NBA";
  const rows = isA ? sessionState.scenario1Rows : sessionState.scenario2Rows;
  const log = document.getElementById(isA ? "audit-log-a" : "audit-log-b");
  const hint = document.getElementById(isA ? "audit-hint-a" : "audit-hint-b");
  if (!log) return;

  const emptyMsg = isA
    ? "No results yet — click Run Scenario 1 above."
    : "No results yet — click Run Scenario 2 above.";

  log.innerHTML = renderAuditRows(rows, emptyMsg);
  if (hint) {
    hint.textContent = rows.length
      ? `Showing ${rows.length} record(s) from this session.`
      : (isA ? "Run Scenario 1 to see results from this session only." : "Run Scenario 2 to see results from this session only.");
  }
}

function clearScenarioSession(scenario) {
  const isA = scenario === "PUSH_NBA";
  if (isA) {
    sessionState.scenario1Rows = [];
    sessionState.scenario1RunAt = null;
  } else {
    sessionState.scenario2Rows = [];
    sessionState.scenario2RunAt = null;
    sessionState.scenario2CaseId = null;
    sessionState.chatHistory = [];
    const brainLog = document.getElementById("brain-log");
    const responsePanel = document.getElementById("agent-response");
    if (brainLog) brainLog.innerHTML = "<p class='hint'>Run Scenario 2 to populate the reasoning trace.</p>";
    if (responsePanel) responsePanel.textContent = "Waiting for agent...";
    resetConciergeChatWindow();
  }
  renderSessionAuditLog(scenario);
  setStatus(isA ? "Scenario 1 log cleared. Ready to rerun." : "Scenario 2 log cleared. Ready to rerun.");
}

async function fetchSessionResults(scenario, since) {
  const params = new URLSearchParams({
    window: "1w",
    scenario,
    filter: "all",
    limit: "20",
  });
  if (since) params.set("since", since);
  return apiFetch(`/api/execution-results?${params}`);
}

function bindStatClicks(panel) {
  panel.querySelectorAll(".stat-clickable").forEach(btn => {
    btn.addEventListener("click", () => {
      sessionState.selectedFilter = btn.dataset.filter;
      panel.querySelectorAll(".stat-clickable").forEach(b => b.classList.remove("stat-active"));
      btn.classList.add("stat-active");
      loadExecutiveDetails();
    });
  });
}

async function loadExecutiveStats() {
  const panel = document.getElementById("stats-panel");
  if (!panel) return;

  const stats = await apiFetch(`/api/execution-stats?window=${sessionState.window}`);
  const metrics = [
    { key: "all", value: stats.total_audit_rows, label: "All operations" },
    { key: "successful", value: stats.successful_resolutions, label: "Successful" },
    { key: "autorebook", value: stats.proactive_rebook_actions, label: "Auto-rebooks" },
    { key: "hold_prompt", value: stats.hold_and_prompt_actions, label: "Hold & prompt" },
    { key: "staged", value: stats.staged_for_concierge, label: "Staged (1→2)" },
    { key: "failed", value: stats.failed_actions || 0, label: "Failed" },
  ];

  panel.innerHTML = metrics.map(m => `
    <button class="stat-card stat-clickable ${sessionState.selectedFilter === m.key ? "stat-active" : ""}"
            data-filter="${m.key}" type="button">
      <div class="stat-value">${m.value}</div>
      <div class="stat-label">${escapeHtml(m.label)}</div>
    </button>
  `).join("");

  bindStatClicks(panel);

  const hint = document.getElementById("overview-hint");
  if (hint) {
    hint.textContent = `Aggregated agent actions from Iceberg — last ${WINDOW_LABELS[sessionState.window]}. Click a metric to drill down.`;
  }
}

async function loadExecutiveOverview() {
  await loadExecutiveStats();
  await loadExecutiveDetails();
}

async function loadExecutiveDetails() {
  const panel = document.getElementById("detail-panel");
  const title = document.getElementById("detail-title");
  const count = document.getElementById("detail-count");
  if (!panel) return;

  panel.innerHTML = "<p class='hint'>Loading records from Iceberg…</p>";

  const rows = await apiFetch(
    `/api/execution-results?window=${sessionState.window}&filter=${sessionState.selectedFilter}&limit=100`
  );

  if (title) {
    title.textContent = FILTER_LABELS[sessionState.selectedFilter] || "Operation Details";
  }
  if (count) {
    count.textContent = rows.length ? `${rows.length} record(s)` : "No records";
  }

  panel.innerHTML = renderAuditRows(
    rows,
    `No ${(FILTER_LABELS[sessionState.selectedFilter] || "operations").toLowerCase()} in the last ${WINDOW_LABELS[sessionState.window]}.`
  );
}

async function loadContrast() {
  const container = document.getElementById("contrast-panel");
  if (!container) return;
  try {
    const data = await apiFetch("/api/rules-contrast");
    const rules = data.rules_engine || {};
    const agentic = data.agentic || {};
    container.innerHTML = `
      <div class="contrast-card rules">
        <h3>${escapeHtml(rules.system || "Rules Engine")}</h3>
        <p><strong>Action:</strong> ${escapeHtml(rules.action_taken || "")}</p>
        <p><strong>Operational:</strong> ${escapeHtml(rules.operational_result || "")}</p>
        <p class="contrast-bad">${escapeHtml(rules.customer_result || "")}</p>
        ${rules.flight_chosen ? `<p class="contrast-meta">Flight: ${escapeHtml(rules.flight_chosen)} · Arrival: ${escapeHtml(rules.arrival_local || "")}</p>` : ""}
      </div>
      <div class="contrast-card agentic">
        <h3>${escapeHtml(agentic.system || "Agentic Workflow")}</h3>
        <p><strong>Action:</strong> ${escapeHtml(agentic.action_taken || "")}</p>
        <p><strong>Operational:</strong> ${escapeHtml(agentic.operational_result || "")}</p>
        <p class="contrast-good">${escapeHtml(agentic.customer_result || "")}</p>
        ${agentic.flight_chosen ? `<p class="contrast-meta">Flight: ${escapeHtml(agentic.flight_chosen)} · Arrival: ${escapeHtml(agentic.arrival_local || "")} · ${escapeHtml(agentic.amenity || "")}</p>` : ""}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p class="error-text">${escapeHtml(err.message)}</p>`;
  }
}

async function loadEvents() {
  const container = document.getElementById("events-panel");
  if (!container) return;
  container.innerHTML = "<p class='hint'>Loading disruption data from Iceberg…</p>";
  const events = await apiFetch("/api/operational-events");
  container.innerHTML = events.map(e => `
    <div class="event-card ${e.misconnect_risk ? "event-risk" : ""}">
      <div class="event-id">${escapeHtml(e.customer_id)} <span class="event-pnr">${escapeHtml(e.pnr)}</span></div>
      <div class="event-route">${escapeHtml(e.itinerary)}</div>
      <div class="event-timing">
        Connection <strong>${e.orig_connection_mins}m → ${e.new_connection_mins}m</strong>
        ${e.misconnect_risk ? '<span class="event-flag">MISCONNECT RISK</span>' : ""}
      </div>
    </div>
  `).join("");
}

async function loadSegmentPanels(passengers) {
  const container = document.getElementById("archetype-panels");
  if (!container) return;

  container.innerHTML = passengers.map(renderSkeletonSegmentCard).join("");

  const segmentNotes = {
    "CUST-404": "High-value, choice-oriented — Scenario 1 holds options; Scenario 2 chat executes preference.",
  };

  await Promise.all(passengers.map(async (cid) => {
    const card = document.getElementById(`segment-${cid}`);
    if (!card) return;

    try {
      const data = await apiFetch(`/api/passenger/${cid}`);
      const segment = (data.uplift && data.uplift[0]) ? data.uplift[0].archetype : "UNKNOWN";
      card.outerHTML = renderSegmentCard(
        cid,
        segment,
        renderProfileSummary(data.profile),
        segmentNotes[cid] || null
      );
    } catch (err) {
      card.outerHTML = renderSegmentCard(cid, "ERROR", `<p class="error-text">${escapeHtml(err.message)}</p>`, null);
    }
  }));
}

async function loadSegmentsTab(passengers) {
  if (sessionState.segmentsLoaded) return;
  await Promise.all([loadEvents(), loadSegmentPanels(passengers)]);
  sessionState.segmentsLoaded = true;
}

async function loadComparisonTab() {
  await loadContrast();
  sessionState.comparisonLoaded = true;
}

function initTabs(passengers) {
  document.querySelectorAll("[data-goto-tab]").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = document.querySelector(`.tab[data-tab="${btn.dataset.gotoTab}"]`);
      tab?.click();
    });
  });

  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", async () => {
      const target = tab.dataset.tab;
      document.querySelectorAll(".tab").forEach(t => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach(p => {
        p.classList.remove("active");
        p.hidden = true;
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const panel = document.getElementById(`tab-${target}`);
      if (panel) {
        panel.classList.add("active");
        panel.hidden = false;
      }

      if (target === "segments") await loadSegmentsTab(passengers);
      if (target === "comparison") await loadComparisonTab();
    });
  });
}

function initTimeframes() {
  document.querySelectorAll(".timeframe-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      sessionState.window = btn.dataset.window;
      document.querySelectorAll(".timeframe-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      await loadExecutiveOverview();
    });
  });
}

function appendChatBubble(chatWindow, role, text) {
  if (!chatWindow || !text) return;
  const label = role === "agent" ? "Concierge" : "David";
  const cls = role === "agent" ? "agent" : "passenger";
  chatWindow.insertAdjacentHTML(
    "beforeend",
    `<div class="chat-msg ${cls}"><span class="chat-label">${label}</span>${escapeHtml(text)}</div>`
  );
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function clearChatInput(textarea) {
  if (!textarea) return;
  textarea.value = "";
  textarea.defaultValue = "";
}

function resetConciergeChatWindow() {
  const chatWindow = document.getElementById("chat-window");
  const freeform = document.getElementById("freeform-chat");
  if (chatWindow) {
    const push = chatWindow.querySelector(".chat-msg.push");
    chatWindow.innerHTML = "";
    if (push) chatWindow.appendChild(push);
  }
  clearChatInput(freeform);
}

async function runScenario2Chat(customerId, scriptedChat) {
  if (sessionState.scenario2Running) return;

  const btn = document.getElementById("btn-scenario-b");
  const brainLog = document.getElementById("brain-log");
  const responsePanel = document.getElementById("agent-response");
  const chatWindow = document.getElementById("chat-window");
  const freeform = document.getElementById("freeform-chat");

  const chatMessage = (freeform?.value || "").trim() || scriptedChat;
  sessionState.scenario2Running = true;
  if (btn) btn.disabled = true;
  clearChatInput(freeform);
  appendChatBubble(chatWindow, "passenger", chatMessage);
  responsePanel.textContent = "Agent is reasoning… (3-agent CrewAI workflow)";
  setStatus("Running Scenario 2 — agentic concierge for David Vance…");
  showLoading();
  const runAt = new Date().toISOString().slice(0, 19).replace("T", " ");
  sessionState.scenario2RunAt = runAt;
  const historyPayload = sessionState.chatHistory.map(t => ({ role: t.role, text: t.text }));
  sessionState.chatHistory.push({ role: "passenger", text: chatMessage });
  try {
    const result = await withLoading(() => apiFetch("/api/scenario-b", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_message: chatMessage,
        chat_history: historyPayload,
      }),
    }));
    const data = result.results?.[customerId] || {};
    renderBrainLog(brainLog, data.brain_log);
    const reply = data.concierge_reply || data.result || JSON.stringify(result, null, 2);
    appendChatBubble(chatWindow, "agent", reply);
    sessionState.chatHistory.push({ role: "agent", text: reply });
    responsePanel.textContent = reply;
    if (data.audit_row) {
      sessionState.scenario2CaseId = data.case_id || data.audit_row.case_id || sessionState.scenario2CaseId;
      sessionState.scenario2Rows.push(data.audit_row);
    } else if (data.audit) {
      sessionState.scenario2CaseId = data.case_id || sessionState.scenario2CaseId;
      sessionState.scenario2Rows.push({
        ...data.audit,
        customer_id: customerId,
        pnr: data.pnr || "PNR-404D",
        scenario: "PULL_CONCIERGE",
        reasoning: data.audit.reasoning || "",
      });
    }
    renderSessionAuditLog("PULL_CONCIERGE");
    setStatus("Scenario 2 complete.");
    await loadExecutiveOverview();
  } catch (err) {
    responsePanel.textContent = `Error: ${err.message}`;
    setStatus(err.message, true);
  } finally {
    hideLoading();
    sessionState.scenario2Running = false;
    if (btn) btn.disabled = false;
    clearChatInput(freeform);
  }
}

function initConcierge(customerId, scriptedChat) {
  const form = document.getElementById("concierge-chat-form");
  const freeform = document.getElementById("freeform-chat");
  if (form?.dataset.conciergeBound === "1") return;
  if (form) form.dataset.conciergeBound = "1";

  const submitChat = async (event) => {
    event?.preventDefault();
    await runScenario2Chat(customerId, scriptedChat);
  };

  form?.addEventListener("submit", submitChat);
  freeform?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitChat(event);
    }
  });
}

async function checkEnvStatus() {
  try {
    const health = await fetch("/api/health").then(r => r.json());
    const env = health.env || {};
    if (!health.ready_for_scenarios) {
      const missing = [];
      if (!env.openai_api_key_set) missing.push("OPENAI_API_KEY");
      if (!env.snowflake_pat_set) missing.push("SNOWFLAKE_PAT");
      const hint = env.env_file_found
        ? `Missing in .env: ${missing.join(", ")}`
        : "No .env file — add keys to .env or export them in your shell, then restart the dashboard.";
      setStatus(hint, true);
      return false;
    }
    setStatus("Ready. Run Scenario 1 to populate metrics, or Scenario 2 for David's concierge chat.");
    return true;
  } catch {
    return true;
  }
}

function initExecutive(passengers, customerId, scriptedChat) {
  initTabs(passengers);
  initTimeframes();
  loadExecutiveOverview();
  renderSessionAuditLog("PUSH_NBA");
  renderSessionAuditLog("PULL_CONCIERGE");
  initConcierge(customerId, scriptedChat);
  checkEnvStatus();

  document.getElementById("btn-clear-a")?.addEventListener("click", () => clearScenarioSession("PUSH_NBA"));
  document.getElementById("btn-clear-b")?.addEventListener("click", () => clearScenarioSession("PULL_CONCIERGE"));

  document.getElementById("btn-scenario-a")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-scenario-a");
    btn.disabled = true;
    setStatus("Running Scenario 1 — processing all passengers. This takes several minutes…");
    showLoading();
    const runAt = new Date().toISOString().slice(0, 19).replace("T", " ");
    sessionState.scenario1RunAt = runAt;
    try {
      await withLoading(() => apiFetch("/api/scenario-a", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      }));
      sessionState.scenario1Rows = await fetchSessionResults("PUSH_NBA", runAt);
      renderSessionAuditLog("PUSH_NBA");
      setStatus("Scenario 1 complete. Switch to Scenario 2 tab for David's concierge chat.");
      await loadExecutiveOverview();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      hideLoading();
      btn.disabled = false;
    }
  });
}
