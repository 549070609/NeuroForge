import { useCallback, useRef, useState } from "react";
import type {
  ChatMessage,
  AlertMessage,
  ProactiveSummary,
  SituationSnapshot,
  ToolCall,
  WSEvent,
  LogEvent,
} from "../types";

let msgCounter = 0;
const nextId = () => `msg-${++msgCounter}-${Date.now()}`;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [summaries, setSummaries] = useState<ProactiveSummary[]>([]);
  const [pendingTools, setPendingTools] = useState<ToolCall[]>([]);
  const [logEvents, setLogEvents] = useState<LogEvent[]>([]);
  const [lastToolResult, setLastToolResult] = useState<ToolCall | null>(null);
  const [agentWorking, setAgentWorking] = useState(false);
  const [workingHint, setWorkingHint] = useState("");
  const [processingSteps, setProcessingSteps] = useState<
    Array<{ id: string; content: string; timestamp: number }>
  >([]);

  // True only while the agent is processing a user-initiated request (vs background proactive monitoring)
  const [conversationActive, setConversationActive] = useState(false);
  // Ref mirror so the memoized handleWSEvent callback can read the current value
  const conversationActiveRef = useRef(false);

  const lastSnapshotRef = useRef<SituationSnapshot | null>(null);

  const captureSituationSnapshot = useCallback((): SituationSnapshot => {
    const events = logEvents;
    const critical = events.filter((e) => e.level === "CRITICAL").length;
    const warning = events.filter((e) => e.level === "WARNING").length;
    const info = events.filter((e) => e.level === "INFO").length;

    const recent = events.slice(-10);
    const timeRange =
      events.length > 0
        ? {
            from: events[0]?.timestamp?.split("T")[1]?.slice(0, 8) || "??:??:??",
            to: events[events.length - 1]?.timestamp?.split("T")[1]?.slice(0, 8) || "??:??:??",
          }
        : undefined;

    const snapshot: SituationSnapshot = {
      capturedAt: Date.now(),
      stats: { critical, warning, info, total: events.length },
      recentEvents: recent,
      timeRange,
    };
    lastSnapshotRef.current = snapshot;
    return snapshot;
  }, [logEvents]);

  const addSituationRequest = useCallback(() => {
    const snapshot = captureSituationSnapshot();
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        type: "user",
        content: "请调用当前态势数据进行比对分析",
        timestamp: Date.now(),
        situationSnapshot: snapshot,
      },
    ]);
    setAgentWorking(true);
    setWorkingHint("Agent 正在分析态势数据...");
    conversationActiveRef.current = true;
    setConversationActive(true);
    return snapshot;
  }, [captureSituationSnapshot]);

  const addUserMessage = useCallback((content: string, alerts?: AlertMessage[] | null) => {
    setMessages((prev) => [
      ...prev,
      {
        id: nextId(),
        type: "user",
        content,
        timestamp: Date.now(),
        ...(alerts && alerts.length > 0 ? { attachedAlerts: alerts } : {}),
      },
    ]);
    setAgentWorking(true);
    setWorkingHint("Agent 思考中...");
    conversationActiveRef.current = true;
    setConversationActive(true);
  }, []);

  const handleWSEvent = useCallback((event: WSEvent) => {
    switch (event.type) {
      case "agent_reply":
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            type: "agent",
            content: event.content || "",
            timestamp: Date.now(),
            toolCalls: [...(prev[prev.length - 1]?.toolCalls || [])],
            situationSnapshot: event.situationSnapshot,
          },
        ]);
        setPendingTools([]);
        setAgentWorking(false);
        setWorkingHint("");
        setProcessingSteps([]);
        conversationActiveRef.current = false;
        setConversationActive(false);
        break;

      case "agent_proactive":
        {
          const alertId = nextId();
          const content = event.content || "";
          const priority = (event.priority as AlertMessage["priority"]) || "INFO";
          const ts = Date.now();
          const shouldStream = priority === "CRITICAL" || priority === "WARNING";

          setAlerts((prev) => [
            ...prev,
            { id: alertId, content, timestamp: ts, priority, streaming: shouldStream },
          ]);

          // Only reset conversation/working state if no user-initiated request is in flight.
          // Background proactive events must not stomp on an active user conversation.
          if (!conversationActiveRef.current) {
            setAgentWorking(false);
            setWorkingHint("");
            setProcessingSteps([]);
            setConversationActive(false);
          }

          if (priority === "CRITICAL" || priority === "WARNING") {
            const summaryText =
              event.summary ||
              content.replace(/[*#\n]/g, " ").replace(/\s+/g, " ").trim().slice(0, 60);
            if (summaryText) {
              setSummaries((prev) => [
                ...prev,
                {
                  id: `sum-${alertId}`,
                  summary: summaryText,
                  originalContent: content,
                  priority,
                  timestamp: ts,
                  checked: false,
                },
              ]);
            }
          }
        }
        break;

      case "tool_call":
        {
          const tc: ToolCall = {
            id: `tc-${Date.now()}`,
            tool: event.tool || "",
            description: event.description || "",
            status: "executing",
          };
          setPendingTools((prev) => [...prev, tc]);
          setWorkingHint(`调用工具: ${event.tool || "processing"}...`);
          setProcessingSteps((prev) => [
            ...prev,
            { id: tc.id, content: `调用工具: ${event.tool || "processing"}...`, timestamp: Date.now() },
          ]);
        }
        break;

      case "tool_result":
        {
          const completedTc: ToolCall = {
            id: `tc-${Date.now()}`,
            tool: event.tool || "",
            description: "",
            status: "completed",
            result: event.result,
          };
          setPendingTools((prev) =>
            prev.map((t) =>
              t.tool === event.tool ? { ...t, status: "completed" as const, result: event.result } : t
            )
          );
          setLastToolResult(completedTc);
        }
        break;

      case "thinking":
        setProcessingSteps((prev) => [
          ...prev,
          { id: nextId(), content: event.content || "Agent 处理中...", timestamp: Date.now() },
        ]);
        setAgentWorking(true);
        setWorkingHint(event.content || "Agent 处理中...");
        break;

      case "log_event":
        if (event.data) {
          setLogEvents((prev) => [...prev, event.data as LogEvent]);
        }
        break;

      case "status":
        break;

      default:
        break;
    }
  }, []);

  const toggleSummary = useCallback((id: string) => {
    setSummaries((prev) =>
      prev.map((s) => (s.id === id ? { ...s, checked: !s.checked } : s))
    );
  }, []);

  const getCheckedSummariesContext = useCallback((): string => {
    const checked = summaries.filter((s) => s.checked);
    if (checked.length === 0) return "";

    const parts = checked.map(
      (s, i) =>
        `--- 参考信息 ${i + 1} ---\n摘要: ${s.summary}\n原始内容:\n${s.originalContent}`
    );
    return `**[已选择的态势参考信息]**\n\n${parts.join("\n\n")}`;
  }, [summaries]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setAlerts([]);
    setSummaries([]);
    setPendingTools([]);
    setLogEvents([]);
    setLastToolResult(null);
    setProcessingSteps([]);
  }, []);

  return {
    messages,
    alerts,
    summaries,
    pendingTools,
    logEvents,
    lastToolResult,
    agentWorking,
    workingHint,
    processingSteps,
    conversationActive,
    addUserMessage,
    addSituationRequest,
    captureSituationSnapshot,
    handleWSEvent,
    toggleSummary,
    getCheckedSummariesContext,
    clearMessages,
  };
}
