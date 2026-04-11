/* ============================================================
   FlowMind AI — Application Logic
   Handles prompt input, DAG generation, execution simulation,
   tool mapping, and learning insights.
   ============================================================ */

// ─── Workflow Templates ───────────────────────────────────────
const WORKFLOW_TEMPLATES = {
  bug: {
    title: "Critical Bug Escalation",
    nodes: [
      { title: "Fetch GitHub Issue", detail: "Pull issue metadata & labels", icon: "📥" },
      { title: "Analyze Severity", detail: "LLM classifies priority level", icon: "🧠" },
      { title: "Send Slack Alert", detail: "Notify #engineering channel", icon: "💬" },
      { title: "Update Escalation Tracker", detail: "Write row to Google Sheets", icon: "📊" },
      { title: "Request Manager Approval", detail: "Human-in-the-loop gate", icon: "✅" },
    ],
    tools: [
      { task: "Fetch Issue Data", api: "GitHub REST API", icon: "🐙", type: "github" },
      { task: "Classify Severity", api: "LLM Agent (GPT-4)", icon: "🧠", type: "ai" },
      { task: "Notify Engineering", api: "Slack Web API", icon: "💬", type: "slack" },
      { task: "Log to Tracker", api: "Google Sheets API", icon: "📊", type: "sheets" },
      { task: "Approval Gate", api: "Internal Workflow Engine", icon: "🔐", type: "ai" },
    ],
    logs: [
      { icon: "info", text: "Initializing workflow pipeline..." },
      { icon: "success", text: "Connected to <span class='highlight'>GitHub API</span>" },
      { icon: "success", text: "Issue <span class='value'>#1847</span> fetched — <span class='highlight'>\"Login page crashes on mobile\"</span>" },
      { icon: "success", text: "Severity classified as <span class='value'>CRITICAL</span> (confidence: 0.94)" },
      { icon: "success", text: "Slack message sent to <span class='highlight'>#engineering-alerts</span>" },
      { icon: "success", text: "Tracker row inserted — Sheet <span class='value'>\"Escalation Log\"</span> Row <span class='value'>142</span>" },
      { icon: "warning", text: "⏳ Awaiting manager approval from <span class='highlight'>@sarah.chen</span>..." },
      { icon: "success", text: "Approval received — priority set to <span class='value'>P0</span>" },
      { icon: "success", text: "Workflow completed in <span class='value'>12.3s</span>" },
    ],
    learning: {
      status: "Success",
      time: "12.3s",
      score: "94%",
      suggestion: "Pre-approved escalation rules for known critical patterns can reduce approval delay by <span class='opt-highlight'>~30%</span>. Consider auto-routing P0 issues when severity confidence exceeds 0.95.",
      barLabel: "Optimization Potential",
      barValue: 72,
    },
  },
  sales: {
    title: "Weekly Sales Report",
    nodes: [
      { title: "Schedule Trigger", detail: "Cron: Every Monday 9:00 AM", icon: "⏰" },
      { title: "Pull Sales Data", detail: "Fetch from Google Sheets", icon: "📊" },
      { title: "Generate Summary", detail: "LLM creates executive brief", icon: "🧠" },
      { title: "Format Report", detail: "Structure with charts & KPIs", icon: "📈" },
      { title: "Post to Slack", detail: "Send to #sales channel", icon: "💬" },
    ],
    tools: [
      { task: "Trigger on Schedule", api: "Cron Scheduler", icon: "⏰", type: "ai" },
      { task: "Fetch Sales Data", api: "Google Sheets API", icon: "📊", type: "sheets" },
      { task: "Summarize Data", api: "LLM Agent (GPT-4)", icon: "🧠", type: "ai" },
      { task: "Format as Report", api: "Template Engine", icon: "📄", type: "ai" },
      { task: "Post to Channel", api: "Slack Web API", icon: "💬", type: "slack" },
    ],
    logs: [
      { icon: "info", text: "Cron trigger activated — <span class='highlight'>Monday 9:00 AM</span>" },
      { icon: "success", text: "Connected to <span class='highlight'>Google Sheets API</span>" },
      { icon: "success", text: "Fetched <span class='value'>247 rows</span> from \"Weekly Sales\" sheet" },
      { icon: "success", text: "LLM generated executive summary — <span class='value'>3 key insights</span>" },
      { icon: "success", text: "Report formatted with KPI cards and trend charts" },
      { icon: "success", text: "Posted to <span class='highlight'>#sales</span> — <span class='value'>14 reactions</span> in first hour" },
      { icon: "success", text: "Workflow completed in <span class='value'>8.7s</span>" },
    ],
    learning: {
      status: "Success",
      time: "8.7s",
      score: "97%",
      suggestion: "Historical data shows <span class='opt-highlight'>Tuesday posts get 22% more engagement</span>. Consider shifting schedule. Also, caching last week's data can reduce fetch time by ~40%.",
      barLabel: "Report Quality Score",
      barValue: 88,
    },
  },
  pr: {
    title: "PR Auto-Review Pipeline",
    nodes: [
      { title: "Detect New PR", detail: "GitHub webhook listener", icon: "🔔" },
      { title: "Fetch Code Diff", detail: "Pull changed files & context", icon: "📄" },
      { title: "Run Code Analysis", detail: "LLM reviews code quality", icon: "🧠" },
      { title: "Post Review Comments", detail: "Inline comments on GitHub", icon: "💬" },
      { title: "Notify Reviewer", detail: "Send Slack DM to assignee", icon: "📨" },
    ],
    tools: [
      { task: "Listen for PRs", api: "GitHub Webhooks", icon: "🔔", type: "github" },
      { task: "Fetch Diff", api: "GitHub REST API", icon: "🐙", type: "github" },
      { task: "Analyze Code", api: "LLM Agent (GPT-4)", icon: "🧠", type: "ai" },
      { task: "Post Comments", api: "GitHub Reviews API", icon: "💬", type: "github" },
      { task: "DM Reviewer", api: "Slack Web API", icon: "📨", type: "slack" },
    ],
    logs: [
      { icon: "info", text: "Webhook received — PR <span class='value'>#312</span> opened by <span class='highlight'>@dev.alex</span>" },
      { icon: "success", text: "Fetched diff: <span class='value'>8 files changed</span>, +142 / -37 lines" },
      { icon: "success", text: "Code analysis complete — <span class='value'>3 suggestions</span>, <span class='value'>1 potential bug</span>" },
      { icon: "warning", text: "⚠ Detected missing null check in <span class='highlight'>auth/middleware.js:47</span>" },
      { icon: "success", text: "Posted <span class='value'>4 inline comments</span> on GitHub PR" },
      { icon: "success", text: "Slack DM sent to <span class='highlight'>@reviewer.maya</span>" },
      { icon: "success", text: "Pipeline completed in <span class='value'>6.1s</span>" },
    ],
    learning: {
      status: "Success",
      time: "6.1s",
      score: "91%",
      suggestion: "This PR author frequently misses null checks (3 of last 5 PRs). Consider adding a <span class='opt-highlight'>personalized lint rule</span> for this pattern. Review time can be reduced by ~25%.",
      barLabel: "Code Quality Trend",
      barValue: 78,
    },
  },
};

