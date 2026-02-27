import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  AlertCircle,
  Info,
  ChevronDown,
  ChevronUp,
  Clock,
} from "lucide-react";
import type { SituationSnapshot } from "../types";

interface Props {
  snapshot: SituationSnapshot;
  compact?: boolean;
}

export default function SituationCard({ snapshot, compact = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { stats, recentEvents, capturedAt, timeRange } = snapshot;

  const barTotal = stats.total || 1;
  const critPct = (stats.critical / barTotal) * 100;
  const warnPct = (stats.warning / barTotal) * 100;
  const infoPct = (stats.info / barTotal) * 100;

  return (
    <div className="mt-2 border border-cyan-500/30 bg-cyan-950/15 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-cyan-900/10 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <Activity size={13} className="text-cyan-400 shrink-0" />
        <span className="text-[11px] font-semibold text-cyan-300 tracking-wide">
          态势数据快照
        </span>
        <div className="flex items-center gap-1 ml-auto text-[10px] text-gray-500">
          <Clock size={10} />
          {new Date(capturedAt).toLocaleTimeString()}
        </div>
        {expanded ? (
          <ChevronUp size={12} className="text-cyan-500" />
        ) : (
          <ChevronDown size={12} className="text-cyan-500" />
        )}
      </div>

      {/* Stats bar (always visible) */}
      <div className="px-3 pb-2">
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1 text-red-400">
            <AlertTriangle size={10} /> {stats.critical}
          </span>
          <span className="flex items-center gap-1 text-amber-400">
            <AlertCircle size={10} /> {stats.warning}
          </span>
          <span className="flex items-center gap-1 text-emerald-400">
            <Info size={10} /> {stats.info}
          </span>
          <span className="text-gray-500 ml-auto">
            共 {stats.total} 事件
          </span>
        </div>
        {/* Threat bar */}
        <div className="flex h-1.5 rounded-full overflow-hidden bg-gray-800 mt-1.5">
          {stats.critical > 0 && (
            <div className="bg-red-500 transition-all" style={{ width: `${critPct}%` }} />
          )}
          {stats.warning > 0 && (
            <div className="bg-amber-500 transition-all" style={{ width: `${warnPct}%` }} />
          )}
          {stats.info > 0 && (
            <div className="bg-emerald-500 transition-all" style={{ width: `${infoPct}%` }} />
          )}
        </div>
      </div>

      {/* Expanded: recent events */}
      {expanded && recentEvents.length > 0 && (
        <div className="border-t border-cyan-500/15 px-3 py-2 space-y-1 max-h-40 overflow-y-auto">
          {timeRange && (
            <div className="text-[9px] text-gray-600 mb-1">
              {timeRange.from} — {timeRange.to}
            </div>
          )}
          {recentEvents.map((evt, i) => {
            const levelColor =
              evt.level === "CRITICAL"
                ? "text-red-400"
                : evt.level === "WARNING"
                ? "text-amber-400"
                : "text-emerald-400";
            return (
              <div
                key={`${evt.timestamp}-${i}`}
                className="flex items-start gap-2 text-[10px] font-mono"
              >
                <span className={`${levelColor} font-semibold shrink-0 w-14`}>
                  [{evt.level.slice(0, 4)}]
                </span>
                <span className="text-gray-500 shrink-0">
                  {evt.timestamp.split("T")[1]?.slice(0, 8) || "??:??:??"}
                </span>
                <span className="text-gray-300 break-all">{evt.message}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
