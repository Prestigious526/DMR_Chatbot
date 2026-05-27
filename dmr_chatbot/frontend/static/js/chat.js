/**
 * chat.js — App controller
 * Wires Api.js + UI.js together. Manages session state and input.
 */
import Api from "./api.js";
import UI  from "./ui.js";

let chatEl, inputEl, sendBtn, resetBtn, askAiBtn, llmDot;
let sessionId = null;
let isWaiting  = false;
let lastTier   = 1;   // track current tier for typing indicator

document.addEventListener("DOMContentLoaded", async () => {
  chatEl   = document.getElementById("chat");
  inputEl  = document.getElementById("user-input");
  sendBtn  = document.getElementById("send-btn");
  resetBtn = document.getElementById("reset-btn");
  askAiBtn = document.getElementById("ask-ai-btn");
  llmDot   = document.getElementById("llm-status-dot");

  sendBtn.addEventListener("click",  handleSend);
  resetBtn.addEventListener("click", handleReset);
  askAiBtn.addEventListener("click", handleAskAi);
  inputEl.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });
  inputEl.addEventListener("input", autoResize);
  chatEl.addEventListener("click", handleChatClick);

  await initSession();
  checkLlmStatus();
});

async function initSession() {
  try {
    const resp = await Api.createSession();
    sessionId = resp.session_id;
    renderBot(resp);
  } catch (err) {
    renderError(`Cannot connect to server. Make sure server.py is running.\n${err.message}`);
  }
}

async function checkLlmStatus() {
  try {
    const status = await Api.getStatus();
    if (status?.tier2_llm?.available) {
      llmDot.className = "available";
      llmDot.title = `AI: ${status.tier2_llm.model || status.tier2_llm.backend} — ready`;
    } else {
      llmDot.className = "unavailable";
      llmDot.title = "AI Knowledge Base offline (Ollama not running)";
    }
  } catch { /* server not ready */ }
}

async function handleSend() {
  const text = inputEl.value.trim();
  if (!text || isWaiting) return;
  inputEl.value = "";
  autoResize();
  renderUser(text);
  await send(text, null);
}

async function handleReset() {
  if (!sessionId || isWaiting) return;
  UI.disableAllButtons(chatEl);
  renderUser("Reset session");
  try {
    const resp = await Api.resetSession(sessionId);
    renderBot(resp);
    lastTier = 1;
  } catch(err) { renderError(err.message); }
}

async function handleAskAi() {
  if (!sessionId || isWaiting) return;
  renderUser("Ask AI");
  await send("CMD:ASK_AI", null);   // null = already shown above
}

async function handleChatClick(e) {
  const btn = e.target.closest("button[data-action]");
  if (!btn || isWaiting) return;
  UI.disableAllButtons(chatEl);
  const action = btn.getAttribute("data-action");

  const labels = {
    "yes":"✓ Yes", "no":"✗ No",
    "CMD:NEW":"Diagnose another fault",
    "CMD:RESTART":"Restart procedure",
    "CMD:ALL_PROCS":"Show all procedures",
    "CMD:ASK_AI":"Ask AI",
  };
  let display = labels[action] ?? btn.textContent.trim();
  if (action.startsWith("CMD:SELECT:")) display = `Start ${action.split(":")[2]}`;

  renderUser(display);
  await send(action, null);
}

async function send(apiText, displayText) {
  if (!sessionId) return;
  isWaiting = true;
  setDisabled(true);

  // Show typing indicator with correct tier
  const isTier2 = apiText.startsWith("CMD:ASK_AI") || apiText.startsWith("CMD:RAG:") || lastTier === 2;
  const indicator = UI.createTypingIndicator(isTier2 ? 2 : 1);
  chatEl.appendChild(indicator);
  UI.scrollToBottom(chatEl);

  try {
    const resp = await Api.sendMessage(sessionId, apiText);
    chatEl.removeChild(indicator);
    lastTier = resp.tier || 1;
    renderBot(resp);
  } catch(err) {
    chatEl.removeChild(indicator);
    renderError(err.message);
  } finally {
    isWaiting = false;
    setDisabled(false);
    inputEl.focus();
  }
}

function renderUser(text) {
  if (!text) return;
  chatEl.appendChild(UI.createUserMessage(text));
  UI.scrollToBottom(chatEl);
}
function renderBot(resp) {
  chatEl.appendChild(UI.createBotMessage(resp));
  UI.scrollToBottom(chatEl);
}
function renderError(msg) {
  chatEl.appendChild(UI.createBotMessage({ message_type:"error", text:msg }));
  UI.scrollToBottom(chatEl);
}
function setDisabled(d) {
  inputEl.disabled = d;
  sendBtn.disabled = d;
  sendBtn.style.opacity = d ? "0.5" : "1";
}
function autoResize() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + "px";
}
