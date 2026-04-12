/* ============================================================
   FlowMind AI - Application Logic
   Uses the backend prompt endpoint when available and falls
   back to local demo templates when the API is offline.
   ============================================================ */

const API_BASE_URL = "http://127.0.0.1:8000";

const WORKFLOW_TEMPLATES = {
  bug: {
    nodes: [
      { title: "Fetch Issue Context", detail: "Collect issue metadata from the project system", icon: "📥" },
      { title: "Create GitHub Issue", detail: "Open a follow-up issue for engineering", icon: "🐙" },
      { title: "Send Slack Alert", detail: "Notify the engineering channel", icon: "💬" },
      { title: "Request Approval", detail: "Pause for human confirmation", icon: "✅" },
    ],
    tools: [
      { task: "Fetch Issue Context", api: "Mock PM Connector", icon: "📥", type: "ai" },
      { task: "Create GitHub Issue", api: "GitHub Connector", icon: "🐙", type: "github" },
      { task: "Send Slack Message", api: "Slack Connector", icon: "💬", type: "slack" },
      { task: "Approval Gate", api: "Workflow Runtime", icon: "✅", type: "ai" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: backend unavailable, showing a local workflow simulation." },
      { icon: "success", text: "Generated a critical issue workflow from the prompt." },
      { icon: "success", text: "Mapped the workflow to mock PM, GitHub, Slack, and approval connectors." },
      { icon: "warning", text: "Execution paused at approval gate in demo mode." },
    ],
    learning: {
      status: "Demo Mode",
      time: "4 steps",
      score: "75%",
      suggestion: "Start the backend to generate real steps from the prompt and execute the live runtime instead of the local simulation.",
      barLabel: "Backend Connectivity",
      barValue: 25,
    },
  },
  sales: {
    nodes: [
      { title: "Read Sales Source", detail: "Collect weekly numbers from the source sheet", icon: "📊" },
      { title: "Update Tracking Sheet", detail: "Persist the report data", icon: "📈" },
      { title: "Send Slack Summary", detail: "Notify the sales channel", icon: "💬" },
    ],
    tools: [
      { task: "Read Sales Source", api: "Planning Heuristic", icon: "📊", type: "ai" },
      { task: "Update Google Sheet", api: "Sheets Connector", icon: "📈", type: "sheets" },
      { task: "Send Slack Message", api: "Slack Connector", icon: "💬", type: "slack" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: using the local sales-report template." },
      { icon: "success", text: "Prepared a weekly report workflow from the prompt." },
      { icon: "success", text: "Connected the plan to Sheets and Slack." },
    ],
    learning: {
      status: "Demo Mode",
      time: "3 steps",
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
      { title: "Send Reviewer Notification", detail: "Notify the reviewer on Slack", icon: "💬" },
    ],
    tools: [
      { task: "Inspect PR Context", api: "Planning Heuristic", icon: "📥", type: "ai" },
      { task: "Create GitHub Issue", api: "GitHub Connector", icon: "🐙", type: "github" },
      { task: "Send Slack Message", api: "Slack Connector", icon: "💬", type: "slack" },
    ],
    logs: [
      { icon: "info", text: "Demo mode: using the PR workflow template." },
      { icon: "success", text: "Generated a review workflow from the prompt." },
      { icon: "success", text: "Mapped tasks to GitHub and Slack connectors." },
    ],
    learning: {
      status: "Demo Mode",
      time: "3 steps",
      score: "67%",
      suggestion: "Run the backend to produce real generated steps and execution results for pull-request prompts.",
      barLabel: "Runtime Readiness",
      barValue: 35,
    },
  },
};

const TOOL_META = {
  mock_pm: { label: "Fetch Issue Context", api: "Mock PM Connector", icon: "📥", type: "ai" },
  slack: { label: "Send Slack Message", api: "Slack Connector", icon: "💬", type: "slack" },
  github: { label: "Create GitHub Issue", api: "GitHub Connector", icon: "🐙", type: "github" },
  sheets: { label: "Update Google Sheet", api: "Sheets Connector", icon: "📊", type: "sheets" },
  approval: { label: "Request Approval", api: "Workflow Runtime", icon: "✅", type: "ai" },
};

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
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += gap) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
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
        <div class="stat-value time">${escapeHTML(data.time)}</div>
        <div class="stat-label">Exec Time</div>
      </div>
      <div class="stat-card" id="stat-2">
        <div class="stat-value score">${escapeHTML(data.score)}</div>
        <div class="stat-label">Confidence</div>
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
  setTimeout(() => {
    document.getElementById("insight-main")?.classList.add("visible");
    setTimeout(() => {
      const barFill = document.getElementById("insightBarFill");
      if (barFill) barFill.style.width = `${data.barValue}%`;
    }, 240);
  }, 480);
}

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

  // ── Recovery tracking (additive – does not change existing log shape) ──
  let retriedCount = 0;
  let fallbackCount = 0;
  let continuedCount = 0;

  const logs = [{ icon: "info", text: `Prompt received: ${response.prompt || ""}` }];
  steps.forEach((step) => {
    const message = step.result?.message || `${step.tool}.${step.action} finished`;
    const icon =
      step.status === "success" ? "success" :
      step.status === "waiting_approval" ? "warning" :
      step.status === "failed" ? "error" :
      "info";

    // Build recovery badge string (empty when no recovery occurred)
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
  if (run.status === "failed") status = "Failed";

  // Build suggestion – append recovery summary when applicable
  let suggestion =
    run.status === "waiting_approval"
      ? "The workflow is paused at an approval step. Calling the approval endpoint will resume execution from the next task."
      : run.status === "completed"
        ? "The prompt was converted into executable workflow steps and completed successfully. The next upgrade would be replacing mock connectors with real APIs."
        : "The generated workflow needs follow-up. Add retry rules or connector-specific validation for more resilience.";

  const recoveryParts = [];
  if (retriedCount) recoveryParts.push(`${retriedCount} retried`);
  if (fallbackCount) recoveryParts.push(`${fallbackCount} fallback`);
  if (continuedCount) recoveryParts.push(`${continuedCount} continued after failure`);
  if (recoveryParts.length) {
    suggestion += ` Self-healing engine activated: ${recoveryParts.join(", ")}.`;
  }

  return {
    nodes,
    tools,
    logs,
    learning: {
      status,
      time: `${steps.length} step${steps.length === 1 ? "" : "s"}`,
      score: `${completion}%`,
      suggestion,
      barLabel: "Workflow Completion",
      barValue: completion,
    },
  };
}

async function requestWorkflowFromBackend(prompt) {
  const response = await fetch(`${API_BASE_URL}/run-prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Failed to generate workflow");
  }
  return data;
}

async function renderFallbackWorkflow(prompt, errorMessage) {
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

let isGenerating = false;

async function generateWorkflow() {
  const input = document.getElementById("promptInput");
  const btn = document.getElementById("generateBtn");
  const prompt = input.value.trim();
  if (!prompt || isGenerating) return;

  isGenerating = true;
  btn.classList.add("loading");

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

    document.getElementById("dagStatus").textContent = `${visualization.nodes.length} steps`;
    document.getElementById("dagStatus").className = "panel-status done";
    renderDAG(visualization.nodes);

    await sleep(220);
    document.getElementById("toolsStatus").textContent = `${visualization.tools.length} tools`;
    document.getElementById("toolsStatus").className = "panel-status done";
    renderTools(visualization.tools);

    await sleep(320);
    document.getElementById("workflow-section").scrollIntoView({ behavior: "smooth", block: "start" });

    btn.classList.remove("loading");

    await sleep(420);
    document.getElementById("learningStatus").textContent = "Analyzing...";
    document.getElementById("learningStatus").className = "panel-status active";
    await runExecution(visualization.logs, visualization.nodes);
    renderLearning(visualization.learning);

  } catch (error) {
    console.warn("Backend unavailable or failed. Using fallback.", error);
    renderFallbackWorkflow(prompt, error.message);
  } finally {
    btn.classList.remove("loading");
    isGenerating = false;
  }
}

// ─── Backend Health Check ────────────────────────────────────

async function checkBackendHealth() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const res = await fetch(`${API_BASE_URL}/run/nonexistent`, { method: "GET" });
    // Even a 404 means the server is alive
    if (dot) dot.style.background = "var(--accent-emerald)";
    if (text) text.textContent = "Backend Connected — Agentic Workflow Orchestration";
    return true;
  } catch {
    if (dot) dot.style.background = "var(--accent-amber)";
    if (text) text.textContent = "Offline Mode — Demo Templates Active";
    return false;
  }
}

// ─── Typing Placeholder Effect ───────────────────────────────

function initTypingPlaceholder() {
  const prompts = [
    "When a bug is reported, create a GitHub issue and notify Slack...",
    "Every Monday, pull the sales report and post it to #sales...",
    "When a PR is opened, analyze the code and notify the reviewer...",
    "Log customer feedback in Sheets and alert the product team...",
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
        pauseCounter = 15; // pause before deleting
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

// ─── Auth State Management (Member 1 — non-invasive) ─────────

let currentUser = null;

async function checkAuthState() {
  const signInBtn = document.getElementById("signInBtn");
  const userInfo = document.getElementById("userInfo");
  const userAvatar = document.getElementById("userAvatar");
  const userName = document.getElementById("userName");

  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      credentials: "include",
    });
    if (res.ok) {
      const data = await res.json();
      currentUser = data;
      // Show user info, hide sign-in
      if (signInBtn) signInBtn.style.display = "none";
      if (userInfo) userInfo.style.display = "flex";
      if (userAvatar) {
        userAvatar.src = data.picture_url || "";
        userAvatar.style.display = data.picture_url ? "block" : "none";
      }
      if (userName) userName.textContent = data.name || data.email;
      return true;
    }
  } catch {
    // Not authenticated or backend offline — that's fine
  }

  // Not authenticated — show sign-in button
  currentUser = null;
  if (signInBtn) signInBtn.style.display = "flex";
  if (userInfo) userInfo.style.display = "none";
  return false;
}

function handleLogout() {
  fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).finally(() => {
    currentUser = null;
    checkAuthState();
  });
}

// ─── Event Listeners ─────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initGrid();
  initNavbar();
  initTypingPlaceholder();
  checkBackendHealth();
  checkAuthState();

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

      // Highlight the selected chip
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

  // Auth: logout button
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
});