// ─── Utility Functions ────────────────────────────────────────

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function detectTemplate(prompt) {
  const lower = prompt.toLowerCase();
  if (lower.includes("bug") || lower.includes("issue") || lower.includes("escalat") || lower.includes("critical"))
    return "bug";
  if (lower.includes("sales") || lower.includes("report") || lower.includes("weekly") || lower.includes("monday"))
    return "sales";
  if (lower.includes("pull request") || lower.includes("pr ") || lower.includes("review") || lower.includes("code"))
    return "pr";
  // Default to bug for any other prompt
  return "bug";
}

function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ─── Grid Background Canvas ──────────────────────────────────

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

// ─── Navbar Scroll ────────────────────────────────────────────

function initNavbar() {
  const navbar = document.getElementById("navbar");
  window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 20);
  });
}

// ─── DAG Rendering ────────────────────────────────────────────

function renderDAG(nodes) {
  const container = document.getElementById("dagContainer");
  container.innerHTML = "";

  const wrapper = document.createElement("div");
  wrapper.className = "dag-nodes";

  nodes.forEach((node, i) => {
    // Node
    const el = document.createElement("div");
    el.className = "dag-node";
    el.id = `dag-node-${i}`;
    el.innerHTML = `
      <div class="node-step">${i + 1}</div>
      <div class="node-content">
        <div class="node-title">${node.icon} ${node.title}</div>
        <div class="node-detail">${node.detail}</div>
      </div>
      <div class="node-status-dot pending" id="node-dot-${i}"></div>
    `;
    wrapper.appendChild(el);

    // Arrow (except after last node)
    if (i < nodes.length - 1) {
      const arrow = document.createElement("div");
      arrow.className = "dag-arrow";
      arrow.id = `dag-arrow-${i}`;
      arrow.innerHTML = `<div class="arrow-line"></div><div class="arrow-head"></div>`;
      wrapper.appendChild(arrow);
    }
  });

  container.appendChild(wrapper);

  // Animate in
  nodes.forEach((_, i) => {
    setTimeout(() => {
      const nodeEl = document.getElementById(`dag-node-${i}`);
      if (nodeEl) nodeEl.classList.add("visible");
      const arrowEl = document.getElementById(`dag-arrow-${i}`);
      if (arrowEl) setTimeout(() => arrowEl.classList.add("visible"), 100);
    }, i * 180);
  });
}

