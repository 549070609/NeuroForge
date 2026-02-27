import { useEffect, useRef } from "react";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import type { LogEvent } from "../types";

interface Props {
  events: LogEvent[];
}

const levelConfig: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  CRITICAL: { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10" },
  WARNING: { icon: AlertCircle, color: "text-amber-400", bg: "bg-amber-500/10" },
  INFO: { icon: Info, color: "text-emerald-400", bg: "bg-emerald-500/10" },
};

export default function LogStream({ events }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-600 font-mono text-sm">
        等待战场数据流...
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full overflow-y-auto font-mono text-xs space-y-0.5 p-2">
      {events.map((evt, i) => {
        const cfg = levelConfig[evt.level] || levelConfig.INFO;
        const Icon = cfg.icon;
        return (
          <div
            key={`${evt.timestamp}-${i}`}
            className={`flex items-start gap-2 px-2 py-1.5 rounded ${cfg.bg} animate-fade-in`}
          >
            <Icon size={12} className={`${cfg.color} shrink-0 mt-0.5`} />
            <span className="text-gray-500 shrink-0">
              {evt.timestamp.split("T")[1]?.slice(0, 8) || "??:??:??"}
            </span>
            <span className={`${cfg.color} font-semibold shrink-0 w-16`}>
              [{evt.level}]
            </span>
            <span className="text-gray-300 break-all">{evt.message}</span>
          </div>
        );
      })}
    </div>
  );
}
