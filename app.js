// SPA state variables
let state = {
  goal: "",
  duration_days: 0,
  tasks: [],
  chat_history: []
};

let hasApiKey = false;

// DOM Elements
const settingsPanel = document.getElementById("settings-panel");
const apiKeyInput = document.getElementById("api-key-input");
const btnSaveKey = document.getElementById("btn-save-key");
const keyStatusText = document.getElementById("key-status-text");
const btnSettingsToggle = document.getElementById("btn-settings-toggle");

const goalWizardCard = document.getElementById("goal-wizard-card");
const goalInput = document.getElementById("goal-input");
const durationInput = document.getElementById("duration-input");
const btnGeneratePlan = document.getElementById("btn-generate-plan");
const wizardError = document.getElementById("wizard-error");

const chatMessagesBox = document.getElementById("chat-messages-box");
const chatUserInput = document.getElementById("chat-user-input");
const btnSendMessage = document.getElementById("btn-send-message");

const metricsCard = document.getElementById("metrics-card");
const activeGoalTitle = document.getElementById("active-goal-title");
const activeGoalDuration = document.getElementById("active-goal-duration");
const progressPercentageText = document.getElementById("progress-percentage-text");
const progressRatio = document.getElementById("progress-ratio");
const progressCircle = document.querySelector(".progress-ring__circle");
const btnExport = document.getElementById("btn-export");
const btnExportPdf = document.getElementById("btn-export-pdf");
const btnReset = document.getElementById("btn-reset");

const listTodo = document.getElementById("list-todo");
const listInProgress = document.getElementById("list-inprogress");
const listCompleted = document.getElementById("list-completed");

const countTodo = document.getElementById("count-todo");
const countInProgress = document.getElementById("count-inprogress");
const countCompleted = document.getElementById("count-completed");

const loadingOverlay = document.getElementById("loading-overlay");
const loadingTitle = document.getElementById("loading-title");

// SVG Circle circumference config (r=32 => 2 * pi * 32 = 201.06)
const CIRCUMFERENCE = 201.06;

// LocalStorage Sync Helpers
function saveLocalState() {
  localStorage.setItem("workspace_state", JSON.stringify(state));
  syncWithServer();
}

async function syncWithServer() {
  try {
    await fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state)
    });
  } catch (e) {
    console.error("State sync failed:", e);
  }
}

// Initial Load & Server Status Check
async function init() {
  try {
    const res = await fetch("/api/status");
    const statusData = await res.json();
    
    hasApiKey = statusData.has_api_key;
    
    if (!hasApiKey) {
      settingsPanel.style.display = "block";
      keyStatusText.textContent = "⚠️ Gemini API Key required to run the AI Planner Agent.";
      keyStatusText.className = "status-msg error";
    } else {
      settingsPanel.style.display = "none";
    }
    
    // Load local storage first (for persistence across server resets)
    const savedLocal = localStorage.getItem("workspace_state");
    if (savedLocal) {
      state = JSON.parse(savedLocal);
      renderWorkspace();
      syncWithServer(); // Backup to server session cache
    } else {
      await fetchWorkspace();
    }
  } catch (err) {
    console.error("Initialization failed:", err);
  }
}

// Fetch Workspace State from Server
async function fetchWorkspace() {
  try {
    const res = await fetch("/api/workspace");
    state = await res.json();
    renderWorkspace();
  } catch (err) {
    console.error("Failed to load workspace:", err);
  }
}

// Save Gemini API Key
btnSaveKey.addEventListener("click", async () => {
  const key = apiKeyInput.value.trim();
  if (!key) {
    keyStatusText.textContent = "Key cannot be empty.";
    keyStatusText.className = "status-msg error";
    return;
  }
  
  showLoading("Configuring API Key...", "Saving environment config.");
  try {
    const res = await fetch("/api/set_key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key })
    });
    
    const data = await res.json();
    if (res.ok) {
      hasApiKey = true;
      keyStatusText.textContent = "✅ Key saved successfully!";
      keyStatusText.className = "status-msg success";
      setTimeout(() => {
        settingsPanel.style.display = "none";
      }, 1500);
    } else {
      keyStatusText.textContent = `Error: ${data.detail}`;
      keyStatusText.className = "status-msg error";
    }
  } catch (err) {
    keyStatusText.textContent = "Connection failed.";
    keyStatusText.className = "status-msg error";
  } finally {
    hideLoading();
  }
});

// Toggle Settings Card
btnSettingsToggle.addEventListener("click", () => {
  if (settingsPanel.style.display === "none") {
    settingsPanel.style.display = "block";
  } else {
    settingsPanel.style.display = "none";
  }
});

