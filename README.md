# NeuroForge

> AI Agent 服务平台 — "Model as Agent, Code as Configuration"

## 项目简介

NeuroForge 是一个 Python Monorepo 架构的 AI Agent 服务平台，提供通用 AI Agent 服务基础设施，支持多 LLM Provider、插件化架构与全栈演示应用。

## 目录结构

```
main/
├── agentforge-engine/     # 核心 Agent 引擎（pyagentforge）
├── Service/               # FastAPI 网关与服务层
├── Agent/                 # Agent 定义与元数据
├── Long-memory/           # 长期记忆插件（ChromaDB）
├── perception/            # 主动感知插件
├── Docs/                  # 项目文档与规范
├── default_llm_config.json    # LLM 默认配置
├── llm_config_schema.json     # LLM 配置 JSON Schema
└── llm_config.template.json   # LLM 配置模板
```

---

### `agentforge-engine/` — 核心 Agent 引擎

Agent 引擎核心包 `pyagentforge`，实现 Agent 运行时、多 Provider 适配、工具系统与插件体系。

```
agentforge-engine/
├── pyagentforge/
│   ├── kernel/            # 引擎核心：AgentEngine、ContextManager、ToolExecutor
│   ├── providers/         # LLM Provider 适配（Anthropic / OpenAI / Google / GLM）
│   ├── tools/             # 工具系统
│   │   ├── base.py        # BaseTool 基类
│   │   ├── registry.py    # ToolRegistry 注册中心
│   │   ├── permission.py  # 权限检查
│   │   └── builtin/       # 30+ 内置工具（bash、read、write、edit、grep、glob、
│   │                      #   websearch、webfetch、todo、plan、task、codesearch …）
│   ├── plugin/            # 插件框架：PluginManager、PluginRegistry、Hook 系统
│   ├── plugins/           # 插件实现（40+ 插件）
│   │   ├── providers/     #   Provider 插件（anthropic / openai / google）
│   │   ├── tools/         #   工具插件（ast_grep / python_ast / file_tools / web_tools）
│   │   ├── middleware/    #   中间件插件（thinking / compaction / failover / error_recovery）
│   │   ├── integration/   #   集成插件（task_system / chain_of_thought / persistence / events …）
│   │   ├── protocol/      #   协议插件（MCP Server / MCP Client / LSP）
│   │   ├── interface/     #   接口插件（REST API / WebSocket）
│   │   └── skills/        #   技能插件（skill_loader）
│   ├── prompts/           # Prompt 系统：多 Provider Prompt 变体与能力模块
│   ├── skills/            # Skills 系统：SkillLoader、SkillRegistry
│   ├── codesearch/        # 代码搜索：LSP Bridge、索引器、解析器
│   ├── mcp/               # MCP（Model Context Protocol）支持
│   ├── lsp/               # LSP（Language Server Protocol）支持
│   ├── config/            # 配置管理
│   └── utils/             # 通用工具函数
├── tests/                 # 测试套件（kernel / providers / tools / plugin / integration）
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
│   │   ├── app.py         # Application Factory
│   │   ├── middleware/    # 中间件（auth / rate_limit / workspace）
│   │   └── routes/        # API 路由
│   │       ├── health.py      # GET  /health
│   │       ├── agents.py      # /api/v1/agents
│   │       ├── workspaces.py  # /api/v1/workspaces
│   │       ├── sessions.py    # /api/v1/sessions
│   │       ├── execute.py     # /api/v1/execute
│   │       ├── tools.py       # /api/v1/tools
│   │       └── proxy.py       # /api/v1/proxy
│   ├── services/          # 服务实现
│   │   ├── base.py            # BaseService
│   │   ├── agent_service.py   # Agent 管理服务
│   │   └── proxy/             # AgentProxyService / AgentExecutor
│   ├── workspace/         # 工作区管理（WorkspaceManager / PathValidator）
│   ├── execution/         # 执行引擎（Executor / Options / Result）
│   ├── sessions/          # 会话管理（SessionManager）
│   ├── schemas/           # Pydantic 请求/响应 Schema
│   ├── events/            # SSE 事件系统
│   ├── persistence/       # 持久化存储
│   └── config/            # ServiceSettings 配置
├── tests/                 # 测试套件
└── docs/                  # API 文档
```

---

### `Agent/` — Agent 定义与元数据

Agent 目录系统，包含 Agent 定义、模板和 MateAgent 工具链。

```
Agent/
├── core/                  # 核心模块（AgentDirectory / AgentBaseConfig）
├── mate-agent/            # 元级 Agent（管理其他 Agent）
│   ├── agent.yaml         # Agent 定义
│   ├── system_prompt.md   # 系统提示词
│   ├── tools/             # MateAgent 工具（CRUD / 分析 / 配置 / 系统）
│   ├── templates/         # Agent 模板（simple / tool / reasoning）
│   ├── subagents/         # 子 Agent（builder / modifier / analyzer / tester）
│   └── docs/              # 文档
├── active-agent/          # 主动型 Agent 定义
└── passive-agent/         # 被动型 Agent 定义
```

---

### `Long-memory/` — 长期记忆插件

基于 ChromaDB 的长期记忆系统，支持语义搜索与本地 Embedding。

```
Long-memory/
├── embeddings/            # 本地 Embedding 插件
│   ├── PLUGIN.py          # 插件入口
│   ├── embeddings_provider.py
│   └── models/            # 本地模型（all-MiniLM-L6-v2）
└── long-memory/           # 长期记忆插件
    ├── PLUGIN.py          # 插件入口
    ├── vector_store.py    # ChromaDB 向量存储
    ├── tools/             # 记忆工具（store / search / delete / list）
    ├── middleware/         # 中间件
    ├── memory_processor/  # 记忆处理器插件
    ├── super_compress/    # 超级压缩插件
    └── tests/             # 测试
```

---

### `perception/` — 主动感知插件

基于 ATON/TOON 日志格式的主动感知与决策插件。

```
perception/
├── PLUGIN.py              # 插件入口
├── detector.py            # 格式检测
├── parser.py              # 日志解析
├── perception.py          # 感知与决策
├── executor.py            # 决策执行
├── tools.py               # 插件工具
└── tests/                 # 测试
```

---

### `Docs/` — 项目文档

```
Docs/
├── JSON_CONFIG_README.zh-CN.md        # JSON 配置指南
├── ATON与TOON格式介绍.md              # ATON/TOON 格式介绍
├── AGent构建指南-本体建模.md           # Agent 构建指南
├── 日志上报规范-总览.md               # 日志上报规范总览
└── 日志上报规范-ATON与TOON格式详解.md  # ATON/TOON 格式详解
```

---

## 快速开始

```bash
# 安装核心引擎
cd main/agentforge-engine && pip install -e ".[dev]"

# 启动 Service API（:8000）
cd main/Service && pip install -e ".[dev]"
uvicorn Service.gateway.app:create_app --factory --reload --port 8000

# 启动演示应用（Backend :8080 + Frontend :5173）
cd test && python start.py --install
```

## 技术栈

| 层级 | 技术 |
|------|------|
| **核心引擎** | Python 3.11+, Pydantic v2, anthropic, openai, google-generativeai |
| **服务层** | FastAPI, Uvicorn, SQLAlchemy + aiosqlite |
| **长期记忆** | ChromaDB, sentence-transformers (all-MiniLM-L6-v2) |
| **前端演示** | React 19, TypeScript, Vite 7, Tailwind CSS 4 |
| **测试** | pytest, pytest-asyncio, pytest-cov |

---

*2026-02-28*
