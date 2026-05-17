/* ============================================================
   FlowMind AI - Application Logic (V2)
   Full frontend-backend integration with:
   - JWT authentication
   - Real API calls with auth headers
   - Live execution polling
   - Step editor modal (custom workflow input)
   - Approval modal
   - Voice-to-text input
   - Fallback demo templates when backend is offline
   ============================================================ */
// Auto-detect backend URL: use localhost for local dev, Render for production
const API_BASE_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8081"
  : "https://flowmindai.onrender.com";

// ─── Current Run State ───────────────────────────────────────
let currentRunId = null;
let pollInterval = null;
let isGenerating = false;
let execStartTime = null; // tracks when workflow execution began

// ─── Workflow Templates (Offline Fallback) ───────────────────

const WORKFLOW_TEMPLATES = {
  bug: {
    nodes: [
      { title: "Fetch Issue Context", detail: "Collect issue metadata from the project system", icon: "📥" },
      { title: "Create GitHub Issue", detail: "Open a follow-up issue for engineering", icon: "🐙" },
      { title: "Send Email Alert", detail: "Email the engineering lead via Gmail", icon: "📧" },
      { title: "Create Jira Ticket", detail: "Log to Jira for tracking", icon: "🎫" },
      { title: "Request Approval", detail: "Pause for human confirmation", icon: "✅" },
    ],
    tools: [
      { task: "Fetch Issue Context", api: "MCP · Planning Agent", icon: "📥", type: "ai" },
      { task: "Create GitHub Issue", api: "MCP · server-github", icon: "🐙", type: "github" },
      { task: "Send Email Alert", api: "MCP · server-gmail", icon: "📧", type: "email" },
      { task: "Create Jira Ticket", api: "MCP · server-jira", icon: "🎫", type: "jira" },
      { task: "Approval Gate", api: "MCP · Workflow Runtime", icon: "✅", type: "ai" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: backend unavailable, showing a local workflow simulation." },
      { icon: "success", text: "Generated a critical issue workflow from the prompt." },
      { icon: "success", text: "Mapped the workflow to GitHub, Gmail, Jira, and approval MCP servers." },
      { icon: "warning", text: "Execution paused at approval gate in demo mode." },
    ],
    learning: {
      status: "Demo Mode",
      steps: "5 steps",
      time: "~3.2s",
      score: "80%",
      suggestion: "Start the backend to generate real steps from the prompt and execute the live runtime instead of the local simulation.",
      barLabel: "Backend Connectivity",
      barValue: 25,
    },
  },
  sales: {
    nodes: [
      { title: "Read Sales Source", detail: "Collect weekly numbers from the source sheet", icon: "📊" },
      { title: "Update Tracking Sheet", detail: "Persist the report data", icon: "📈" },
      { title: "Send Email Summary", detail: "Email the sales team via Gmail", icon: "📧" },
    ],
    tools: [
      { task: "Read Sales Source", api: "MCP · server-gdrive", icon: "📊", type: "sheets" },
      { task: "Update Google Sheet", api: "MCP · server-gdrive", icon: "📈", type: "sheets" },
      { task: "Send Email Summary", api: "MCP · server-gmail", icon: "📧", type: "email" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: using the local sales-report template." },
      { icon: "success", text: "Prepared a weekly report workflow from the prompt." },
      { icon: "success", text: "Connected the plan to Google Sheets and Gmail MCP servers." },
    ],
    learning: {
      status: "Demo Mode",
      steps: "3 steps",
      time: "~2.1s",
      score: "67%",
      suggestion: "The backend can turn this prompt into structured runtime steps automatically once it is running.",
      barLabel: "Runtime Readiness",
      barValue: 35,
    },
  },
  pr: {
    nodes: [
      { title: "Inspect PR Context", detail: "Gather repo and change information", icon: "📥" },
      { title: "Create GitHub Follow-up", detail: "Log review work on GitHub", icon: "🐙" },
      { title: "Email Reviewer Summary", detail: "Send review summary via Gmail", icon: "📧" },
    ],
    tools: [
      { task: "Inspect PR Context", api: "MCP · server-github", icon: "📥", type: "github" },
      { task: "Create GitHub Issue", api: "MCP · server-github", icon: "🐙", type: "github" },
      { task: "Email Reviewer", api: "MCP · server-gmail", icon: "📧", type: "email" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: using the PR workflow template." },
      { icon: "success", text: "Generated a review workflow from the prompt." },
      { icon: "success", text: "Mapped tasks to GitHub and Gmail MCP servers." },
    ],
    learning: {
      status: "Demo Mode",
      steps: "3 steps",
      time: "~1.8s",
      score: "67%",
      suggestion: "Run the backend to produce real generated steps and execution results for pull-request prompts.",
      barLabel: "Runtime Readiness",
      barValue: 35,
    },
  },
};

const TOOL_META = {
  mock_pm: { label: "Fetch Issue Context", api: "MCP · Planning Agent", icon: "📥", type: "ai" },
  gmail: { label: "Send Email", api: "MCP · server-gmail", icon: "📧", type: "email" },
  github: { label: "Create GitHub Issue", api: "MCP · server-github", icon: "🐙", type: "github" },
  sheets: { label: "Update Google Sheet", api: "MCP · server-gdrive", icon: "📊", type: "sheets" },
  jira: { label: "Create Jira Ticket", api: "MCP · server-jira", icon: "🎫", type: "jira" },
  approval: { label: "Request Approval", api: "MCP · Workflow Runtime", icon: "✅", type: "ai" },
  email: { label: "Send Email", api: "MCP · server-gmail", icon: "📧", type: "email" },
  request_user_input: { label: "User Input Required", api: "MCP · Workflow Runtime", icon: "✏️", type: "ai" },
};

// ============================================================
//  AUTH UTILITIES
// ============================================================

function getToken() {
  return localStorage.getItem("flowmind_token");
}

function getUserProfile() {
  try {
    return JSON.parse(localStorage.getItem("flowmind_user_profile") || "null");
  } catch {
    return null;
  }
}

function getUser() {
  const profile = getUserProfile();
  return profile?.name || localStorage.getItem("flowmind_user") || "User";
}

function isLoggedIn() {
  return !!getToken();
}

function handleLogout() {
  localStorage.removeItem("flowmind_token");
  localStorage.removeItem("flowmind_user");
  localStorage.removeItem("flowmind_auth_provider");
  localStorage.removeItem("flowmind_user_profile");
  window.location.href = "login.html";
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = "login.html";
    return false;
  }
  return true;
}

function renderUserMenu() {
  const userMenu = document.getElementById("userMenu");
  const userAvatar = document.getElementById("userAvatar");
  const userNameEl = document.getElementById("userName");
  const profile = getUserProfile();

  if (isLoggedIn() && userMenu) {
    const name = getUser();
    userMenu.style.display = "flex";
    if (profile?.picture) {
      userAvatar.innerHTML = `<img src="${profile.picture}" alt="${escapeHTML(name)}" class="user-avatar-image" />`;
    } else {
      userAvatar.textContent = name.substring(0, 2);
    }
    userNameEl.textContent = name;
  }
}

function authHeaders() {
  const token = getToken();
  const headers = { "Content-Type": "application/json" };
  if (token && token !== "dev_bypass_token") {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ============================================================
//  UTILITIES
// ============================================================

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function detectTemplate(prompt) {
  const lower = prompt.toLowerCase();
  if (lower.includes("bug") || lower.includes("issue") || lower.includes("escalat") || lower.includes("critical")) return "bug";
  if (lower.includes("sales") || lower.includes("report") || lower.includes("weekly") || lower.includes("monday")) return "sales";
  if (lower.includes("pull request") || lower.includes("pr ") || lower.includes("review") || lower.includes("code")) return "pr";
  return "bug";
}

function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// ============================================================
//  TOAST NOTIFICATIONS
// ============================================================

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const icons = { success: "✓", error: "✕", info: "ℹ", warning: "⚠" };
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || "ℹ"}</span><span>${escapeHTML(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("removing");
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ============================================================
//  BACKGROUND / UI INIT
// ============================================================

function initGrid() {
  const canvas = document.getElementById("gridCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 0.5;
    const gap = 60;
    for (let x = 0; x < canvas.width; x += gap) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += gap) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }
  }

  resize();
  window.addEventListener("resize", resize);
}

function initNavbar() {
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 20);
  });
}

