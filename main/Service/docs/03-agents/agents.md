# Agents

Agent 与远端模型的连接方式已统一为模型级配置 + `LLMClient`。

## 原则

- 不再向 SDK 注入内置厂商 Provider
- 所有供应商通过自定义模型配置接入
- 仅依赖兼容格式与必要请求参数
