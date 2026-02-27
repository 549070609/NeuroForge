import { useState } from "react";
import { Wrench, ChevronDown, ChevronUp, CheckCircle, Loader } from "lucide-react";
import type { ToolCall } from "../types";

interface Props {
  toolCall: ToolCall;
}

export default function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false);
  const isExecuting = toolCall.status === "executing";

  return (
    <div className="border border-emerald-900/40 rounded-lg mb-2 overflow-hidden bg-[#0e0e16]">
      <button
        className="w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-emerald-900/10 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {isExecuting ? (
          <Loader size={14} className="text-amber-400 animate-spin" />
        ) : (
          <CheckCircle size={14} className="text-emerald-400" />
        )}
        <Wrench size={14} className="text-gray-400" />
        <span className="font-mono text-emerald-300">{toolCall.tool}</span>
        <span className="text-gray-500 text-xs ml-1">
          {isExecuting ? "执行中..." : "已完成"}
        </span>
        <span className="ml-auto">
          {expanded ? (
            <ChevronUp size={14} className="text-gray-500" />
          ) : (
            <ChevronDown size={14} className="text-gray-500" />
          )}
        </span>
      </button>
      {expanded && toolCall.result && (
        <div className="px-3 pb-3 border-t border-gray-800/50">
          <pre className="text-xs text-gray-400 mt-2 bg-[#080810] p-3 rounded overflow-auto max-h-60 font-mono">
            {JSON.stringify(toolCall.result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