// ============================================================
//  DAG RENDERING
// ============================================================

function renderDAG(nodes) {
  const container = document.getElementById("dagContainer");
  container.innerHTML = "";

  const wrapper = document.createElement("div");
  wrapper.className = "dag-nodes";

  nodes.forEach((node, i) => {
    const el = document.createElement("div");
    el.className = "dag-node";
    el.id = `dag-node-${i}`;
    el.innerHTML = `
      <div class="node-step">${i + 1}</div>
      <div class="node-content">
        <div class="node-title">${escapeHTML(node.icon)} ${escapeHTML(node.title)}</div>
        <div class="node-detail">${escapeHTML(node.detail)}</div>
      </div>
      <div class="node-status-dot pending" id="node-dot-${i}"></div>
    `;
    wrapper.appendChild(el);

    if (i < nodes.length - 1) {
      const arrow = document.createElement("div");
      arrow.className = "dag-arrow";
      arrow.id = `dag-arrow-${i}`;
      arrow.innerHTML = `<div class="arrow-line"></div><div class="arrow-head"></div>`;
      wrapper.appendChild(arrow);
    }
  });

  container.appendChild(wrapper);

  nodes.forEach((_, i) => {
    setTimeout(() => {
      document.getElementById(`dag-node-${i}`)?.classList.add("visible");
      const arrowEl = document.getElementById(`dag-arrow-${i}`);
      if (arrowEl) setTimeout(() => arrowEl.classList.add("visible"), 100);
    }, i * 160);
  });
}

function renderTools(tools) {
  const container = document.getElementById("toolsContainer");
  container.innerHTML = "";

  const list = document.createElement("div");
  list.className = "tools-list";

  tools.forEach((tool, i) => {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.innerHTML = `
      <div class="tool-card-icon ${tool.type}">${escapeHTML(tool.icon)}</div>
      <div class="tool-card-info">
        <div class="tool-card-task">${escapeHTML(tool.task)}</div>
        <div class="tool-card-api">${escapeHTML(tool.api)}</div>
      </div>
      <div class="tool-card-badge connected">Routed</div>
    `;
    list.appendChild(card);
    setTimeout(() => card.classList.add("visible"), i * 120 + 200);
  });

  container.appendChild(list);
}

// ============================================================
//  DAG NODE STATUS UPDATES (Live Polling)
// ============================================================

