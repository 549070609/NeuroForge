import { Wrench, X, Code, FileText } from "lucide-react";
import type { ToolCall } from "../types";

interface Props {
  toolResult: ToolCall | null;
  onClose: () => void;
}

export default function ToolOutputPanel({ toolResult, onClose }: Props) {
  if (!toolResult || !toolResult.result) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 p-6">
        <Wrench size={40} className="mb-3 opacity-40" />
        <p className="text-sm">工具输出将在此处显示</p>
        <p className="text-xs mt-1 text-gray-700">发送消息触发工具调用</p>
      </div>
    );
  }

  const result = toolResult.result as Record<string, unknown>;
  const code = (result.code as string) || "";
  const language = (result.language as string) || "";
  const content = (result.content as string) || "";
  const converted = (result.converted as string) || "";

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/60">
        <div className="flex items-center gap-2">
          {code ? (
            <Code size={16} className="text-emerald-400" />
          ) : (
            <FileText size={16} className="text-emerald-400" />
          )}
          <span className="font-mono text-sm text-emerald-300">{toolResult.tool}</span>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {code && (
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">
              {language} 代码
            </div>
            <pre className="bg-[#080810] border border-gray-800 rounded-lg p-4 text-sm font-mono text-green-300 overflow-auto">
              {code}
            </pre>
          </div>
        )}

        {content && (
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">文档内容</div>
            <div className="bg-[#080810] border border-gray-800 rounded-lg p-4 text-sm text-gray-300 whitespace-pre-wrap">
              {content}
            </div>
          </div>
        )}

        {converted && (
          <div className="mb-4">
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">转换结果</div>
            <pre className="bg-[#080810] border border-gray-800 rounded-lg p-4 text-sm font-mono text-amber-300 overflow-auto">
              {converted}
            </pre>
          </div>
        )}

        {!code && !content && !converted && (
          <div>
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider">工具输出</div>
            <pre className="bg-[#080810] border border-gray-800 rounded-lg p-4 text-sm font-mono text-gray-400 overflow-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