// ─── Tool Mapping Rendering ──────────────────────────────────

function renderTools(tools) {
  const container = document.getElementById("toolsContainer");
  container.innerHTML = "";

  const list = document.createElement("div");
  list.className = "tools-list";

  tools.forEach((tool, i) => {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.innerHTML = `
      <div class="tool-card-icon ${tool.type}">${tool.icon}</div>
      <div class="tool-card-info">
        <div class="tool-card-task">${tool.task}</div>
        <div class="tool-card-api">${tool.api}</div>
      </div>
      <div class="tool-card-badge connected">Routed</div>
    `;
    list.appendChild(card);

    setTimeout(() => card.classList.add("visible"), i * 120 + 300);
  });

  container.appendChild(list);
}

// ─── Execution Console ───────────────────────────────────────

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

    const isLast = i === logs.length - 1;
    const isWaiting = log.text.includes("⏳") || log.text.includes("Awaiting");
    let iconHTML;

    if (log.icon === "success") iconHTML = `<span class="log-icon success">✔</span>`;
    else if (log.icon === "warning") iconHTML = `<span class="log-icon warning">⚠</span>`;
    else if (log.icon === "error") iconHTML = `<span class="log-icon error">✘</span>`;
    else iconHTML = `<span class="log-icon info">›</span>`;

    entry.innerHTML = `
      ${iconHTML}
      <span class="log-text">${log.text}</span>
      <span class="log-timestamp">${formatTimestamp()}</span>
    `;
    container.appendChild(entry);

    await sleep(80);
    entry.classList.add("visible");

    // Update corresponding DAG node
    if (i > 0 && i - 1 < nodes.length) {
      const dotIdx = Math.min(i - 1, nodes.length - 1);
      const dot = document.getElementById(`node-dot-${dotIdx}`);
      const nodeEl = document.getElementById(`dag-node-${dotIdx}`);
      if (dot) {
        dot.className = "node-status-dot done";
      }
      if (nodeEl) {
        nodeEl.classList.remove("active");
        nodeEl.classList.add("completed");
      }
      // Mark next as active
      if (dotIdx + 1 < nodes.length) {
        const nextNode = document.getElementById(`dag-node-${dotIdx + 1}`);
        const nextDot = document.getElementById(`node-dot-${dotIdx + 1}`);
        if (nextNode) nextNode.classList.add("active");
        if (nextDot) nextDot.className = "node-status-dot running";
      }
    }

    // Simulate waiting for approval
    if (isWaiting) {
      await sleep(2000);
    } else {
      await sleep(600 + Math.random() * 600);
    }

    container.scrollTop = container.scrollHeight;
  }

  // Mark all nodes done
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

// ─── Learning / Feedback Rendering ──────────────────────────

function renderLearning(data) {
  const container = document.getElementById("learningContainer");
  const statusEl = document.getElementById("learningStatus");
  container.innerHTML = "";
  statusEl.textContent = "Analysis ready";
  statusEl.className = "panel-status done";

  const content = document.createElement("div");
  content.className = "learning-content";

  // Stats
  const stats = document.createElement("div");
  stats.className = "learning-stats";
  stats.innerHTML = `
    <div class="stat-card" id="stat-0">
      <div class="stat-value success">✓ ${data.status}</div>
      <div class="stat-label">Status</div>
    </div>
    <div class="stat-card" id="stat-1">
      <div class="stat-value time">${data.time}</div>
      <div class="stat-label">Exec Time</div>
    </div>
    <div class="stat-card" id="stat-2">
      <div class="stat-value score">${data.score}</div>
      <div class="stat-label">Confidence</div>
    </div>
  `;
  content.appendChild(stats);

  // Insight
  const insight = document.createElement("div");
  insight.className = "insight-card";
  insight.id = "insight-main";
  insight.innerHTML = `
    <div class="insight-header">
      <span class="insight-icon">💡</span>
      <span class="insight-title">Optimization Suggestion</span>
    </div>
    <div class="insight-body">${data.suggestion}</div>
    <div class="insight-bar-container">
      <div class="insight-bar-label">
        <span>${data.barLabel}</span>
        <span>${data.barValue}%</span>
      </div>
      <div class="insight-bar">
        <div class="insight-bar-fill" id="insightBarFill"></div>
      </div>
    </div>
    <div class="feedback-actions">
      <button class="feedback-btn primary" onclick="handleFeedback('apply')">✓ Apply Suggestion</button>
      <button class="feedback-btn" onclick="handleFeedback('dismiss')">Dismiss</button>
      <button class="feedback-btn" onclick="handleFeedback('details')">More Details</button>
    </div>
  `;
  content.appendChild(insight);

  container.appendChild(content);

  // Animate stats
  setTimeout(() => document.getElementById("stat-0")?.classList.add("visible"), 200);
  setTimeout(() => document.getElementById("stat-1")?.classList.add("visible"), 350);
  setTimeout(() => document.getElementById("stat-2")?.classList.add("visible"), 500);
  setTimeout(() => {
    document.getElementById("insight-main")?.classList.add("visible");
    setTimeout(() => {
      const barFill = document.getElementById("insightBarFill");
      if (barFill) barFill.style.width = data.barValue + "%";
    }, 300);
  }, 650);
}