function updateNodeStatus(index, status) {
  const dot = document.getElementById(`node-dot-${index}`);
  const nodeEl = document.getElementById(`dag-node-${index}`);
  if (!dot || !nodeEl) return;

  // Clear previous state classes
  nodeEl.classList.remove("active", "completed", "waiting", "failed", "recovered");

  if (status === "running") {
    dot.className = "node-status-dot running";
    nodeEl.classList.add("active");
  } else if (status === "success") {
    dot.className = "node-status-dot done";
    nodeEl.classList.add("completed");
  } else if (status === "failed") {
    dot.className = "node-status-dot failed";
    nodeEl.classList.add("failed");
  } else if (status === "waiting_approval") {
    dot.className = "node-status-dot waiting_approval";
    nodeEl.classList.add("waiting");
  } else if (status === "waiting_user_input") {
    dot.className = "node-status-dot waiting_user_input";
    nodeEl.classList.add("waiting");
  } else if (status === "rolled_back") {
    dot.className = "node-status-dot rolled_back";
    nodeEl.classList.add("failed");
  } else {
    dot.className = "node-status-dot pending";
  }
}

function addConsoleLog(text, icon = "info") {
  const container = document.getElementById("consoleContainer");

  const entry = document.createElement("div");
  entry.className = "log-entry";

  let iconHTML;
  if (icon === "success") iconHTML = `<span class="log-icon success">✓</span>`;
  else if (icon === "warning") iconHTML = `<span class="log-icon warning">⚠</span>`;
  else if (icon === "error") iconHTML = `<span class="log-icon error">✕</span>`;
  else iconHTML = `<span class="log-icon info">›</span>`;

  entry.innerHTML = `
    ${iconHTML}
    <span class="log-text">${escapeHTML(text)}</span>
    <span class="log-timestamp">${formatTimestamp()}</span>
  `;
  container.appendChild(entry);
  requestAnimationFrame(() => entry.classList.add("visible"));
  container.scrollTop = container.scrollHeight;
}

// ============================================================
//  EXECUTION CONSOLE (for offline fallback)
// ============================================================

async function runExecution(logs, nodes) {
  const container = document.getElementById("consoleContainer");
  const statusEl = document.getElementById("consoleStatus");
  container.innerHTML = "";
  statusEl.textContent = "Running";
  statusEl.className = "panel-status running";

  for (let i = 0; i < logs.length; i++) {
    const log = logs[i];
    const entry = document.createElement("div");
    entry.className = "log-entry";

    let iconHTML;
    if (log.icon === "success") iconHTML = `<span class="log-icon success">✓</span>`;
    else if (log.icon === "warning") iconHTML = `<span class="log-icon warning">⚠</span>`;
    else if (log.icon === "error") iconHTML = `<span class="log-icon error">✕</span>`;
    else iconHTML = `<span class="log-icon info">›</span>`;

    entry.innerHTML = `
      ${iconHTML}
      <span class="log-text">${escapeHTML(log.text)}</span>
      <span class="log-timestamp">${formatTimestamp()}</span>
    `;
    container.appendChild(entry);

    await sleep(60);
    entry.classList.add("visible");

    if (i > 0 && i - 1 < nodes.length) {
      const dotIdx = Math.min(i - 1, nodes.length - 1);
      const dot = document.getElementById(`node-dot-${dotIdx}`);
      const nodeEl = document.getElementById(`dag-node-${dotIdx}`);
      if (dot) dot.className = "node-status-dot done";
      if (nodeEl) {
        nodeEl.classList.remove("active");
        nodeEl.classList.add("completed");
      }
      if (dotIdx + 1 < nodes.length) {
        document.getElementById(`dag-node-${dotIdx + 1}`)?.classList.add("active");
        const nextDot = document.getElementById(`node-dot-${dotIdx + 1}`);
        if (nextDot) nextDot.className = "node-status-dot running";
      }
    }

    await sleep(log.icon === "warning" ? 1200 : 500);
    container.scrollTop = container.scrollHeight;
  }

  for (let i = 0; i < nodes.length; i++) {
    const dot = document.getElementById(`node-dot-${i}`);
    const nodeEl = document.getElementById(`dag-node-${i}`);
    if (dot) dot.className = "node-status-dot done";
    if (nodeEl) {
      nodeEl.classList.remove("active");
      nodeEl.classList.add("completed");
    }
  }

  statusEl.textContent = "Completed";
  statusEl.className = "panel-status done";
}

// ============================================================
//  LEARNING PANEL
// ============================================================

