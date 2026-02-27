import { Link } from "react-router-dom";
import { Bot, Radio, Shield, Zap, Code, Eye } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center p-8">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-emerald-400 tracking-wider mb-3">
          NEUROFORGE
        </h1>
        <p className="text-gray-500 text-lg">Agent 能力展示系统</p>
        <div className="w-24 h-0.5 bg-emerald-500/30 mx-auto mt-4" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl w-full">
        {/* Passive Agent Card */}
        <Link
          to="/passive"
          className="group border border-emerald-900/40 rounded-xl p-6 bg-gradient-to-br from-[#0e0e16] to-[#0a0f14] hover:border-emerald-600/50 transition-all hover:shadow-lg hover:shadow-emerald-900/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Bot size={24} className="text-blue-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-100 group-hover:text-emerald-300 transition-colors">
                被动型 Agent
              </h2>
              <span className="text-xs text-gray-600 font-mono">passive-agent</span>
            </div>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            通用编程与写作助手，响应用户指令，提供高质量的代码生成、代码审查、文档撰写等能力。
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { icon: Code, label: "代码生成" },
              { icon: Eye, label: "代码审查" },
              { icon: Zap, label: "文档撰写" },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="flex items-center gap-1 text-xs text-gray-500 bg-gray-800/40 px-2 py-1 rounded"
              >
                <Icon size={12} />
                {label}
              </span>
            ))}
          </div>
        </Link>

        {/* Active Agent Card */}
        <Link
          to="/active"
          className="group border border-emerald-900/40 rounded-xl p-6 bg-gradient-to-br from-[#0e0e16] to-[#140a0a] hover:border-red-600/40 transition-all hover:shadow-lg hover:shadow-red-900/20"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Radio size={24} className="text-red-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-100 group-hover:text-red-300 transition-colors">
                主动型 Agent
              </h2>
              <span className="text-xs text-gray-600 font-mono">active-agent · Overwatch</span>
            </div>
          </div>
          <p className="text-gray-400 text-sm mb-4">
            战场态势感知指挥官。通过感知器监控实时数据流，自动检测威胁并主动发起对话报告。
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { icon: Shield, label: "威胁感知" },
              { icon: Radio, label: "主动报告" },
              { icon: Zap, label: "使命召唤主题" },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="flex items-center gap-1 text-xs text-gray-500 bg-gray-800/40 px-2 py-1 rounded"
              >
                <Icon size={12} />
                {label}
              </span>
            ))}
          </div>
        </Link>
      </div>

      <div className="mt-12 text-center text-gray-700 text-xs">
        <p>NeuroForge Agent Engine · 能力演示 · v1.0</p>
      </div>
    </div>
  );
}
