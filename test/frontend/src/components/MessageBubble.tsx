import { useState } from "react";
import { Bot, User, AlertTriangle, Shield, FileText, ChevronDown, ChevronRight } from "lucide-react";
import type { ChatMessage } from "../types";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SituationCard from "./SituationCard";

const alertStyles: Record<string, { border: string; bg: string; text: string; label: string }> = {
  CRITICAL: { border: "border-red-500/40", bg: "bg-red-950/30", text: "text-red-400", label: "紧急" },
  WARNING: { border: "border-amber-500/30", bg: "bg-amber-950/20", text: "text-amber-400", label: "警告" },
  INFO: { border: "border-emerald-500/30", bg: "bg-emerald-950/20", text: "text-emerald-400", label: "通知" },
};

function AttachedAlertCard({ alert }: { alert: NonNullable<ChatMessage["attachedAlerts"]>[number] }) {
  const [expanded, setExpanded] = useState(false);
  const style = alertStyles[alert.priority] || alertStyles.INFO;

  const plainPreview = alert.content
    .replace(/[#*_~`>\-|]/g, "")
    .replace(/\n+/g, " ")
    .trim();
  const previewText = plainPreview.length > 60 ? plainPreview.slice(0, 60) + "…" : plainPreview;

  return (
    <div
      className={`mt-2 border ${style.border} ${style.bg} rounded-md px-3 py-2 cursor-pointer transition-colors hover:brightness-110`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-center gap-1.5">
        {expanded ? (
          <ChevronDown size={10} className={style.text} />
        ) : (
          <ChevronRight size={10} className={style.text} />
        )}
        <FileText size={10} className={style.text} />
        <span className={`text-[9px] font-semibold uppercase tracking-wider ${style.text}`}>
          {style.label} · 参考上下文
        </span>
        <span className="text-[9px] text-gray-600 ml-auto">
          {new Date(alert.timestamp).toLocaleTimeString()}
        </span>
      </div>
      {expanded ? (
        <div className="prose prose-invert prose-xs max-w-none text-gray-400 text-[11px] leading-relaxed [&_strong]:text-emerald-300 [&_p]:my-0.5 mt-1.5 [&_table]:w-full [&_table]:text-[10px] [&_th]:bg-gray-800/60 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-gray-300 [&_th]:font-semibold [&_td]:px-2 [&_td]:py-1 [&_td]:border-t [&_td]:border-gray-800/40 [&_tr:hover]:bg-gray-800/20">
          <Markdown remarkPlugins={[remarkGfm]}>{alert.content}</Markdown>
        </div>
      ) : (
        <p className="text-[10px] text-gray-500 mt-1 truncate leading-snug">{previewText}</p>
      )}
    </div>
  );
}

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  if (message.type === "system") {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-gray-500 italic bg-gray-800/40 px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  const isUser = message.type === "user";
  const isProactive = message.type === "agent_proactive";

  const priorityStyles: Record<string, string> = {
    CRITICAL: "border-red-500/60 bg-red-950/20",
    WARNING: "border-amber-500/50 bg-amber-950/15",
    INFO: "border-emerald-500/40 bg-emerald-950/10",
  };

  const borderClass = isProactive
    ? priorityStyles[message.priority || "INFO"] || priorityStyles.INFO
    : isUser
    ? "border-gray-700/50 bg-gray-800/40"
    : "border-emerald-800/40 bg-emerald-950/15";

  const iconBg = isProactive
    ? message.priority === "CRITICAL"
      ? "bg-red-500/20"
      : message.priority === "WARNING"
      ? "bg-amber-500/20"
      : "bg-emerald-500/20"
    : isUser
    ? "bg-blue-500/20"
    : "bg-emerald-500/20";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""} mb-4 animate-fade-in`}>
      <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${iconBg}`}>
        {isUser ? (
          <User size={16} className="text-blue-400" />
        ) : isProactive ? (
          message.priority === "CRITICAL" ? (
            <AlertTriangle size={16} className="text-red-400" />
          ) : (
            <Shield size={16} className="text-emerald-400" />
          )
        ) : (
          <Bot size={16} className="text-emerald-400" />
        )}
      </div>
      <div
        className={`border rounded-lg px-3 py-2 max-w-[75%] ${borderClass} ${
          isUser ? "ml-auto" : "mr-auto"
        }`}
      >
        {isProactive && message.priority === "CRITICAL" && (
          <div className="flex items-center gap-2 mb-2 text-red-400 text-xs font-semibold uppercase tracking-wider">
            <AlertTriangle size={12} className="animate-pulse" />
            紧急警报
          </div>
        )}
        <div className="prose prose-invert prose-xs max-w-none text-[13px] leading-relaxed text-gray-200 [&_strong]:text-emerald-300 [&_code]:bg-gray-800 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_pre]:bg-[#111118] [&_pre]:border [&_pre]:border-gray-800 [&_pre]:rounded-lg [&_pre]:text-xs [&_table]:w-full [&_table]:text-xs [&_table]:my-2 [&_table]:border-collapse [&_th]:bg-gray-800/60 [&_th]:px-2.5 [&_th]:py-1.5 [&_th]:text-left [&_th]:text-emerald-300 [&_th]:font-semibold [&_th]:text-[11px] [&_th]:uppercase [&_th]:tracking-wider [&_td]:px-2.5 [&_td]:py-1.5 [&_td]:border-t [&_td]:border-gray-800/40 [&_td]:text-[12px] [&_tr:hover]:bg-gray-800/20">
          <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
        </div>
        {message.attachedAlerts && message.attachedAlerts.length > 0 && (
          <div className="space-y-1">
            {message.attachedAlerts.map((a) => (
              <AttachedAlertCard key={a.id} alert={a} />
            ))}
          </div>
        )}
        {message.situationSnapshot && (
          <SituationCard snapshot={message.situationSnapshot} />
        )}
        <div className="text-[10px] text-gray-600 mt-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