function renderLearning(data) {
  const container = document.getElementById("learningContainer");
  const statusEl = document.getElementById("learningStatus");
  container.innerHTML = "";
  statusEl.textContent = "Analysis ready";
  statusEl.className = "panel-status done";

  const content = document.createElement("div");
  content.className = "learning-content";
  content.innerHTML = `
    <div class="learning-stats">
      <div class="stat-card" id="stat-0">
        <div class="stat-value success">${escapeHTML(data.status)}</div>
        <div class="stat-label">Status</div>
      </div>
      <div class="stat-card" id="stat-1">
        <div class="stat-value time">${escapeHTML(data.steps)}</div>
        <div class="stat-label">Steps</div>
      </div>
      <div class="stat-card" id="stat-2">
        <div class="stat-value time">${escapeHTML(data.time)}</div>
        <div class="stat-label">Exec Time</div>
      </div>
      <div class="stat-card" id="stat-3">
        <div class="stat-value score">${escapeHTML(data.score)}</div>
        <div class="stat-label">Completion</div>
      </div>
    </div>
    <div class="insight-card" id="insight-main">
      <div class="insight-header">
        <span class="insight-icon">💡</span>
        <span class="insight-title">Workflow Insight</span>
      </div>
      <div class="insight-body">${escapeHTML(data.suggestion)}</div>
      <div class="insight-bar-container">
        <div class="insight-bar-label">
          <span>${escapeHTML(data.barLabel)}</span>
          <span>${escapeHTML(String(data.barValue))}%</span>
        </div>
        <div class="insight-bar">
          <div class="insight-bar-fill" id="insightBarFill"></div>
        </div>
      </div>
    </div>
  `;
  container.appendChild(content);

  setTimeout(() => document.getElementById("stat-0")?.classList.add("visible"), 120);
  setTimeout(() => document.getElementById("stat-1")?.classList.add("visible"), 240);
  setTimeout(() => document.getElementById("stat-2")?.classList.add("visible"), 360);
  setTimeout(() => document.getElementById("stat-3")?.classList.add("visible"), 480);
  setTimeout(() => {
    document.getElementById("insight-main")?.classList.add("visible");
    setTimeout(() => {
      const barFill = document.getElementById("insightBarFill");
      if (barFill) barFill.style.width = `${data.barValue}%`;
    }, 240);
  }, 600);
}

// ============================================================
//  BUILD VISUALIZATION FROM BACKEND RESPONSE
// ============================================================

function buildVisualizationFromResponse(response) {
  const run = response.run || { steps: [], status: "failed" };
  const steps = run.steps || [];
  const generatedSteps = response.generated_steps || [];

  const nodes = steps.map((step, index) => ({
    title: TOOL_META[step.tool]?.label || step.tool,
    detail: generatedSteps[index]?.input || step.params?.raw_input || `Execute ${step.action}`,
    icon: TOOL_META[step.tool]?.icon || "⚙️",
  }));

  const tools = steps.map((step) => ({
    task: TOOL_META[step.tool]?.label || step.tool,
    api: TOOL_META[step.tool]?.api || step.action,
    icon: TOOL_META[step.tool]?.icon || "⚙️",
    type: TOOL_META[step.tool]?.type || "ai",
  }));

  // ── Recovery tracking ──
  let retriedCount = 0;
  let fallbackCount = 0;
  let continuedCount = 0;

  const logs = [{ icon: "info", text: `Prompt received: ${response.prompt || ""}` }];
  steps.forEach((step) => {
    const message = step.result?.message || `${step.tool}.${step.action} finished`;
    const icon =
      step.status === "success" ? "success" :
        step.status === "waiting_approval" ? "warning" :
          step.status === "waiting_user_input" ? "warning" :
            step.status === "failed" ? "error" :
              "info";

    let badge = "";
    const r = step.result || {};
    if (r.recovery_status === "retried") {
      badge = ` 🔄 retried×${r.retry_count}`;
      retriedCount++;
    } else if (r.recovery_status === "fallback") {
      badge = " 🛡️ fallback";
      fallbackCount++;
    } else if (r.recovery_status === "continued_after_failure") {
      badge = " ⏩ continued";
      continuedCount++;
    }

    logs.push({ icon, text: `Step ${step.step_id} • ${step.tool} — ${message}${badge}` });
  });

  const successfulSteps = steps.filter((step) => step.status === "success").length;
  const completion = steps.length ? Math.round((successfulSteps / steps.length) * 100) : 0;

  let status = "Running";
  if (run.status === "completed") status = "Success";
  if (run.status === "waiting_approval") status = "Approval Needed";
  if (run.status === "waiting_user_input") status = "Input Needed";
  if (run.status === "failed") status = "Failed";
  if (run.status === "failed_rolled_back") status = "Rolled Back";

  let suggestion =
    run.status === "waiting_approval"
      ? "The workflow is paused at an approval step. Click the Approve button in the modal to resume execution."
      : run.status === "waiting_user_input"
        ? "The workflow needs your custom input. Fill in the step editor modal to continue."
        : run.status === "completed"
          ? "The prompt was converted into executable workflow steps and completed successfully via real API connectors."
          : run.status === "failed_rolled_back"
            ? "The workflow failed and all previous steps have been rolled back. Check the execution logs for details."
            : "The generated workflow needs follow-up. Add retry rules or connector-specific validation for more resilience.";

  const recoveryParts = [];
  if (retriedCount) recoveryParts.push(`${retriedCount} retried`);
  if (fallbackCount) recoveryParts.push(`${fallbackCount} fallback`);
  if (continuedCount) recoveryParts.push(`${continuedCount} continued after failure`);
  if (recoveryParts.length) {
    suggestion += ` Self-healing engine activated: ${recoveryParts.join(", ")}.`;
  }

  // Compute elapsed execution time safely
  let elapsed = "—";
  if (run.created_at) {
    const startMs = new Date(run.created_at).getTime();
    // If run is complete, try to use a completed timestamp, else just show what we had when it finished
    const endMs = (run.status === "completed" || run.status === "failed") && run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
    const ms = endMs - startMs;
    // Cap at 0 just in case clock skew
    if (ms > 0) {
      elapsed = ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
    }
  } else if (execStartTime) {
    const ms = Date.now() - execStartTime;
    elapsed = ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  }


  return {
    nodes,
    tools,
    logs,
    learning: {
      status,
      steps: `${steps.length} step${steps.length === 1 ? "" : "s"}`,
      time: elapsed,
      score: `${completion}%`,
      suggestion,
      barLabel: "Workflow Completion",
      barValue: completion,
    },
  };
}

