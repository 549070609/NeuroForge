const BASE = "";

export async function createSession(): Promise<string> {
  const res = await fetch(`${BASE}/api/session/create`, { method: "POST" });
  const data = await res.json();
  return data.session_id;
}

export async function fetchPassiveTools() {
  const res = await fetch(`${BASE}/api/tools/passive`);
  return res.json();
}

export async function fetchActiveTools() {
  const res = await fetch(`${BASE}/api/tools/active`);
  return res.json();
}

export async function fetchScenarios(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/scenarios`);
  const data = await res.json();
  return data.scenarios;
}

export async function triggerMock(sessionId: string, scenario?: string) {
  const res = await fetch(`${BASE}/api/active/trigger-mock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, scenario }),
  });
  return res.json();
}

export function getWsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // In development, connect directly to the backend to bypass Vite proxy
  // WebSocket data-frame forwarding issues (proxy establishes handshake but
  // drops client→server frames, causing heartbeat timeouts and silent failure).
  if (import.meta.env.DEV) {
    const backendHost = import.meta.env.VITE_BACKEND_HOST ?? "localhost:8080";
    return `${proto}//${backendHost}${path}`;
  }
  return `${proto}//${window.location.host}${path}`;
}

// ==================== Config API ====================

export interface AppConfig {
  mode: string;
  provider: string;
  api_key_set: boolean;
  api_key_preview: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface ModelOption {
  id: string;
  name: string;
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await fetch(`${BASE}/api/config`);
  return res.json();
}

export async function updateConfig(updates: Record<string, unknown>): Promise<AppConfig> {
  const res = await fetch(`${BASE}/api/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  return res.json();
}

export async function testConnection(
  params?: { provider?: string; api_key?: string; base_url?: string; model?: string }
): Promise<{ success: boolean; response?: string; error?: string }> {
  const res = await fetch(`${BASE}/api/config/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params || {}),
  });
  return res.json();
}

export async function fetchModelsForProvider(provider: string): Promise<ModelOption[]> {
  const res = await fetch(`${BASE}/api/config/models?provider=${provider}`);
  const data = await res.json();
  return data.models;
}

export async function fetchHealth(): Promise<{ status: string; mode: string; model: string }> {
  const res = await fetch(`${BASE}/api/health`);
  return res.json();
}
