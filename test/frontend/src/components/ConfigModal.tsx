import { useEffect, useState } from "react";
import {
  X, Save, TestTube, Loader, CheckCircle, AlertCircle,
  Cpu, Key, Globe, Thermometer, Hash,
} from "lucide-react";
import type { AppConfig, ModelOption } from "../utils/api";
import { fetchConfig, updateConfig, testConnection, fetchModelsForProvider } from "../utils/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

const PROVIDERS = [
  { id: "anthropic", name: "Anthropic (Claude)" },
  { id: "openai", name: "OpenAI (GPT)" },
  { id: "custom", name: "自定义 (Custom Endpoint)" },
];

const CUSTOM_API_TYPES = [
  { id: "openai-completions", name: "OpenAI 兼容格式" },
  { id: "anthropic-messages", name: "Anthropic Messages 格式" },
];

const AUTH_HEADER_TYPES = [
  { id: "bearer", name: "Bearer (Authorization)" },
  { id: "api-key", name: "api-key" },
  { id: "x-api-key", name: "x-api-key" },
];

export default function ConfigModal({ open, onClose }: Props) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [localProvider, setLocalProvider] = useState("anthropic");
  const [localModel, setLocalModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [localApiType, setLocalApiType] = useState("openai-completions");
  const [localAuthHeaderType, setLocalAuthHeaderType] = useState("bearer");
  const [localBaseUrl, setLocalBaseUrl] = useState("");
  const [localTemp, setLocalTemp] = useState(0.4);
  const [localMaxTokens, setLocalMaxTokens] = useState(4096);
  const [localMode, setLocalMode] = useState("mock");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; msg: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (open) {
      fetchConfig().then((c) => {
        setConfig(c);
        setLocalProvider(c.provider);
        setLocalModel(c.model);
        setLocalApiType(c.api_type || "openai-completions");
        setLocalAuthHeaderType(c.auth_header_type || "bearer");
        setLocalBaseUrl(c.base_url || "");
        setLocalTemp(c.temperature);
        setLocalMaxTokens(c.max_tokens);
        setLocalMode(c.mode);
        setApiKey("");
      });
    }
  }, [open]);

  useEffect(() => {
    fetchModelsForProvider(localProvider).then(setModels);
  }, [localProvider]);

  if (!open) return null;

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const currentModel = localProvider === "custom" && customModel ? customModel : localModel;
      const res = await testConnection({
        provider: localProvider,
        api_type: localProvider === "custom" ? localApiType : undefined,
        auth_header_type: localProvider === "custom" ? localAuthHeaderType : undefined,
        api_key: apiKey || undefined,
        base_url: localBaseUrl || undefined,
        model: currentModel || undefined,
      });
      setTestResult({
        success: res.success,
        msg: res.success
          ? `连接成功: ${res.response?.slice(0, 100) || "OK"}`
          : `连接失败: ${res.error || "Unknown error"}`,
      });
    } catch (err) {
      setTestResult({ success: false, msg: `请求失败: ${err}` });
    }
    setTesting(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    const updates: Record<string, unknown> = {
      mode: localMode,
      provider: localProvider,
      api_type: localApiType,
      auth_header_type: localAuthHeaderType,
      model: localProvider === "custom" && customModel ? customModel : localModel,
      base_url: localBaseUrl,
      temperature: localTemp,
      max_tokens: localMaxTokens,
    };
    if (apiKey) {
      updates.api_key = apiKey;
    }
    await updateConfig(updates);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#111118] border border-gray-800 rounded-xl w-full max-w-lg mx-4 shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/60">
          <div className="flex items-center gap-2">
            <Cpu size={18} className="text-emerald-400" />
            <h2 className="text-base font-semibold text-gray-100">模型配置</h2>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* Mode Toggle */}
          <div>
            <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">运行模式</label>
            <div className="flex gap-2">
              {[
                { id: "mock", label: "Mock 模拟" },
                { id: "llm", label: "真实 LLM" },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setLocalMode(m.id)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                    localMode === m.id
                      ? "bg-emerald-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {localMode === "llm" && (
            <>
              {/* Provider */}
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">
                  Provider
                </label>
                <select
                  value={localProvider}
                  onChange={(e) => {
                    const p = e.target.value;
                    setLocalProvider(p);
                    setLocalModel("");
                    setCustomModel("");
                    if (p !== "custom") setLocalApiType("openai-completions");
                  }}
                  className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-700/60"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              {/* API Key */}
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Key size={12} />
                  API Key
                  {config?.api_key_set && (
                    <span className="text-emerald-500 text-[10px] ml-1">
                      (已配置: {config.api_key_preview})
                    </span>
                  )}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={config?.api_key_set ? "留空保持不变，输入新值覆盖" : "输入 API Key..."}
                  className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-700/60"
                />
              </div>

              {/* Base URL + API Type (custom only) */}
              {localProvider === "custom" && (
                <>
                  <div>
                    <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                      <Globe size={12} />
                      Base URL
                    </label>
                    <input
                      value={localBaseUrl}
                      onChange={(e) => setLocalBaseUrl(e.target.value)}
                      placeholder="https://api.example.com/v1"
                      className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-700/60"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">
                      API 协议格式
                    </label>
                    <div className="flex gap-2">
                      {CUSTOM_API_TYPES.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setLocalApiType(t.id)}
                          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                            localApiType === t.id
                              ? "bg-emerald-600 text-white"
                              : "bg-gray-800 text-gray-400 hover:text-gray-200"
                          }`}
                        >
                          {t.name}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">
                      认证方式 (401 可尝试切换)
                    </label>
                    <div className="flex gap-2 flex-wrap">
                      {AUTH_HEADER_TYPES.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setLocalAuthHeaderType(t.id)}
                          className={`py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                            localAuthHeaderType === t.id
                              ? "bg-emerald-600 text-white"
                              : "bg-gray-800 text-gray-400 hover:text-gray-200"
                          }`}
                        >
                          {t.name}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Model */}
              <div>
                <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">模型</label>
                {models.length > 0 ? (
                  <select
                    value={localModel}
                    onChange={(e) => setLocalModel(e.target.value)}
                    className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-700/60"
                  >
                    <option value="">选择模型...</option>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>{m.name} ({m.id})</option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    placeholder="输入模型 ID（如 gpt-4o, deepseek-chat）"
                    className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-700/60"
                  />
                )}
              </div>

              {/* Temperature & Max Tokens */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Thermometer size={12} />
                    Temperature: {localTemp}
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={localTemp}
                    onChange={(e) => setLocalTemp(parseFloat(e.target.value))}
                    className="w-full accent-emerald-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Hash size={12} />
                    Max Tokens
                  </label>
                  <input
                    type="number"
                    value={localMaxTokens}
                    onChange={(e) => setLocalMaxTokens(parseInt(e.target.value) || 4096)}
                    min={256}
                    max={32768}
                    step={256}
                    className="w-full bg-[#0a0a0f] border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-emerald-700/60"
                  />
                </div>
              </div>

              {/* Test Connection */}
              <div>
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800/60 disabled:opacity-50 transition-colors"
                >
                  {testing ? (
                    <Loader size={14} className="animate-spin" />
                  ) : (
                    <TestTube size={14} />
                  )}
                  {testing ? "测试中..." : "测试连接"}
                </button>
                {testResult && (
                  <div
                    className={`mt-2 text-xs px-3 py-2 rounded-lg flex items-start gap-2 ${
                      testResult.success
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                        : "bg-red-500/10 text-red-400 border border-red-500/30"
                    }`}
                  >
                    {testResult.success ? <CheckCircle size={14} className="shrink-0 mt-0.5" /> : <AlertCircle size={14} className="shrink-0 mt-0.5" />}
                    <span className="break-all">{testResult.msg}</span>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-800/60">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? (
              <Loader size={14} className="animate-spin" />
            ) : saved ? (
              <CheckCircle size={14} />
            ) : (
              <Save size={14} />
            )}
            {saving ? "保存中..." : saved ? "已保存" : "保存配置"}
          </button>
        </div>
      </div>
    </div>
  );
}