// ============================================================
//  LIVE EXECUTION POLLING
// ============================================================

function startPolling(runId) {
  if (pollInterval) clearInterval(pollInterval);
  currentRunId = runId;

  const consoleStatusEl = document.getElementById("consoleStatus");
  consoleStatusEl.textContent = "Running";
  consoleStatusEl.className = "panel-status running";

  const container = document.getElementById("consoleContainer");
  container.innerHTML = "";
  addConsoleLog("Workflow execution started. Polling for updates...", "info");

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/run/${runId}`, { headers: authHeaders() });
      if (!resp.ok) return;
      const run = await resp.json();

      // Update DAG nodes in real-time
      const steps = run.steps || [];
      steps.forEach((step, i) => {
        updateNodeStatus(i, step.status);
      });

      // Terminal states
      if (run.status === "completed") {
        clearInterval(pollInterval);
        pollInterval = null;
        consoleStatusEl.textContent = "Completed";
        consoleStatusEl.className = "panel-status done";
        addConsoleLog("✅ Workflow completed successfully!", "success");
        showToast("Workflow completed!", "success");

        // Render final learning
        const viz = buildVisualizationFromResponse({ run, prompt: "" });
        renderLearning(viz.learning);

        // Try to fetch execution logs
        fetchLearningInsights(runId);
        return;
      }

      if (run.status === "failed" || run.status === "failed_rolled_back") {
        clearInterval(pollInterval);
        pollInterval = null;
        consoleStatusEl.textContent = run.status === "failed_rolled_back" ? "Rolled Back" : "Failed";
        consoleStatusEl.className = "panel-status";

        const failedStep = steps.find(s => s.status === "failed");
        if (failedStep) {
          addConsoleLog(`Step ${failedStep.step_id} (${failedStep.tool}) failed: ${failedStep.result?.message || "Unknown error"}`, "error");
        }

        if (run.status === "failed_rolled_back") {
          addConsoleLog("All previous steps have been rolled back.", "warning");
        }

        showToast(run.status === "failed_rolled_back" ? "Workflow failed & rolled back" : "Workflow failed", "error");

        const viz = buildVisualizationFromResponse({ run, prompt: "" });
        renderLearning(viz.learning);
        return;
      }

      if (run.status === "waiting_approval") {
        clearInterval(pollInterval);
        pollInterval = null;
        consoleStatusEl.textContent = "Awaiting Approval";
        consoleStatusEl.className = "panel-status active";
        addConsoleLog("Workflow paused — approval required.", "warning");
        showApprovalModal(runId, steps);
        return;
      }

      if (run.status === "waiting_user_input") {
        clearInterval(pollInterval);
        pollInterval = null;
        consoleStatusEl.textContent = "Input Needed";
        consoleStatusEl.className = "panel-status active";
        addConsoleLog("Workflow paused — your input is needed.", "warning");
        showStepEditorModal(runId, steps);
        return;
      }

      // Update console with running step info
      const runningStep = steps.find(s => s.status === "running");
      if (runningStep) {
        const label = TOOL_META[runningStep.tool]?.label || runningStep.tool;
        addConsoleLog(`Executing: ${label} (Step ${runningStep.step_id})`, "info");
      }

      // Log completed steps
      steps.forEach(step => {
        if (step.status === "success" && step.result) {
          const logKey = `logged-${runId}-${step.step_id}`;
          if (!window[logKey]) {
            window[logKey] = true;
            addConsoleLog(`Step ${step.step_id} • ${step.tool} — ${step.result.message || "Done"}`, "success");
          }
        }
      });

    } catch (err) {
      console.warn("Poll error:", err);
    }
  }, 1500);
}

async function fetchLearningInsights(runId) {
  try {
    const resp = await fetch(`${API_BASE_URL}/logs/${runId}`, { headers: authHeaders() });
    if (resp.ok) {
      const logs = await resp.json();
      document.getElementById("learningStatus").textContent = `${logs.length} log entries`;
    }
  } catch {
    // /logs endpoint may not exist yet (Member 1's task)
  }
}

// ============================================================
//  STEP EDITOR MODAL (Custom Workflow Input)
// ============================================================

let pendingEditorRunId = null;
let pendingEditorStepId = null;

function showStepEditorModal(runId, steps) {
  const modal = document.getElementById("stepEditorModal");
  const waitingStep = steps.find(s => s.status === "waiting_user_input");

  if (!waitingStep) return;

  pendingEditorRunId = runId;
  pendingEditorStepId = waitingStep.step_id;

  const label = TOOL_META[waitingStep.tool]?.label || waitingStep.tool;
  const question = waitingStep.params?.question || waitingStep.params?.raw_input || "Please provide your custom input for this step.";

  document.getElementById("stepEditorBadge").textContent = `Step ${waitingStep.step_id}`;
  document.getElementById("stepEditorStepName").textContent = label;
  document.getElementById("stepEditorPrompt").textContent = question;
  document.getElementById("stepEditorInput").value = "";
  document.getElementById("stepEditorInput").placeholder = `E.g., customize the ${label.toLowerCase()}...`;

  modal.classList.add("visible");
  showToast("Your input is needed to continue the workflow", "info");
}

async function submitStepEdit() {
  const input = document.getElementById("stepEditorInput").value.trim();
  const modal = document.getElementById("stepEditorModal");

  if (!pendingEditorRunId || !pendingEditorStepId) return;

  modal.classList.remove("visible");
  addConsoleLog(`User input submitted for Step ${pendingEditorStepId}: "${input || "(default)"}"`, "success");
  showToast("Input submitted — resuming workflow", "success");

  try {
    await fetch(`${API_BASE_URL}/submit-user-input`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        run_id: pendingEditorRunId,
        step_id: pendingEditorStepId,
        params: { body: input || "(default)" },
      }),
    });
  } catch (err) {
    console.warn("submit-user-input failed:", err);
    showToast("Failed to submit input — check backend connection", "error");
  }

  // Resume polling
  startPolling(pendingEditorRunId);
  pendingEditorRunId = null;
  pendingEditorStepId = null;
}

function skipStepEdit() {
  document.getElementById("stepEditorInput").value = "";
  submitStepEdit();
}

// ============================================================
//  APPROVAL MODAL
// ============================================================

let pendingApprovalRunId = null;
let pendingApprovalStepId = null;

function showApprovalModal(runId, steps) {
  const modal = document.getElementById("approvalModal");
  const list = document.getElementById("approvalStepsList");
  list.innerHTML = "";

  const waitingStep = steps.find(s => s.status === "waiting_approval");
  if (!waitingStep) return;

  pendingApprovalRunId = runId;
  pendingApprovalStepId = waitingStep.step_id;

  // Show all steps with their status
  steps.forEach((step, i) => {
    const label = TOOL_META[step.tool]?.label || step.tool;
    const statusIcon = step.status === "success" ? "✓" :
      step.status === "waiting_approval" ? "⏸" :
        step.status === "failed" ? "✕" :
          step.status === "pending" ? "○" : "●";

    const item = document.createElement("div");
    item.className = "approval-step-item";
    item.innerHTML = `
      <span class="approval-step-num">${statusIcon}</span>
      <span class="approval-step-tool">${escapeHTML(label)}</span>
      <span class="approval-step-action">${escapeHTML(step.action)}</span>
    `;
    list.appendChild(item);
  });

  modal.classList.add("visible");
  showToast("Workflow paused — approval required", "warning");
}

async function approveWorkflow() {
  const modal = document.getElementById("approvalModal");
  modal.classList.remove("visible");

  if (!pendingApprovalRunId || !pendingApprovalStepId) return;

  addConsoleLog(`Approval granted for Step ${pendingApprovalStepId}`, "success");
  showToast("Approved! Resuming workflow...", "success");

  try {
    const resp = await fetch(`${API_BASE_URL}/approve-step`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        run_id: pendingApprovalRunId,
        step_id: pendingApprovalStepId,
      }),
    });

    if (resp.ok) {
      // Resume polling to track remaining steps
      startPolling(pendingApprovalRunId);
    } else {
      const err = await resp.json();
      addConsoleLog(`Approval failed: ${err.detail || "Unknown error"}`, "error");
      showToast("Approval failed", "error");
    }
  } catch (err) {
    console.warn("Approval request failed:", err);
    showToast("Failed to reach backend", "error");
  }

  pendingApprovalRunId = null;
  pendingApprovalStepId = null;
}

function rejectWorkflow() {
  const modal = document.getElementById("approvalModal");
  modal.classList.remove("visible");

  addConsoleLog("Workflow rejected by user.", "error");
  showToast("Workflow rejected", "error");

  document.getElementById("consoleStatus").textContent = "Rejected";
  document.getElementById("consoleStatus").className = "panel-status";

  pendingApprovalRunId = null;
  pendingApprovalStepId = null;
}

// ============================================================
//  VOICE-TO-TEXT INPUT (Enhanced)
//  - Real-time interim results (words appear as you speak)
//  - Continuous mode (keeps listening until you stop it)
//  - Visual listening indicator with animated bars
//  - Appends to existing text instead of overwriting
//  - Specific error messages for common failures
// ============================================================

let recognition = null;
let voiceTranscriptBefore = ""; // text that was in the input before voice started

function startVoiceInput() {
  const voiceBtn = document.getElementById("voiceBtn");
  const promptInput = document.getElementById("promptInput");
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  // ── Unsupported browser ──
  if (!SpeechRecognition) {
    showToast("Voice input not supported in this browser. Try Chrome or Edge.", "error");
    voiceBtn.classList.add("unsupported");
    voiceBtn.title = "Voice input not supported";
    return;
  }

  // ── Toggle off if already recording ──
  if (recognition) {
    recognition.stop();
    recognition = null;
    voiceBtn.classList.remove("recording");
    voiceBtn.innerHTML = getMicSVG();
    showToast("Voice input stopped", "info");
    return;
  }

  // ── Start new session ──
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;   // Show words as they're spoken
  recognition.continuous = true;       // Keep listening until manually stopped
  recognition.maxAlternatives = 1;

  // Remember any text already in the input so we can append
  voiceTranscriptBefore = promptInput.value;

  voiceBtn.classList.add("recording");
  voiceBtn.innerHTML = getListeningSVG();
  showToast("🎤 Listening... speak your workflow prompt. Click mic again to stop.", "info");

  // ── Real-time transcript ──
  recognition.onresult = (event) => {
    let interimTranscript = "";
    let finalTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += text;
      } else {
        interimTranscript += text;
      }
    }

    // Build the full text: previous text + final chunks so far + current interim
    const prefix = voiceTranscriptBefore ? voiceTranscriptBefore.trimEnd() + " " : "";
    const display = prefix + finalTranscript + interimTranscript;
    promptInput.value = display;

    // Update the stored "before" text as final chunks arrive
    if (finalTranscript) {
      voiceTranscriptBefore = prefix + finalTranscript;
    }
  };

  // ── Error handling with specific messages ──
  recognition.onerror = (event) => {
    console.warn("Speech recognition error:", event.error);
    const messages = {
      "not-allowed": "Microphone access denied. Please allow mic permissions.",
      "no-speech": "No speech detected. Try again in a quieter environment.",
      "audio-capture": "No microphone found. Check your audio device.",
      "network": "Network error during speech recognition.",
    };
    if (event.error !== "aborted") {
      showToast(messages[event.error] || `Voice error: ${event.error}`, "error");
    }
  };

  // ── Cleanup when recognition ends ──
  recognition.onend = () => {
    voiceBtn.classList.remove("recording");
    voiceBtn.innerHTML = getMicSVG();
    if (recognition) {
      // Show success if we actually captured text
      const captured = promptInput.value.trim();
      if (captured && captured !== voiceTranscriptBefore.trim()) {
        showToast(`✓ Voice captured: "${captured.substring(0, 60)}${captured.length > 60 ? '...' : ''}"`, "success");
      }
    }
    recognition = null;
  };

  try {
    recognition.start();
  } catch (err) {
    console.warn("Failed to start speech recognition:", err);
    showToast("Could not start voice input. Check microphone permissions.", "error");
    voiceBtn.classList.remove("recording");
    voiceBtn.innerHTML = getMicSVG();
    recognition = null;
  }
}

// ── SVG helpers for mic button states ──

function getMicSVG() {
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>`;
}

