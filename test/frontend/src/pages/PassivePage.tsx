import { useEffect, useMemo, useState } from "react";
import { Bot, Wrench } from "lucide-react";
import ChatPanel from "../components/ChatPanel";
import ToolOutputPanel from "../components/ToolOutputPanel";
import { useWebSocket } from "../hooks/useWebSocket";
import { useChat } from "../hooks/useChat";
import { createSession, getWsUrl } from "../utils/api";

export default function PassivePage() {
  const [sessionId, setSessionId] = useState<string>("");
  const { messages, pendingTools, lastToolResult, agentWorking, workingHint, processingSteps, addUserMessage, handleWSEvent } = useChat();
  const [showToolPanel, setShowToolPanel] = useState(true);

  useEffect(() => {
    createSession().then(setSessionId);
  }, []);

  const wsUrl = useMemo(
    () => (sessionId ? getWsUrl(`/ws/passive/${sessionId}`) : ""),
    [sessionId]
  );

  const { connected, send } = useWebSocket({
    url: wsUrl,
    onMessage: handleWSEvent,
    autoConnect: !!sessionId,
  });

  const handleSend = (message: string) => {
    addUserMessage(message);
    send({ message });
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex">
      {/* Chat area */}
      <div className={`flex flex-col ${showToolPanel ? "w-3/5" : "w-full"} border-r border-gray-800/40`}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800/40 bg-[#0d0d14]/50">
          <Bot size={20} className="text-blue-400" />
          <div>
            <h2 className="text-sm font-semibold text-gray-200">被动型通用 Agent</h2>
            <p className="text-xs text-gray-500">编程 · 写作 · 文档 · 格式转换</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                connected ? "bg-emerald-400" : "bg-gray-600"
              }`}
            />
            <span className="text-xs text-gray-500">
              {connected ? "已连接" : "连接中..."}
            </span>
            <button
              onClick={() => setShowToolPanel(!showToolPanel)}
              className="ml-2 text-gray-500 hover:text-gray-300 p-1 rounded hover:bg-gray-800/40"
              title="切换工具面板"
            >
              <Wrench size={16} />
            </button>
          </div>
        </div>
        <ChatPanel
          messages={messages}
          pendingTools={pendingTools}
          onSend={handleSend}
          placeholder="试试：写一个 Python 排序函数 / 审查代码 / 写一份 API 文档..."
          disabled={!connected}
          agentWorking={agentWorking}
          workingHint={workingHint}
          processingSteps={processingSteps}
        />
      </div>

      {/* Tool output panel */}
      {showToolPanel && (
        <div className="w-2/5 bg-[#0b0b12]">
          <ToolOutputPanel
            toolResult={lastToolResult}
            onClose={() => setShowToolPanel(false)}
          />
        </div>
      )}
    </div>
  );
}