// ─── Feedback Handler ────────────────────────────────────────

function handleFeedback(action) {
  const container = document.getElementById("learningContainer");
  const existing = container.querySelector(".feedback-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "insight-card feedback-toast";
  toast.style.borderColor = "rgba(52, 211, 153, 0.3)";
  toast.style.marginTop = "12px";

  if (action === "apply") {
    toast.innerHTML = `
      <div class="insight-header">
        <span class="insight-icon">✅</span>
        <span class="insight-title">Suggestion Applied</span>
      </div>
      <div class="insight-body">Future workflows will use the optimized configuration. The learning model has been updated.</div>
    `;
  } else if (action === "dismiss") {
    toast.innerHTML = `
      <div class="insight-header">
        <span class="insight-icon">📝</span>
        <span class="insight-title">Feedback Recorded</span>
      </div>
      <div class="insight-body">This suggestion has been dismissed. It won't appear for similar workflows.</div>
    `;
  } else {
    toast.innerHTML = `
      <div class="insight-header">
        <span class="insight-icon">🔍</span>
        <span class="insight-title">Detailed Analysis</span>
      </div>
      <div class="insight-body">Based on 47 historical workflow executions, the average delay from manual approval is 4.2 minutes. Auto-approval for high-confidence classifications (>0.95) would eliminate this bottleneck in ~68% of cases while maintaining safety controls.</div>
    `;
  }

  container.querySelector(".learning-content").appendChild(toast);
  setTimeout(() => toast.classList.add("visible"), 50);
}

// ─── Main Generation Pipeline ────────────────────────────────

let isGenerating = false;

async function generateWorkflow() {
  const input = document.getElementById("promptInput");
  const btn = document.getElementById("generateBtn");
  const prompt = input.value.trim();

  if (!prompt || isGenerating) return;
  isGenerating = true;

  // Button loading state
  btn.classList.add("loading");

  // Detect template
  const templateKey = detectTemplate(prompt);
  const template = WORKFLOW_TEMPLATES[templateKey];

  // Update statuses
  document.getElementById("dagStatus").textContent = "Generating...";
  document.getElementById("dagStatus").className = "panel-status active";
  document.getElementById("toolsStatus").textContent = "Mapping...";
  document.getElementById("toolsStatus").className = "panel-status active";

  // Simulate LLM latency
  await sleep(1200);

  // Render DAG
  document.getElementById("dagStatus").textContent = `${template.nodes.length} steps`;
  document.getElementById("dagStatus").className = "panel-status done";
  renderDAG(template.nodes);

  // Render Tools
  await sleep(400);
  document.getElementById("toolsStatus").textContent = `${template.tools.length} tools`;
  document.getElementById("toolsStatus").className = "panel-status done";
  renderTools(template.tools);

  // Scroll to workflow section
  await sleep(600);
  document.getElementById("workflow-section").scrollIntoView({ behavior: "smooth", block: "start" });

  // Button done
  btn.classList.remove("loading");

  // Start execution after a brief pause
  await sleep(1500);
  document.getElementById("learningStatus").textContent = "Analyzing...";
  document.getElementById("learningStatus").className = "panel-status active";
  await runExecution(template.logs, template.nodes);

  // Show learning insights
  await sleep(500);
  renderLearning(template.learning);

  isGenerating = false;
}

// ─── Event Listeners ─────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initGrid();
  initNavbar();

  // Generate button
  document.getElementById("generateBtn").addEventListener("click", generateWorkflow);

  // Enter key in prompt
  document.getElementById("promptInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      generateWorkflow();
    }
  });

  // Example chips
  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      const input = document.getElementById("promptInput");
      input.value = prompt;
      input.focus();

      // Visual feedback
      chip.style.background = "rgba(139, 92, 246, 0.2)";
      chip.style.borderColor = "rgba(139, 92, 246, 0.4)";
      chip.style.color = "#a78bfa";
    });
  });

  // Smooth scroll for nav links
  document.querySelectorAll('.nav-link[href^="#"]').forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector(link.getAttribute("href"));
      if (target) target.scrollIntoView({ behavior: "smooth" });
    });
  });
});