// Generate Planner Roadmap
btnGeneratePlan.addEventListener("click", async () => {
  const goal = goalInput.value.trim();
  const duration = parseInt(durationInput.value);
  
  if (!hasApiKey) {
    wizardError.textContent = "Please configure your Gemini API Key first (click Key Setup above).";
    settingsPanel.style.display = "block";
    return;
  }
  if (!goal) {
    wizardError.textContent = "Please describe your learning or project goal.";
    return;
  }
  if (isNaN(duration) || duration <= 0 || duration > 30) {
    wizardError.textContent = "Please specify a duration between 1 and 30 days.";
    return;
  }
  
  wizardError.textContent = "";
  showLoading("Planning Agent At Work...", "Architecting curriculum, generating daily sub-tasks, and searching curated resources.");
  
  try {
    const res = await fetch("/api/init_goal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal, duration_days: duration })
    });
    
    const data = await res.json();
    if (res.ok) {
      state = data;
      saveLocalState();
      renderWorkspace();
    } else {
      wizardError.textContent = `Error: ${data.detail}`;
    }
  } catch (err) {
    wizardError.textContent = "Failed to communicate with the planning server.";
  } finally {
    hideLoading();
  }
});

// Update Task Column Status (Move task along Kanban board)
async function updateTask(taskId, newStatus) {
  try {
    const res = await fetch("/api/update_task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, status: newStatus })
    });
    
    if (res.ok) {
      state = await res.json();
      saveLocalState();
      renderWorkspace();
    }
  } catch (err) {
    console.error("Failed to update task:", err);
  }
}

// Send interactive message to Agent
async function sendMessage() {
  const text = chatUserInput.value.trim();
  if (!text) return;
  
  if (!hasApiKey) {
    alert("Please set your API Key first.");
    return;
  }
  
  // Update state locally for instant user message display
  state.chat_history.push({ sender: "user", text: text });
  saveLocalState();
  chatUserInput.value = "";
  renderChat();
  
  // Show Agent typing log placeholder
  const typingBubble = document.createElement("div");
  typingBubble.className = "chat-msg agent typing-log";
  typingBubble.textContent = "Coach Agent is analyzing your board and drafting reply...";
  chatMessagesBox.appendChild(typingBubble);
  chatMessagesBox.scrollTop = chatMessagesBox.scrollHeight;
  
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });
    
    const data = await res.json();
    if (res.ok) {
      state.chat_history = data.chat_history;
      saveLocalState();
      renderChat();
    } else {
      // Remove typing bubble and show error
      typingBubble.remove();
      alert(`Chat Error: ${data.detail}`);
    }
  } catch (err) {
    typingBubble.remove();
    alert("Failed to send message to Agent.");
  }
}

btnSendMessage.addEventListener("click", sendMessage);
chatUserInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

// Export Roadmap Download
btnExport.addEventListener("click", () => {
  window.open("/api/export", "_blank");
});

// Export PDF by opening backend API endpoint (triggers direct download)
btnExportPdf.addEventListener("click", () => {
  window.open("/api/export_pdf", "_blank");
});

// Reset Workspace / Start New Goal
btnReset.addEventListener("click", async () => {
  if (!confirm("Are you sure you want to reset your workspace and start a new goal?")) return;
  showLoading("Resetting Workspace...", "Clearing active goals and roadmaps.");
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    if (res.ok) {
      state = await res.json();
      localStorage.removeItem("workspace_state");
      renderWorkspace();
    }
  } catch (err) {
    console.error("Failed to reset workspace:", err);
  } finally {
    hideLoading();
  }
});

// Loading helper functions
function showLoading(title, desc) {
  loadingTitle.textContent = title;
  document.getElementById("loading-desc").textContent = desc;
  loadingOverlay.style.display = "flex";
}

function hideLoading() {
  loadingOverlay.style.display = "none";
}

