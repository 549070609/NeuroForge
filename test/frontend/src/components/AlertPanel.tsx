import { useEffect, useRef, useState, useCallback } from "react";
import { AlertTriangle, Shield, Bell, Loader2, Scan, ChevronDown, ChevronUp, Check } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AlertMessage } from "../types";

interface Props {
  alerts: AlertMessage[];
  onStreamComplete?: (id: string) => void;
  onAlertClick?: (alert: AlertMessage) => void;
  selectedAlertIds?: Set<string>;
}

const priorityConfig = {
  CRITICAL: {
    icon: AlertTriangle,
    border: "border-red-500/50",
    bg: "bg-red-950/20",
    badge: "bg-red-500/20 text-red-400",
    label: "紧急",
  },
  WARNING: {
    icon: Shield,
    border: "border-amber-500/40",
    bg: "bg-amber-950/15",
    badge: "bg-amber-500/20 text-amber-400",
    label: "警告",
  },
  INFO: {
    icon: Bell,
    border: "border-emerald-500/30",
    bg: "bg-emerald-950/10",
    badge: "bg-emerald-500/20 text-emerald-400",
    label: "通知",
  },
};

const CHARS_PER_TICK = 8;
const TICK_INTERVAL_MS = 30;

function StreamingAlertContent({
  content,
  onComplete,
}: {
  content: string;
  onComplete: () => void;
}) {
  const [revealedLen, setRevealedLen] = useState(0);
  const completeRef = useRef(false);

  useEffect(() => {
    if (completeRef.current) return;
    if (revealedLen >= content.length) {
      completeRef.current = true;
      onComplete();
      return;
    }
    const timer = setTimeout(() => {
      setRevealedLen((prev) => Math.min(prev + CHARS_PER_TICK, content.length));
    }, TICK_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [revealedLen, content, onComplete]);

  const visible = content.slice(0, revealedLen);
  const isStreaming = revealedLen < content.length;

  return (
    <>
      {isStreaming && (
        <div className="flex items-center gap-2 mb-2 px-1 py-1 rounded bg-red-500/10 border border-red-500/20">
          <Scan size={12} className="text-red-400 animate-pulse" />
          <span className="text-[10px] font-medium text-red-300">
            发现关键威胁，AI正在评估
          </span>
          <Loader2 size={10} className="text-red-400 animate-spin ml-auto" />
        </div>
      )}
      <div className="prose prose-invert prose-xs max-w-none text-gray-300 text-xs leading-relaxed [&_strong]:text-emerald-300 [&_code]:bg-gray-800 [&_code]:px-1 [&_code]:rounded [&_p]:my-1 [&_table]:w-full [&_table]:text-[10px] [&_table]:my-1.5 [&_table]:border-collapse [&_th]:bg-gray-800/50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-emerald-300/80 [&_th]:font-semibold [&_th]:text-[10px] [&_td]:px-2 [&_td]:py-1 [&_td]:border-t [&_td]:border-gray-800/30 [&_td]:text-[10px] [&_tr:hover]:bg-gray-800/20">
        <Markdown remarkPlugins={[remarkGfm]}>{visible}</Markdown>
        {isStreaming && (
          <span className="inline-block w-1.5 h-3.5 bg-red-400/80 animate-pulse ml-0.5 align-middle rounded-sm" />
        )}
      </div>
    </>
  );
}

const COLLAPSED_MAX_HEIGHT = 60; // ~3 lines at text-xs leading-relaxed

function CollapsibleContent({
  content,
  alertId,
  expandedAlerts,
  onToggle,
}: {
  content: string;
  alertId: string;
  expandedAlerts: Set<string>;
  onToggle: (id: string) => void;
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [overflows, setOverflows] = useState(false);
  const isExpanded = expandedAlerts.has(alertId);

  useEffect(() => {
    const el = contentRef.current;
    if (el) {
      setOverflows(el.scrollHeight > COLLAPSED_MAX_HEIGHT);
    }
  }, [content]);

  return (
    <div className="relative">
      <div
        ref={contentRef}
        className="prose prose-invert prose-xs max-w-none text-gray-300 text-xs leading-relaxed [&_strong]:text-emerald-300 [&_code]:bg-gray-800 [&_code]:px-1 [&_code]:rounded [&_p]:my-1 [&_table]:w-full [&_table]:text-[10px] [&_table]:my-1.5 [&_table]:border-collapse [&_th]:bg-gray-800/50 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:text-emerald-300/80 [&_th]:font-semibold [&_th]:text-[10px] [&_td]:px-2 [&_td]:py-1 [&_td]:border-t [&_td]:border-gray-800/30 [&_td]:text-[10px] [&_tr:hover]:bg-gray-800/20 overflow-hidden transition-[max-height] duration-300 ease-in-out"
        style={{ maxHeight: isExpanded || !overflows ? contentRef.current?.scrollHeight ?? 9999 : COLLAPSED_MAX_HEIGHT }}
      >
        <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
      </div>
      {overflows && !isExpanded && (
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black/60 to-transparent pointer-events-none rounded-b" />
      )}
      {overflows && (
        <button
          onClick={(e) => { e.stopPropagation(); onToggle(alertId); }}
          className="mt-1.5 flex items-center gap-1 text-[10px] text-cyan-400/70 hover:text-cyan-300 transition-colors"
        >
          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {isExpanded ? "收起" : "展开全部"}
        </button>
      )}
    </div>
  );
}

export default function AlertPanel({ alerts, onStreamComplete, onAlertClick, selectedAlertIds }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [completedStreams, setCompletedStreams] = useState<Set<string>>(
    () => new Set(),
  );
  const [expandedAlerts, setExpandedAlerts] = useState<Set<string>>(
    () => new Set(),
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [alerts]);

  const handleStreamComplete = useCallback(
    (id: string) => {
      setCompletedStreams((prev) => new Set(prev).add(id));
      onStreamComplete?.(id);
    },
    [onStreamComplete],
  );

  const handleToggleExpand = useCallback((id: string) => {
    setExpandedAlerts((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectedCount = selectedAlertIds?.size ?? 0;

  if (alerts.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 p-6">
        <Bell size={36} className="mb-3 opacity-30" />
        <p className="text-sm">等待主动消息...</p>
        <p className="text-xs mt-1 text-gray-700">触发模拟数据后，Overwatch 将在此推送警报</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      {/* Multi-select hint bar */}
      {onAlertClick && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-gray-800/40 border border-gray-800/60">
          <Check size={10} className="text-cyan-500/60 shrink-0" />
          <span className="text-[10px] text-gray-500">
            点击可多选插入上下文
          </span>
          {selectedCount > 0 && (
            <span className="ml-auto text-[10px] font-mono bg-cyan-500/20 text-cyan-400 px-1.5 py-0.5 rounded-full">
              {selectedCount} 已选
            </span>
          )}
        </div>
      )}

      {alerts.map((alert) => {
        const cfg = priorityConfig[alert.priority] || priorityConfig.INFO;
        const Icon = cfg.icon;
        const shouldStream =
          alert.streaming && !completedStreams.has(alert.id);
        const isClickable = !shouldStream && onAlertClick;
        const isSelected = selectedAlertIds?.has(alert.id) ?? false;
        return (
          <div
            key={alert.id}
            onClick={isClickable ? () => onAlertClick(alert) : undefined}
            className={`relative border ${cfg.border} ${cfg.bg} rounded-lg p-3 animate-fade-in transition-all ${
              isClickable
                ? "cursor-pointer hover:ring-1 hover:ring-cyan-500/40"
                : ""
            } ${isSelected ? "ring-2 ring-cyan-500/60 ring-offset-1 ring-offset-[#0b0b11]" : ""}`}
          >
            {/* Selected checkmark badge */}
            {isSelected && (
              <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-cyan-500 flex items-center justify-center shadow-[0_0_6px_rgba(34,211,238,0.5)]">
                <Check size={9} className="text-black" strokeWidth={3} />
              </div>
            )}
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} className={cfg.badge.split(" ")[1]} />
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${cfg.badge}`}
              >
                {cfg.label}
              </span>
              {isClickable && !isSelected && (
                <span className="text-[9px] text-cyan-500/50 ml-1">
                  点击插入上下文
                </span>
              )}
              {isSelected && (
                <span className="text-[9px] text-cyan-400 ml-1">
                  已选中
                </span>
              )}
              <span className={`text-[10px] text-gray-600 ${isSelected ? "mr-5" : "ml-auto"} ml-auto`}>
                {new Date(alert.timestamp).toLocaleTimeString()}
              </span>
            </div>
            {shouldStream ? (
              <StreamingAlertContent
                content={alert.content}
                onComplete={() => handleStreamComplete(alert.id)}
              />
            ) : (
              <CollapsibleContent
                content={alert.content}
                alertId={alert.id}
                expandedAlerts={expandedAlerts}
                onToggle={handleToggleExpand}
              />
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
