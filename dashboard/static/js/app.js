async function apiFetch(url, options = {}) {
  const resp = await fetch(url, options);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || resp.statusText);
  return data;
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status-msg");
  if (el) {
    el.textContent = msg;
    el.style.color = isError ? "var(--danger)" : "var(--muted)";
  }
}

function archetypeClass(name) {
  if (!name) return "";
  const n = name.toUpperCase();
  if (n.includes("SURE")) return "sure-thing";
  if (n.includes("PERSUADABLE")) return "persuadable";
  if (n.includes("SLEEPING")) return "sleeping-dog";
  return "";
}

async function loadAuditLog() {
  const container = document.getElementById("audit-log");
  if (!container) return;
  const rows = await apiFetch("/api/execution-results");
  if (!rows.length) {
    container.innerHTML = "<p class='hint'>No execution results yet. Run a scenario.</p>";
    return;
  }
  container.innerHTML = rows.map(r => `
    <div class="audit-row">
      <div class="audit-meta">${r.executed_at} | ${r.scenario} | ${r.customer_id} | ${r.pnr}</div>
      <div class="audit-action">${r.action_taken}</div>
      <div>${r.reasoning || ""}</div>
      <div class="audit-meta">Status: ${r.status}</div>
    </div>
  `).join("");
}

async function loadEvents() {
  const container = document.getElementById("events-panel");
  if (!container) return;
  const events = await apiFetch("/api/operational-events");
  container.innerHTML = events.map(e => `
    <div class="event-row">
      <strong>${e.customer_id}</strong> (${e.pnr}) — ${e.itinerary}<br>
      Connection: ${e.orig_connection_mins}m → ${e.new_connection_mins}m |
      Misconnect: ${e.misconnect_risk ? "YES" : "NO"}
    </div>
  `).join("");
}

async function loadArchetypePanels(passengers) {
  const container = document.getElementById("archetype-panels");
  if (!container) return;
  container.innerHTML = "<p class='hint'>Loading profiles from Snowflake MCP...</p>";

  const panels = [];
  for (const cid of passengers.filter(c => c !== "CUST-404")) {
    try {
      const data = await apiFetch(`/api/passenger/${cid}`);
      const archetype = (data.uplift && data.uplift[0]) ? data.uplift[0].archetype : "UNKNOWN";
      panels.push(`
        <div class="archetype-card">
          <h3>${cid}</h3>
          <span class="archetype-label ${archetypeClass(archetype)}">${archetype}</span>
          <div class="profile-panel">${data.profile || "No profile returned"}</div>
        </div>
      `);
    } catch (err) {
      panels.push(`<div class="archetype-card"><h3>${cid}</h3><p style="color:var(--danger)">${err.message}</p></div>`);
    }
  }
  container.innerHTML = panels.join("");
}

function initExecutive(passengers) {
  loadAuditLog();
  loadEvents();
  loadArchetypePanels(passengers);

  document.getElementById("btn-refresh")?.addEventListener("click", () => {
    loadAuditLog();
    loadEvents();
    loadArchetypePanels(passengers);
    setStatus("Refreshed.");
  });

  document.getElementById("btn-scenario-a")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-scenario-a");
    btn.disabled = true;
    setStatus("Running Scenario A (Push/NBA)... this may take several minutes.");
    try {
      await apiFetch("/api/scenario-a", { method: "POST" });
      setStatus("Scenario A complete.");
      await loadAuditLog();
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("btn-scenario-b")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-scenario-b");
    btn.disabled = true;
    setStatus("Running Scenario B (Pull/Concierge)... this may take a few minutes.");
    try {
      const result = await apiFetch("/api/scenario-b", { method: "POST" });
      setStatus("Scenario B complete.");
      await loadAuditLog();
      console.log("Scenario B result:", result);
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      btn.disabled = false;
    }
  });
}

function initConcierge(customerId) {
  apiFetch(`/api/passenger/${customerId}`)
    .then(data => {
      document.getElementById("profile-panel").textContent = data.profile || "No profile returned";
    })
    .catch(err => {
      document.getElementById("profile-panel").textContent = `Error: ${err.message}`;
    });

  document.getElementById("btn-run-concierge")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-run-concierge");
    const chatWindow = document.getElementById("chat-window");
    const responsePanel = document.getElementById("agent-response");
    btn.disabled = true;
    responsePanel.textContent = "Agent is reasoning...";
    try {
      const result = await apiFetch("/api/scenario-b", { method: "POST" });
      const agentResult = result.results?.[customerId]?.result || JSON.stringify(result, null, 2);
      chatWindow.innerHTML += `<div class="chat-msg agent">${agentResult.replace(/</g, "&lt;")}</div>`;
      responsePanel.textContent = agentResult;
    } catch (err) {
      responsePanel.textContent = `Error: ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  });
}
