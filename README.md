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
├── Docs/                      # 项目文档与规范
├── llm_config.json            # LLM 运行时配置（填入模型与密钥）
├── llm_config.template.json   # LLM 配置模板（拷贝后改名即可）
└── llm_config_schema.json     # LLM 配置 JSON Schema（结构校验）
```

> LLM 配置说明详见 [`docs/sdk/15-llm-config.md`](docs/sdk/15-llm-config.md)。

---

### `agentforge-engine/` — 核心 Agent 引擎

Agent 引擎核心包 `pyagentforge`，实现 Agent 运行时、协议兼容调用、工具系统与插件体系。

```
agentforge-engine/
├── pyagentforge/
│   ├── kernel/            # 引擎核心：AgentEngine、ContextManager、ToolExecutor
│   ├── protocols.py       # 协议适配：请求/响应格式兼容
│   ├── client.py          # 统一 LLMClient 入口
│   ├── tools/             # 工具系统（base / registry / permission / builtin）
│   ├── plugin/            # 插件框架：PluginManager、PluginRegistry、Hook 系统
│   ├── plugins/           # 插件实现（tools / middleware / integration / protocol / interface）
│   ├── agents/            # Agent 定义栈（building / prompts / skills / commands / metadata / registry）
│   ├── codesearch/        # 代码搜索：LSP Bridge、索引器、解析器
│   ├── mcp/               # MCP（Model Context Protocol）支持
│   ├── lsp/               # LSP（Language Server Protocol）支持
│   ├── config/            # 配置管理（settings / llm_config / env_parser）
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
├── gateway/               # FastAPI 应用（路由 / 中间件 / 应用装配）
├── services/              # 服务实现（Agent / 模型配置 / Proxy 会话等）
├── schemas/               # Pydantic 请求/响应模型
├── persistence/           # 持久化（store / 会话快照）
├── events/                # 事件投递
├── core/                  # 服务基础设施（ServiceRegistry 等）
├── tests/                 # 服务层测试
└── docs/                  # Service 模块文档
```

## 文档索引

> SDK 文档位于 `docs/sdk/`，Service 文档位于 `main/Service/docs/`，项目级规范位于 `main/Docs/`。

| 类别 | 入口 |
|------|------|
| 总体清理计划（P0–P2） | [`docs/architecture-optimization-plan-p0-p2.md`](docs/architecture-optimization-plan-p0-p2.md) |
| 历史变更 / 硬切说明 | [`main/agentforge-engine/CHANGELOG.md`](main/agentforge-engine/CHANGELOG.md) |
| SDK 总览 | [`docs/sdk/00-overview.md`](docs/sdk/00-overview.md) |
| LLMClient 入口 | [`docs/sdk/10-llm-client.md`](docs/sdk/10-llm-client.md) |
| LLM 配置文件规范 | [`docs/sdk/15-llm-config.md`](docs/sdk/15-llm-config.md) |
| MCP 客户端 / 协议 | [`docs/sdk/20-mcp-client.md`](docs/sdk/20-mcp-client.md)、[`docs/sdk/70-mcp-protocol-and-transport.md`](docs/sdk/70-mcp-protocol-and-transport.md) |
| LSP 客户端 / 协议 | [`docs/sdk/30-lsp-client.md`](docs/sdk/30-lsp-client.md)、[`docs/sdk/40-lsp-manager.md`](docs/sdk/40-lsp-manager.md)、[`docs/sdk/80-lsp-protocol-types.md`](docs/sdk/80-lsp-protocol-types.md) |
| 工厂函数 / Kernel & 内置工具 | [`docs/sdk/50-factory-functions.md`](docs/sdk/50-factory-functions.md)、[`docs/sdk/60-kernel-and-tools.md`](docs/sdk/60-kernel-and-tools.md) |
| Service 文档门户 | [`main/Service/docs/README.md`](main/Service/docs/README.md)、[`main/Service/README.md`](main/Service/README.md) |
| API 全量参考 | [`main/Service/docs/API_FULL.md`](main/Service/docs/API_FULL.md) |
| 目录 & 开发导航（中文） | [`main/Docs/main-structure-analysis-and-dev-navigation.md`](main/Docs/main-structure-analysis-and-dev-navigation.md) |
| 日志上报规范 | [`main/Docs/日志上报规范-总览.md`](main/Docs/日志上报规范-总览.md) |
| Agent 建模指南 | [`main/Docs/AGent构建指南-本体建模.md`](main/Docs/AGent构建指南-本体建模.md)、[`main/agentforge-engine/docs/AGent/README.md`](main/agentforge-engine/docs/AGent/README.md) |

## 当前模型接入原则

- SDK 不再内置任何厂商 Provider
- 所有远端模型通过模型级配置接入
- 仅保留 `api_type`、`base_url`、`model_name`、`api_key`、`headers`、`timeout` 等必要参数
- 协议兼容由 `LLMClient` + `protocols.py` 统一处理

## 一键跑全仓测试

根 `pyproject.toml` 已聚合所有子包的测试路径与 `pythonpath`，在仓库根目录执行：

```bash
# 安装开发依赖（首次）
pip install -e main/agentforge-engine[dev]
pip install -e main/Service[dev]

# 运行整仓测试
pytest
```

默认开启 `--import-mode=importlib`，避免不同子包下同名 `PLUGIN.py` / `config.py` 在 `sys.modules` 里相互覆盖；`testpaths` 覆盖 SDK、Service、Agent、Long-memory、Embeddings 全部用例。

如只跑某一子模块，可直接传目录：

```bash
pytest main/Service/tests
pytest main/agentforge-engine/tests/building
pytest main/Long-memory/long-memory/tests
```
