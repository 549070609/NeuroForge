import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Radio, Crosshair, Zap, Bell, Activity, Square, ChevronDown } from "lucide-react";
import ChatPanel from "../components/ChatPanel";
import AlertPanel from "../components/AlertPanel";
import MonitorDashboard from "../components/MonitorDashboard";
import type { FilterLevel } from "../components/MonitorDashboard";
import LogStream from "../components/LogStream";
import { useWebSocket } from "../hooks/useWebSocket";
import { useChat } from "../hooks/useChat";
import { createSession, getWsUrl } from "../utils/api";
import type { AlertMessage, WSEvent } from "../types";

const SCENARIOS = [
  { id: "ambush", label: "伏击战" },
  { id: "air_strike", label: "空袭行动" },
  { id: "recon", label: "侦察任务" },
  { id: "supply_run", label: "补给护送" },
];

export default function ActivePage() {
  const [sessionId, setSessionId] = useState<string>("");
  const {
    messages,
    alerts,
    pendingTools,
    logEvents,
    agentWorking,
    workingHint,
    processingSteps,
    conversationActive,
    addUserMessage,
    addSituationRequest,
    handleWSEvent,
  } = useChat();
  const [selectedScenario, setSelectedScenario] = useState("ambush");
  const [filterLevel, setFilterLevel] = useState<FilterLevel>(null);
  const [contextAlerts, setContextAlerts] = useState<AlertMessage[]>([]);

  type AlertViewMode = "CRITICAL" | "ALL" | "WARNING" | "INFO";
  const [alertViewMode, setAlertViewMode] = useState<AlertViewMode>("CRITICAL");

  const filteredAlerts = useMemo(
    () => filterLevel ? alerts.filter((a) => a.priority === filterLevel) : alerts,
    [alerts, filterLevel],
  );

  const panelAlerts = useMemo(
    () => alertViewMode === "ALL" ? alerts : alerts.filter((a) => a.priority === alertViewMode),
    [alerts, alertViewMode],
  );

  const filteredLogEvents = useMemo(
    () => filterLevel ? logEvents.filter((e) => e.level === filterLevel) : logEvents,
    [logEvents, filterLevel],
  );

  // Whether the continuous monitor loop is active
  const [monitoring, setMonitoring] = useState(false);
  const monitoringRef = useRef(false);
  monitoringRef.current = monitoring;

  // Stable refs to avoid stale closures in effects
  const selectedScenarioRef = useRef(selectedScenario);
  selectedScenarioRef.current = selectedScenario;

  useEffect(() => {
    let cancelled = false;
    createSession().then((id) => {
      if (!cancelled) setSessionId(id);
    });
    return () => { cancelled = true; };
  }, []);

  const wsUrl = useMemo(
    () => (sessionId ? getWsUrl(`/ws/active/${sessionId}`) : ""),
    [sessionId]
  );

  // Wrap the chat handler to intercept monitor status events
  const handleWsEvent = useCallback((event: WSEvent) => {
    if (event.type === "status") {
      if (event.content === "monitor_stopped") setMonitoring(false);
      // monitor_started is purely an ACK, no UI action needed
      return;
    }
    handleWSEvent(event);
  }, [handleWSEvent]);

  const { connected, send } = useWebSocket({
    url: wsUrl,
    onMessage: handleWsEvent,
    autoConnect: !!sessionId,
  });

  // Auto-start monitor when connection is established (first connect or reconnect)
  useEffect(() => {
    if (connected) {
      // Auto-start on first connection; restore loop after reconnect
      send({ type: "start_monitor", scenario: selectedScenarioRef.current });
      setMonitoring(true);
    } else {
      // Connection lost — reflect stopped state in UI
      setMonitoring(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected]);

  // Restart monitor with new scenario when user changes it while monitoring
  useEffect(() => {
    if (connected && monitoringRef.current) {
      send({ type: "start_monitor", scenario: selectedScenario });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedScenario]);

  const handleFetchSituation = useCallback(() => {
    if (!connected || logEvents.length === 0) return;
    const snapshot = addSituationRequest();
    send({ type: "fetch_situation", snapshot });
  }, [connected, logEvents.length, addSituationRequest, send]);

  const handleAlertToggle = useCallback((alert: AlertMessage) => {
    setContextAlerts((prev) => {
      const exists = prev.some((a) => a.id === alert.id);
      if (exists) return prev.filter((a) => a.id !== alert.id);
      return [...prev, alert];
    });
  }, []);

  const handleRemoveContextAlert = useCallback((id: string) => {
    setContextAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const handleSend = (message: string, alertContexts?: AlertMessage[]) => {
    addUserMessage(message, alertContexts);
    if (alertContexts && alertContexts.length > 0) {
      const ctx = alertContexts
        .map(
          (a, i) =>
            `**[参考警报 ${i + 1}]**\n优先级: ${a.priority}\n时间: ${new Date(a.timestamp).toLocaleTimeString()}\n内容:\n${a.content}`
        )
        .join("\n\n");
      send({ type: "message", message, summaryContext: ctx });
    } else {
      send({ type: "message", message });
    }
  };

  const handleToggleMonitor = () => {
    if (!connected) return;
    if (monitoring) {
      send({ type: "stop_monitor" });
      setMonitoring(false);
    } else {
      send({ type: "start_monitor", scenario: selectedScenario });
      setMonitoring(true);
    }
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800/40 bg-[#0d0d14]/50 shrink-0">
        <div className="flex items-center gap-3">
          <Radio size={18} className="text-red-400" />
          <h2 className="text-sm font-semibold text-gray-200">
            Overwatch · 主动 Agent 指挥中心
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            disabled={!connected}
            className="bg-[#111118] border border-gray-800 rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-red-700/60 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>

          {/* Monitor toggle button */}
          <button
            onClick={handleToggleMonitor}
            disabled={!connected}
            className={`flex items-center gap-2 text-white text-xs px-3 py-1.5 rounded-lg transition-colors font-medium disabled:bg-gray-700 disabled:text-gray-500 ${
              monitoring
                ? "bg-gray-700 hover:bg-gray-600"
                : "bg-red-600 hover:bg-red-500"
            }`}
          >
            {monitoring ? (
              <>
                <Square size={12} className="fill-current" />
                停止监控
              </>
            ) : (
              <>
                <Zap size={14} />
                开始监控
              </>
            )}
          </button>

          {/* Connection + monitor status indicator */}
          <div className="flex items-center gap-1.5">
            {monitoring && connected ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
                </span>
                <span className="text-xs text-red-400 font-mono">监控中</span>
              </>
            ) : (
              <>
                <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400" : "bg-gray-600"}`} />
                <span className="text-xs text-gray-500">
                  {connected ? "在线" : "连接中..."}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 3-Column Layout */}
      <div className="flex-1 min-h-0 flex">
        {/* Column 1: Chat */}
        <div className="w-[38%] flex flex-col border-r border-gray-800/40">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800/40 bg-[#0d0d14]/30 shrink-0">
            <Crosshair size={14} className="text-amber-400" />
            <span className="text-xs font-medium text-gray-300">指挥通信频道</span>
          </div>
          <div className="flex-1 min-h-0">
            <ChatPanel
              messages={messages}
              pendingTools={conversationActive ? pendingTools : []}
              onSend={handleSend}
              onFetchSituation={handleFetchSituation}
              placeholder="向 Overwatch 下达指令..."
              disabled={!connected}
              agentWorking={conversationActive && agentWorking}
              workingHint={workingHint}
              processingSteps={conversationActive ? processingSteps : []}
              contextAlerts={contextAlerts}
              onClearContext={() => setContextAlerts([])}
              onRemoveContextAlert={handleRemoveContextAlert}
              hasSituationData={logEvents.length > 0}
            />
          </div>
        </div>

        {/* Column 2: Proactive Alerts */}
        <div className="w-[30%] flex flex-col border-r border-gray-800/40 bg-[#0b0b11]">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800/40 bg-[#0d0d14]/30 shrink-0">
            <Bell size={14} className="text-red-400" />
            <span className="text-xs font-medium text-gray-300">主动消息</span>
            <div className="relative ml-auto flex items-center gap-2">
              <select
                value={alertViewMode}
                onChange={(e) => setAlertViewMode(e.target.value as AlertViewMode)}
                className="appearance-none bg-[#111118] border border-gray-800 rounded pl-2 pr-5 py-0.5 text-[10px] text-gray-400 focus:outline-none focus:border-red-700/60 cursor-pointer"
              >
                <option value="CRITICAL">关键威胁</option>
                <option value="WARNING">警告事件</option>
                <option value="INFO">常规通知</option>
                <option value="ALL">全部消息</option>
              </select>
              <ChevronDown size={10} className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
            </div>
            {panelAlerts.length > 0 && (
              <span className="text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full font-mono">
                {panelAlerts.length}
              </span>
            )}
          </div>
          {/* 常驻状态：持续监控中 */}
          <div className="shrink-0 border-b border-cyan-500/40 bg-gradient-to-r from-cyan-950/50 via-sky-950/40 to-blue-950/50 backdrop-blur-sm ring-1 ring-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.15)] relative overflow-hidden">
            {/* 流光扫过效果 */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-400/10 to-transparent animate-[shimmer_2.5s_ease-in-out_infinite]" />
            <div className="flex items-center gap-2 px-3 py-3 relative">
              <span className="relative flex h-3 w-3 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.6)]" />
              </span>
              <span className="text-[12px] font-semibold truncate bg-gradient-to-r from-cyan-300 via-sky-300 to-blue-300 bg-clip-text text-transparent drop-shadow-[0_0_8px_rgba(34,211,238,0.3)]">
                {agentWorking && processingSteps.length > 0
                  ? processingSteps[processingSteps.length - 1].content
                  : "持续监控中"}
              </span>
              <span className="flex gap-0.5 shrink-0 ml-auto">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse [animation-delay:0ms] shadow-[0_0_4px_rgba(34,211,238,0.8)]" />
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse [animation-delay:150ms] shadow-[0_0_4px_rgba(56,189,248,0.8)]" />
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:300ms] shadow-[0_0_4px_rgba(96,165,250,0.8)]" />
              </span>
            </div>
          </div>
          <div className="flex-1 min-h-0">
            <AlertPanel
              alerts={panelAlerts}
              onAlertClick={handleAlertToggle}
              selectedAlertIds={new Set(contextAlerts.map((a) => a.id))}
            />
          </div>
        </div>

        {/* Column 3: Monitor */}
        <div className="w-[32%] flex flex-col bg-[#090910]">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800/40 bg-[#0d0d14]/30 shrink-0">
            <Activity size={14} className="text-emerald-400" />
            <span className="text-xs font-medium text-gray-300">战场态势监控</span>
            <span className="ml-auto text-[10px] text-gray-600 font-mono">
              {logEvents.length} 事件
            </span>
          </div>
          <div className="shrink-0 px-3 py-2">
            <MonitorDashboard events={logEvents} activeFilter={filterLevel} onFilterChange={setFilterLevel} />
          </div>
          <div className="flex-1 min-h-0 px-3 pb-2">
            <div className="h-full border border-gray-800/40 rounded-lg bg-[#080810] overflow-hidden">
              <LogStream events={filteredLogEvents} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
