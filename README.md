# NeuroForge

> AI Agent 服务平台 — "Model as Agent, Code as Configuration"

## 项目简介

NeuroForge 是一个 Python Monorepo 架构的 AI Agent 服务平台，提供通用 AI Agent 服务基础设施，采用协议驱动的模型接入方式、插件化架构与全栈演示应用。

## 目录结构

```
main/
├── agentforge-engine/         # 核心 Agent 引擎（pyagentforge）
├── Service/                   # FastAPI 网关与服务层
├── Agent/                     # Agent 定义与元数据
├── Long-memory/               # 长期记忆插件（ChromaDB）
├── perception/                # 主动感知插件
├── Docs/                      # 项目文档与规范
├── default_llm_config.json    # LLM 默认配置
├── llm_config_schema.json     # LLM 配置 JSON Schema
└── llm_config.template.json   # LLM 配置模板
```

---

### `agentforge-engine/` — 核心 Agent 引擎

Agent 引擎核心包 `pyagentforge`，实现 Agent 运行时、协议兼容调用、工具系统与插件体系。

```
agentforge-engine/
├── pyagentforge/
│   ├── kernel/            # 引擎核心：AgentEngine、ContextManager、ToolExecutor
│   ├── protocols.py       # 协议适配：请求/响应格式兼容
│   ├── client.py          # 统一 LLMClient 入口
│   ├── tools/             # 工具系统
│   │   ├── base.py        # BaseTool 基类
│   │   ├── registry.py    # ToolRegistry 注册中心
│   │   ├── permission.py  # 权限检查
│   │   └── builtin/       # 内置工具集合
│   ├── plugin/            # 插件框架：PluginManager、PluginRegistry、Hook 系统
│   ├── plugins/           # 插件实现（tools / middleware / integration / protocol / interface）
│   ├── prompts/           # Prompt 系统与能力模块
│   ├── skills/            # Skills 系统：SkillLoader、SkillRegistry
│   ├── codesearch/        # 代码搜索：LSP Bridge、索引器、解析器
│   ├── mcp/               # MCP（Model Context Protocol）支持
│   ├── lsp/               # LSP（Language Server Protocol）支持
│   ├── config/            # 配置管理
│   └── utils/             # 通用工具函数
├── tests/                 # 测试套件
├── data/                  # 数据文件与命令定义
└── examples/              # 示例代码
```

---

### `Service/` — FastAPI 网关与服务层

REST API 网关，提供 Agent 管理、工作区隔离、会话管理与执行代理等功能。

```
Service/
├── Service/
│   ├── gateway/           # FastAPI 应用
│   ├── services/          # 服务实现
│   ├── workspace/         # 工作区管理
│   ├── execution/         # 执行引擎
│   ├── sessions/          # 会话管理
│   ├── schemas/           # Pydantic 请求/响应模型
│   └── core/              # 服务基础设施
├── tests/                 # 服务层测试
└── docs/                  # Service 模块文档
```

## 当前模型接入原则

- SDK 不再内置任何厂商 Provider
- 所有远端模型通过模型级配置接入
- 仅保留 `api_type`、`base_url`、`model_name`、`api_key`、`headers`、`timeout` 等必要参数
- 协议兼容由 `LLMClient` + `protocols.py` 统一处理
