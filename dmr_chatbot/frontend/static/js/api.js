/**
 * api.js — Backend API client
 * All fetch calls live here. Nothing else imports fetch directly.
 */
const BASE_URL = window.DMR_API_BASE || "";

async function _post(path, body = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}
async function _get(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  const data = await res.json();
  return { ok: res.ok, data };
}

const Api = {
  async createSession() {
    const { ok, data } = await _post("/api/session/new");
    if (!ok) throw new Error(data.error || "Failed to create session");
    return data;
  },
  async sendMessage(sessionId, text) {
    const { ok, data } = await _post(`/api/session/${sessionId}/message`, { text });
    if (!ok) throw new Error(data.error || "Server error");
    return data;
  },
  async resetSession(sessionId) {
    const { ok, data } = await _post(`/api/session/${sessionId}/reset`);
    if (!ok) throw new Error(data.error || "Failed to reset");
    return data;
  },
  async getStatus() {
    const { ok, data } = await _get("/api/status");
    return ok ? data : null;
  },
};

export default Api;
