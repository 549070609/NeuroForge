import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ChevronRight,
  AlertTriangle,
  Shield,
  Check,
} from "lucide-react";
import type { ProactiveSummary } from "../types";

interface Props {
  summaries: ProactiveSummary[];
  onToggle: (id: string) => void;
}

const cfg = {
  CRITICAL: {
    Icon: AlertTriangle,
    dot: "bg-red-500",
    tag: "bg-red-500/20 text-red-400",
    border: "border-red-500/30",
    checkedBg: "bg-red-500/8",
    text: "text-red-300",
    label: "紧急",
  },
  WARNING: {
    Icon: Shield,
    dot: "bg-amber-500",
    tag: "bg-amber-500/20 text-amber-400",
    border: "border-amber-500/30",
    checkedBg: "bg-amber-500/8",
    text: "text-amber-300",
    label: "警告",
  },
} as const;

function SummaryItem({
  item,
  onToggle,
}: {
  item: ProactiveSummary;
  onToggle: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const s = cfg[item.priority as keyof typeof cfg];
  if (!s) return null;

  return (
    <div
      className={`rounded border transition-colors ${
        item.checked ? `${s.checkedBg} ${s.border}` : "border-transparent"
      }`}
    >
      {/* Compact row */}
      <div className="flex items-center gap-1.5 px-1.5 py-1 min-h-[28px]">
        {/* Checkbox */}
        <button
          onClick={() => onToggle(item.id)}
          className={`shrink-0 w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${
            item.checked
              ? "bg-cyan-600 border-cyan-600"
              : "border-gray-600 hover:border-gray-400"
          }`}
        >
          {item.checked && <Check size={9} className="text-white" />}
        </button>

        {/* Priority tag */}
        <span
          className={`shrink-0 text-[9px] font-semibold uppercase px-1 py-px rounded ${s.tag}`}
        >
          {s.label}
        </span>

        {/* Summary text (truncated single line) */}
        <span
          className={`flex-1 min-w-0 truncate text-[11px] leading-none ${
            item.checked ? s.text : "text-gray-400"
          }`}
        >
          {item.summary}
        </span>

        {/* Time */}
        <span className="shrink-0 text-[9px] text-gray-600 tabular-nums">
          {new Date(item.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="shrink-0 p-0.5 rounded hover:bg-gray-700/40 transition-colors"
        >
          {expanded ? (
            <ChevronDown size={10} className="text-gray-500" />
          ) : (
            <ChevronRight size={10} className="text-gray-500" />
          )}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-6 pb-1.5 text-[10px] text-gray-500 leading-relaxed whitespace-pre-wrap max-h-[120px] overflow-y-auto">
          {item.originalContent
            .replace(/[*#]/g, "")
            .trim()
            .slice(0, 300)}
          {item.originalContent.length > 300 && "…"}
        </div>
      )}
    </div>
  );
}

export default function SummaryTray({ summaries, onToggle }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const actionable = summaries.filter(
    (s) => s.priority === "CRITICAL" || s.priority === "WARNING"
  );
  const checkedCount = actionable.filter((s) => s.checked).length;
  const criticalCount = actionable.filter((s) => s.priority === "CRITICAL").length;
  const warningCount = actionable.filter((s) => s.priority === "WARNING").length;

  if (actionable.length === 0) return null;

  return (
    <div className="border-b border-gray-800/40 bg-[#0c0c14]/60 shrink-0">
      {/* Header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 w-full px-3 py-1 text-left hover:bg-gray-800/20 transition-colors"
      >
        <AlertTriangle size={11} className="text-red-400 shrink-0" />
        <span className="text-[10px] font-medium text-gray-300">态势摘要</span>

        {criticalCount > 0 && (
          <span className="text-[9px] bg-red-500/20 text-red-400 px-1 py-px rounded font-mono">
            {criticalCount}
          </span>
        )}
        {warningCount > 0 && (
          <span className="text-[9px] bg-amber-500/20 text-amber-400 px-1 py-px rounded font-mono">
            {warningCount}
          </span>
        )}

        {checkedCount > 0 && (
          <span className="text-[9px] bg-cyan-500/15 text-cyan-400 px-1 py-px rounded-full font-mono">
            选{checkedCount}
          </span>
        )}

        <span className="ml-auto">
          {collapsed ? (
            <ChevronDown size={11} className="text-gray-600" />
          ) : (
            <ChevronUp size={11} className="text-gray-600" />
          )}
        </span>
      </button>

      {/* Items */}
      {!collapsed && (
        <div className="px-1.5 pb-1.5 space-y-px max-h-[160px] overflow-y-auto">
          {actionable.map((s) => (
            <SummaryItem key={s.id} item={s} onToggle={onToggle} />
          ))}
        </div>
      )}
    </div>
  );
}
