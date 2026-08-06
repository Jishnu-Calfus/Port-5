const API_BASE = "http://127.0.0.1:8000/api";

async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export function getKpis() {
  return getJSON("/kpis");
}

export function getPriority() {
  return getJSON("/priority");
}

export function getCategories() {
  return getJSON("/categories");
}

export function getSentiment() {
  return getJSON("/sentiment");
}

export function getSources() {
  return getJSON("/sources");
}

export function getTrend() {
  return getJSON("/trend");
}

export function getCurrentWeek() {
  return getJSON("/current-week");
}

export function getSummary() {
  return getJSON("/summary");
}

export async function askQuestion(question, topK = 3) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  if (!res.ok) throw new Error(`ask failed: ${res.status}`);
  return res.json();
}

export async function askAgent(question) {
  const res = await fetch(`${API_BASE}/agent/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    // Unlike askQuestion, the error body here is meant to be shown to the
    // user (e.g. a 422 "couldn't safely answer that" reason) -- surface it
    // instead of just the status code.
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `agent/ask failed: ${res.status}`);
  }
  return res.json();
}
