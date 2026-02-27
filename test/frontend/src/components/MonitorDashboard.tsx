import { AlertTriangle, AlertCircle, Info, Activity } from "lucide-react";
import type { LogEvent } from "../types";

export type FilterLevel = "CRITICAL" | "WARNING" | "INFO" | null;

interface Props {
  events: LogEvent[];
  activeFilter: FilterLevel;
  onFilterChange: (level: FilterLevel) => void;
}

export default function MonitorDashboard({ events, activeFilter, onFilterChange }: Props) {
  const critical = events.filter((e) => e.level === "CRITICAL").length;
  const warning = events.filter((e) => e.level === "WARNING").length;
  const info = events.filter((e) => e.level === "INFO").length;

  const stats: {
    label: string; value: number; level: FilterLevel;
    icon: typeof AlertTriangle; color: string; bg: string; border: string;
    activeBg: string; activeBorder: string;
  }[] = [
    { label: "关键威胁", value: critical, level: "CRITICAL", icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30", activeBg: "bg-red-500/25", activeBorder: "border-red-500/70" },
    { label: "警告事件", value: warning, level: "WARNING", icon: AlertCircle, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30", activeBg: "bg-amber-500/25", activeBorder: "border-amber-500/70" },
    { label: "常规事件", value: info, level: "INFO", icon: Info, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", activeBg: "bg-emerald-500/25", activeBorder: "border-emerald-500/70" },
    { label: "总事件数", value: events.length, level: null, icon: Activity, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30", activeBg: "bg-blue-500/25", activeBorder: "border-blue-500/70" },
  ];

  return (
    <div className="grid grid-cols-2 gap-2">
      {stats.map(({ label, value, level, icon: Icon, color, bg, border, activeBg, activeBorder }) => {
        const isActive = activeFilter === level;
        return (
          <div
            key={label}
            onClick={() => onFilterChange(isActive ? null : level)}
            className={`${isActive ? activeBg : bg} border ${isActive ? activeBorder : border} rounded-lg px-3 py-2 flex items-center gap-2 cursor-pointer transition-all duration-200 hover:scale-[1.02] select-none ${isActive ? "ring-1 ring-white/10 shadow-lg" : "hover:brightness-125"}`}
          >
            <Icon size={16} className={color} />
            <div>
              <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
              <div className="text-[10px] text-gray-500">{label}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
