import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Bot, Radio, Home, Settings, Cpu } from "lucide-react";
import ConfigModal from "./ConfigModal";
import { fetchHealth } from "../utils/api";

export default function Navbar() {
  const { pathname } = useLocation();
  const [configOpen, setConfigOpen] = useState(false);
  const [mode, setMode] = useState<string>("mock");

  const links = [
    { to: "/", label: "首页", icon: Home },
    { to: "/passive", label: "被动 Agent", icon: Bot },
    { to: "/active", label: "主动 Agent", icon: Radio },
  ];

  useEffect(() => {
    fetchHealth()
      .then((h) => setMode(h.mode))
      .catch(() => {});
  }, [configOpen]);

  return (
    <>
      <nav className="border-b border-emerald-900/40 bg-[#0d0d14]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
          <span className="text-emerald-400 font-bold tracking-wider text-lg mr-4">
            NEUROFORGE
          </span>
          {links.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
                pathname === to
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          ))}

          <div className="ml-auto flex items-center gap-3">
            <span
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
                mode === "llm"
                  ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                  : "border-gray-700 text-gray-500 bg-gray-800/40"
              }`}
            >
              <Cpu size={12} />
              {mode === "llm" ? "LLM" : "Mock"}
            </span>
            <button
              onClick={() => setConfigOpen(true)}
              className="flex items-center gap-1.5 text-gray-400 hover:text-emerald-400 px-2.5 py-1.5 rounded-lg hover:bg-gray-800/40 transition-colors text-sm"
            >
              <Settings size={16} />
              配置
            </button>
          </div>
        </div>
      </nav>
      <ConfigModal open={configOpen} onClose={() => setConfigOpen(false)} />
    </>
  );
}
