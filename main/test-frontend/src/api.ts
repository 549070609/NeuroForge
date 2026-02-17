/**
 * PyAgentForge API Client
 *
 * 与 GLM Provider Backend 通信的客户端
 */

const API_BASE = '/api';

// ============ Types ============

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
}

export interface Session {
  session_id: string;
  status: string;
  message_count?: number;
  messages?: Message[];
}

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

export interface CreateSessionRequest {
  agent_id?: string;
  system_prompt?: string;
  model?: string;
}

export interface SendMessageRequest {
  message: string;
  stream?: boolean;
}

// ============ API Client ============

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health(): Promise<{ status: string; provider: string; model: string }> {
    return this.request('/health');
  }

  // List available models
  async listModels(): Promise<ModelInfo[]> {
    return this.request('/models');
  }

  // Create a new session
  async createSession(request: CreateSessionRequest): Promise<Session> {
    return this.request('/sessions', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Get session details
  async getSession(sessionId: string): Promise<Session> {
    return this.request(`/sessions/${sessionId}`);
  }

  // List all sessions
  async listSessions(): Promise<{ sessions: string[] }> {
    return this.request('/sessions');
  }

  // Delete a session
  async deleteSession(sessionId: string): Promise<void> {
    await this.request(`/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  }

  // Send a message (non-streaming)
  async sendMessage(sessionId: string, request: SendMessageRequest): Promise<Message> {
    return this.request(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Create WebSocket connection
  createWebSocket(sessionId: string): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return new WebSocket(`${protocol}//${host}/ws/${sessionId}`);
  }
}

export const api = new APIClient();