// Render entire dashboard workspace
function renderWorkspace() {
  if (!state.goal) {
    // Show setup UI, hide metrics & board
    goalWizardCard.style.display = "block";
    metricsCard.style.display = "none";
    btnExport.style.display = "none";
    btnExportPdf.style.display = "none";
    btnReset.style.display = "none";
    
    listTodo.innerHTML = "";
    listInProgress.innerHTML = "";
    listCompleted.innerHTML = "";
    
    countTodo.textContent = "0";
    countInProgress.textContent = "0";
    countCompleted.textContent = "0";
    
    renderChat();
    return;
  }
  
  // Hide setup UI, show board metrics
  goalWizardCard.style.display = "none";
  metricsCard.style.display = "flex";
  btnExport.style.display = "inline-flex";
  btnExportPdf.style.display = "inline-flex";
  btnReset.style.display = "inline-flex";
  
  activeGoalTitle.textContent = state.goal;
  activeGoalDuration.textContent = `${state.duration_days}-Day Plan`;
  
  // Calculate Task stats & percentages
  const tasks = state.tasks || [];
  const todo = tasks.filter(t => t.status === "todo");
  const inProgress = tasks.filter(t => t.status === "in_progress");
  const completed = tasks.filter(t => t.status === "completed");
  
  countTodo.textContent = todo.length;
  countInProgress.textContent = inProgress.length;
  countCompleted.textContent = completed.length;
  
  const total = tasks.length;
  const doneCount = completed.length;
  const percent = total > 0 ? Math.round((doneCount / total) * 100) : 0;
  
  progressPercentageText.textContent = `${percent}%`;
  progressRatio.textContent = `${doneCount} of ${total} tasks completed`;
  
  // Update progress ring offset
  const offset = CIRCUMFERENCE - (percent / 100) * CIRCUMFERENCE;
  progressCircle.style.strokeDashoffset = offset;
  
  // Render Kanban Lists
  renderTasksList(listTodo, todo, "todo");
  renderTasksList(listInProgress, inProgress, "in_progress");
  renderTasksList(listCompleted, completed, "completed");
  
  // Render Chat history
  renderChat();
}

// Render dynamic task cards in Kanban columns
function renderTasksList(element, tasks, columnStatus) {
  element.innerHTML = "";
  
  if (tasks.length === 0) {
    element.innerHTML = `<div class="status-msg" style="color: var(--text-muted); text-align: center; margin: 20px 0;">No tasks</div>`;
    return;
  }
  
  tasks.forEach(task => {
    const card = document.createElement("div");
    card.className = "task-card";
    
    // Day indicator tag
    const dayTag = `<span class="day-tag">Day ${task.day}</span>`;
    
    // Curated Resources List
    let resourcesHtml = "";
    if (task.resources && task.resources.length > 0) {
      resourcesHtml = `
        <div class="task-resources">
          <span class="resource-label">Agentic Resources:</span>
          ${task.resources.map(res => `
            <a href="${res.url}" target="_blank" class="resource-link">
              ${res.type === "video" ? "🎥" : "📖"} ${res.title}
            </a>
          `).join("")}
        </div>
      `;
    }
    
    // Status movement buttons
    let actionBtn = "";
    if (columnStatus === "todo") {
      actionBtn = `<button class="btn-card-action btn-next" onclick="updateTask('${task.id}', 'in_progress')">Start Work 🔄</button>`;
    } else if (columnStatus === "in_progress") {
      actionBtn = `<button class="btn-card-action btn-next" style="background: rgba(16, 185, 129, 0.15); color: #6ee7b7;" onclick="updateTask('${task.id}', 'completed')">Complete ✅</button>`;
    } else if (columnStatus === "completed") {
      actionBtn = `<button class="btn-card-action" onclick="updateTask('${task.id}', 'in_progress')">Re-open 🔄</button>`;
    }
    
    card.innerHTML = `
      <div class="task-card-header">
        <h4 class="task-title">${task.title}</h4>
        ${dayTag}
      </div>
      <p class="task-desc">${task.description}</p>
      ${resourcesHtml}
      <div class="task-actions">
        ${actionBtn}
        <button class="btn-help-ai" title="Ask AI for task help" onclick="askAiHelp('${task.title}')">
          🤖 Guide Me
        </button>
      </div>
    `;
    
    element.appendChild(card);
  });
}

// Help task function (fills input with direct question)
function askAiHelp(taskTitle) {
  chatUserInput.value = `Explain and help me with the task: "${taskTitle}". Provide quick steps and code examples if applicable.`;
  chatUserInput.focus();
}

// Render chat messages
function renderChat() {
  chatMessagesBox.innerHTML = "";
  const history = state.chat_history || [];
  
  history.forEach(msg => {
    const bubble = document.createElement("div");
    
    if (msg.text.startsWith("[System Alert]")) {
      bubble.className = "chat-msg system";
      bubble.textContent = msg.text;
    } else {
      bubble.className = `chat-msg ${msg.sender === "user" ? "user" : "agent"}`;
      // Basic markdown parsing for bold text and formatting
      bubble.innerHTML = formatMessageText(msg.text);
    }
    
    chatMessagesBox.appendChild(bubble);
  });
  
  chatMessagesBox.scrollTop = chatMessagesBox.scrollHeight;
}

// Simple Helper to format bold **text** and linebreaks in chat UI
function formatMessageText(text) {
  let escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  
  // Format code blocks
  escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // Format inline code
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Format bold text
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Format linebreaks
  escaped = escaped.replace(/\n/g, '<br>');
  
  return escaped;
}

// Run app init
init();
