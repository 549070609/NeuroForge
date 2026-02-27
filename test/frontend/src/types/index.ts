export interface SituationSnapshot {
  capturedAt: number;
  stats: { critical: number; warning: number; info: number; total: number };
  recentEvents: LogEvent[];
  timeRange?: { from: string; to: string };
}

export interface ChatMessage {
  id: string;
  type: "user" | "agent" | "agent_proactive" | "system";
  content: string;
  timestamp: number;
  priority?: "CRITICAL" | "WARNING" | "INFO";
  toolCalls?: ToolCall[];
  attachedAlerts?: AlertMessage[];
  situationSnapshot?: SituationSnapshot;
}

export interface AlertMessage {
  id: string;
  content: string;
  timestamp: number;
  priority: "CRITICAL" | "WARNING" | "INFO";
  streaming?: boolean;
}

export interface ProactiveSummary {
  id: string;
  summary: string;
  originalContent: string;
  priority: "CRITICAL" | "WARNING" | "INFO";
  timestamp: number;
  checked: boolean;
}

export interface ToolCall {
  id: string;
  tool: string;
  description: string;
  status: "executing" | "completed" | "error";
  result?: Record<string, unknown>;
}

export interface LogEvent {
  timestamp: string;
  level: "CRITICAL" | "WARNING" | "INFO";
  source: string;
  callsign: string;
  location: string;
  event_type: string;
  message: string;
  seq?: number;
  metadata?: Record<string, unknown>;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, string>;
}

export interface WSEvent {
  type: string;
  content?: string;
  tool?: string;
  description?: string;
  status?: string;
  result?: Record<string, unknown>;
  data?: LogEvent;
  priority?: string;
  summary?: string;
  situationSnapshot?: SituationSnapshot;
}
