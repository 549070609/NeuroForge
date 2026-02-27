import { useEffect, useRef, useState } from "react";
import { Send, X, FileText, Loader2, Brain, Wrench, AlertTriangle, Shield, Bell } from "lucide-react";
import type { AlertMessage, ChatMessage, ToolCall } from "../types";
import MessageBubble from "./MessageBubble";
import ToolCallCard from "./ToolCallCard";

export interface ProcessingStep {
  id: string;
  content: string;
  timestamp: number;
}

interface Props {
  messages: ChatMessage[];
  pendingTools: ToolCall[];
  onSend: (message: string, contextAlerts?: AlertMessage[]) => void;
  onFetchSituation?: () => void;
  placeholder?: string;
  disabled?: boolean;
  agentWorking?: boolean;
  workingHint?: string;
  processingSteps?: ProcessingStep[];
  contextAlerts?: AlertMessage[];
  onClearContext?: () => void;
  onRemoveContextAlert?: (id: string) => void;
  hasSituationData?: boolean;
}

const priorityIcon: Record<string, React.ReactNode> = {
  CRITICAL: <AlertTriangle size={10} className="text-red-400 shrink-0" />,
  WARNING: <Shield size={10} className="text-amber-400 shrink-0" />,
  INFO: <Bell size={10} className="text-emerald-400 shrink-0" />,
};

const priorityChipStyle: Record<string, string> = {
  CRITICAL: "bg-red-950/40 border-red-500/30 text-red-300",
  WARNING: "bg-amber-950/30 border-amber-500/30 text-amber-300",
  INFO: "bg-emerald-950/30 border-emerald-500/30 text-emerald-300",
};

export default function ChatPanel({
  messages,
  pendingTools,
  onSend,
  onFetchSituation,
  placeholder = "输入消息...",
  disabled = false,
  agentWorking = false,
  workingHint = "",
  processingSteps = [],
  contextAlerts = [],
  onClearContext,
  onRemoveContextAlert,
  hasSituationData = false,
}: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const hasContext = contextAlerts.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingTools, agentWorking, workingHint, processingSteps]);

  useEffect(() => {
    if (hasContext) inputRef.current?.focus();
  }, [hasContext]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, hasContext ? contextAlerts : undefined);
    setInput("");
    onClearContext?.();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* 对话模式下的工作态展示：加载中、工具调用流程、处理步骤 */}
        {(agentWorking || pendingTools.length > 0 || processingSteps.length > 0) && (
          <div className="mb-4 space-y-2 animate-fade-in">
            {/* 当前工作状态与加载提示 */}
            {agentWorking && (
              <div className="flex gap-3 mr-auto max-w-[75%]">
                <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/20">
                  <Loader2 size={16} className="text-emerald-400 animate-spin" />
                </div>
                <div className="border border-emerald-800/40 bg-emerald-950/15 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 text-emerald-300 text-xs font-medium mb-1">
                    <Brain size={12} />
                    Agent 处理中
                  </div>
                  <p className="text-[12px] text-gray-400">
                    {workingHint || "思考中..."}
                  </p>
                </div>
              </div>
            )}

            {/* 处理步骤时间线：思考 → 工具调用 → ... */}
            {processingSteps.length > 0 && (
              <div className="flex gap-3 mr-auto max-w-[75%]">
                <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-gray-700/30" />
                <div className="flex-1 border border-gray-800/60 bg-[#0e0e16] rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 text-gray-400 text-[10px] font-medium uppercase tracking-wider mb-2">
                    <Wrench size={10} />
                    执行流程
                  </div>
                  <ul className="space-y-1">
                    {processingSteps.map((step, i) => (
                      <li
                        key={step.id}
                        className="flex items-center gap-2 text-[11px] text-gray-500"
                      >
                        <span className="shrink-0 w-4 h-4 rounded-full bg-emerald-900/50 flex items-center justify-center text-[9px] text-emerald-400 font-mono">
                          {i + 1}
                        </span>
                        <span className={i === processingSteps.length - 1 ? "text-emerald-300/90" : ""}>
                          {step.content}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* 工具调用卡片列表 */}
            {pendingTools.length > 0 && (
              <div className="flex gap-3 mr-auto max-w-[75%]">
                <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-gray-700/30" />
                <div className="flex-1 space-y-2">
                  {pendingTools.map((tc) => (
                    <ToolCallCard key={tc.id} toolCall={tc} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-gray-800/60 p-3 bg-[#0d0d14]/80">
        {hasContext && (
          <div className="mb-2 animate-fade-in">
            {/* Header row */}
            <div className="flex items-center gap-1.5 mb-1.5">
              <FileText size={11} className="text-cyan-400 shrink-0" />
              <span className="text-[10px] text-cyan-400/80 font-medium">
                已附加 {contextAlerts.length} 条警报上下文
              </span>
              <button
                onClick={onClearContext}
                className="ml-auto text-[9px] text-gray-500 hover:text-gray-300 transition-colors px-1.5 py-0.5 rounded hover:bg-gray-800/60"
              >
                全部清除
              </button>
            </div>
            {/* Alert chips */}
            <div className="flex flex-wrap gap-1.5 max-h-[68px] overflow-y-auto">
              {contextAlerts.map((alert) => {
                const chipStyle = priorityChipStyle[alert.priority] || priorityChipStyle.INFO;
                const icon = priorityIcon[alert.priority] || priorityIcon.INFO;
                const preview = alert.content
                  .replace(/[*#\n|]/g, " ")
                  .replace(/\s+/g, " ")
                  .trim()
                  .slice(0, 35);
                return (
                  <div
                    key={alert.id}
                    className={`flex items-center gap-1 pl-1.5 pr-1 py-0.5 rounded border text-[10px] max-w-[180px] ${chipStyle}`}
                  >
                    {icon}
                    <span className="truncate flex-1 min-w-0">{preview}…</span>
                    <button
                      onClick={() => onRemoveContextAlert?.(alert.id)}
                      className="shrink-0 p-0.5 rounded hover:bg-black/30 transition-colors ml-0.5"
                    >
                      <X size={9} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            className={`flex-1 bg-[#111118] border rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none transition-colors ${
              hasContext
                ? "border-cyan-700/50 focus:border-cyan-600/60"
                : "border-gray-800 focus:border-emerald-700/60"
            }`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder={hasContext ? "输入分析指令，按回车发送..." : placeholder}
            disabled={disabled}
          />
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className={`text-white rounded-lg p-2.5 transition-colors ${
              hasContext
                ? "bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:text-gray-500"
                : "bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
            }`}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