function getListeningSVG() {
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" class="voice-bars">
    <rect x="4"  y="8"  width="3" height="8" rx="1.5" fill="currentColor" class="bar bar-1"/>
    <rect x="10" y="4"  width="3" height="16" rx="1.5" fill="currentColor" class="bar bar-2"/>
    <rect x="16" y="6"  width="3" height="12" rx="1.5" fill="currentColor" class="bar bar-3"/>
  </svg>`;
}

// ============================================================
//  BACKEND API CALLS
// ============================================================

async function requestWorkflowFromBackend(prompt) {
  const response = await fetch(`${API_BASE_URL}/run-prompt`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ prompt }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Failed to generate workflow");
  }
  return data;
}

// ============================================================
//  FALLBACK (OFFLINE) WORKFLOW
// ============================================================

async function renderFallbackWorkflow(prompt, errorMessage) {
  execStartTime = Date.now(); // Start timer for demo mode
  const template = WORKFLOW_TEMPLATES[detectTemplate(prompt)];
  document.getElementById("dagStatus").textContent = `${template.nodes.length} steps`;
  document.getElementById("dagStatus").className = "panel-status done";
  document.getElementById("toolsStatus").textContent = `${template.tools.length} tools`;
  document.getElementById("toolsStatus").className = "panel-status done";
  document.getElementById("consoleStatus").textContent = "Offline Demo";
  document.getElementById("consoleStatus").className = "panel-status";
  renderDAG(template.nodes);
  renderTools(template.tools);

  document.getElementById("workflow-section").scrollIntoView({ behavior: "smooth", block: "start" });

  await sleep(800);
  document.getElementById("learningStatus").textContent = "Analyzing...";
  document.getElementById("learningStatus").className = "panel-status active";
  await runExecution(template.logs, template.nodes);

  renderLearning({
    ...template.learning,
    suggestion: `${template.learning.suggestion} ${errorMessage ? ` (${errorMessage})` : ""}`.trim(),
  });
}

// ============================================================
//  MAIN WORKFLOW GENERATION
// ============================================================

async function generateWorkflow() {
  const input = document.getElementById("promptInput");
  const btn = document.getElementById("generateBtn");
  const prompt = input.value.trim();
  if (!prompt || isGenerating) return;

  isGenerating = true;
  execStartTime = Date.now(); // Start timer for real backend execution
  btn.classList.add("loading");

  // Clear any previous polling
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }

  document.getElementById("dagStatus").textContent = "Generating...";
  document.getElementById("dagStatus").className = "panel-status active";
  document.getElementById("toolsStatus").textContent = "Mapping...";
  document.getElementById("toolsStatus").className = "panel-status active";
  document.getElementById("consoleStatus").textContent = "Contacting API";
  document.getElementById("consoleStatus").className = "panel-status active";
  document.getElementById("learningStatus").textContent = "Waiting...";
  document.getElementById("learningStatus").className = "panel-status";

  try {
    const response = await requestWorkflowFromBackend(prompt);
    const visualization = buildVisualizationFromResponse(response);
    const run = response.run || {};
    currentRunId = run.run_id;

    // Render DAG
    document.getElementById("dagStatus").textContent = `${visualization.nodes.length} steps`;
    document.getElementById("dagStatus").className = "panel-status done";
    renderDAG(visualization.nodes);

    await sleep(220);

    // Render tools
    document.getElementById("toolsStatus").textContent = `${visualization.tools.length} tools`;
    document.getElementById("toolsStatus").className = "panel-status done";
    renderTools(visualization.tools);

    await sleep(320);
    document.getElementById("workflow-section").scrollIntoView({ behavior: "smooth", block: "start" });

    btn.classList.remove("loading");

    // Check if we need user interaction
    if (run.status === "waiting_user_input") {
      showStepEditorModal(run.run_id, run.steps || []);
      // Initial console setup
      const container = document.getElementById("consoleContainer");
      container.innerHTML = "";
      addConsoleLog(`Prompt received: ${prompt}`, "info");
      // Log completed steps
      (run.steps || []).forEach(step => {
        if (step.status === "success" && step.result) {
          addConsoleLog(`Step ${step.step_id} • ${step.tool} — ${step.result.message || "Done"}`, "success");
        }
      });
      addConsoleLog("Workflow paused — your input is needed.", "warning");
      document.getElementById("consoleStatus").textContent = "Input Needed";
      document.getElementById("consoleStatus").className = "panel-status active";
      return;
    }

    if (run.status === "waiting_approval") {
      showApprovalModal(run.run_id, run.steps || []);
      const container = document.getElementById("consoleContainer");
      container.innerHTML = "";
      addConsoleLog(`Prompt received: ${prompt}`, "info");
      (run.steps || []).forEach(step => {
        if (step.status === "success" && step.result) {
          addConsoleLog(`Step ${step.step_id} • ${step.tool} — ${step.result.message || "Done"}`, "success");
        }
      });
      addConsoleLog("Workflow paused — approval required.", "warning");
      document.getElementById("consoleStatus").textContent = "Awaiting Approval";
      document.getElementById("consoleStatus").className = "panel-status active";
      return;
    }

    if (run.status === "completed") {
      // Already finished — show execution logs
      await sleep(420);
      document.getElementById("learningStatus").textContent = "Analyzing...";
      document.getElementById("learningStatus").className = "panel-status active";
      await runExecution(visualization.logs, visualization.nodes);
      renderLearning(visualization.learning);
      showToast("Workflow completed!", "success");
      return;
    }

    if (run.status === "failed" || run.status === "failed_rolled_back") {
      await sleep(420);
      await runExecution(visualization.logs, visualization.nodes);
      renderLearning(visualization.learning);
      showToast(run.status === "failed_rolled_back" ? "Workflow failed & rolled back" : "Workflow failed", "error");
      return;
    }

    // Still running — start polling
    if (run.status === "running") {
      startPolling(run.run_id);
    } else {
      // Fallback: show logs
      await sleep(420);
      document.getElementById("learningStatus").textContent = "Analyzing...";
      document.getElementById("learningStatus").className = "panel-status active";
      await runExecution(visualization.logs, visualization.nodes);
      renderLearning(visualization.learning);
    }

  } catch (error) {
    console.warn("Backend unavailable or failed. Using fallback.", error);
    showToast("Backend offline — showing demo mode", "warning");
    renderFallbackWorkflow(prompt, error.message);
  } finally {
    btn.classList.remove("loading");
    isGenerating = false;
  }
}

// ============================================================
//  BACKEND HEALTH CHECK
// ============================================================

async function checkBackendHealth() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    if (res.ok) {
      if (dot) dot.style.background = "var(--accent-emerald)";
      if (text) text.textContent = "Backend Connected — Agentic MCP Gateway Live";
      return true;
    }
    throw new Error("unhealthy");
  } catch {
    if (dot) dot.style.background = "var(--accent-amber)";
    if (text) text.textContent = "Offline Mode — Demo Templates Active";
    return false;
  }
}

// ============================================================
//  TYPING PLACEHOLDER EFFECT
// ============================================================

function initTypingPlaceholder() {
  const prompts = [
    "When a bug is reported, create a GitHub issue and email the team lead...",
    "Every Monday, pull the sales report and email it to the team...",
    "When a PR is opened, analyze the code and email the reviewer...",
    "Log customer feedback in Sheets and create a Jira ticket...",
    "Send an email to the team when a critical issue is detected...",
  ];
  const input = document.getElementById("promptInput");
  let promptIdx = 0;
  let charIdx = 0;
  let deleting = false;
  let pauseCounter = 0;

  function tick() {
    if (input === document.activeElement || input.value.length > 0) {
      setTimeout(tick, 200);
      return;
    }

    const current = prompts[promptIdx];

    if (!deleting) {
      input.placeholder = current.substring(0, charIdx + 1);
      charIdx++;
      if (charIdx >= current.length) {
        deleting = true;
        pauseCounter = 15;
      }
    } else if (pauseCounter > 0) {
      pauseCounter--;
    } else {
      input.placeholder = current.substring(0, charIdx);
      charIdx--;
      if (charIdx <= 0) {
        deleting = false;
        promptIdx = (promptIdx + 1) % prompts.length;
      }
    }

    setTimeout(tick, deleting && pauseCounter === 0 ? 30 : 60);
  }

  setTimeout(tick, 1000);
}

// ============================================================
//  EVENT LISTENERS
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  // Auth gate — redirect to login if no token
  if (!requireAuth()) return;

  initGrid();
  initNavbar();
  initTypingPlaceholder();
  renderUserMenu();
  checkBackendHealth();

  document.getElementById("generateBtn").addEventListener("click", generateWorkflow);

  document.getElementById("promptInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      generateWorkflow();
    }
  });

  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      const input = document.getElementById("promptInput");
      input.value = prompt;
      input.focus();

      document.querySelectorAll(".example-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
    });
  });

  document.querySelectorAll('.nav-link[href^="#"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const target = document.querySelector(link.getAttribute("href"));
      if (target) target.scrollIntoView({ behavior: "smooth" });
    });
  });

  // Close modals on overlay click
  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("visible");
      }
    });
  });

  // Close modals on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay.visible").forEach(m => m.classList.remove("visible"));
    }
  });
});