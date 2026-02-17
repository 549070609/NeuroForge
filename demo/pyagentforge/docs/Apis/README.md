# PyAgentForge API 文档总览

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本目录包含 PyAgentForge v2.0 的完整 API 文档，涵盖核心引擎、Provider、工具系统、命令技能、插件系统和配置协议。

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [01-core-api.md](./01-core-api.md) | 核心 API - AgentEngine, ContextManager, ToolExecutor |
| [02-providers-api.md](./02-providers-api.md) | Provider API - Anthropic, OpenAI, Google |
| [03-tools-api.md](./03-tools-api.md) | 工具系统 API - 内置工具和自定义工具开发 |
| [04-commands-skills-api.md](./04-commands-skills-api.md) | 命令与技能系统 API |
| [05-plugin-system-api.md](./05-plugin-system-api.md) | 插件系统 API - 插件架构和钩子系统 |
| [06-configuration-api.md](./06-configuration-api.md) | 配置与协议支持 API - Settings, MCP, LSP, REST API |

---

## 快速开始

### 安装

```bash
pip install pyagentforge
```

### 基础使用

```python
import asyncio
from pyagentforge import AgentEngine, ToolRegistry, AnthropicProvider

async def main():
    # 创建 Provider
    provider = AnthropicProvider(
        api_key="your-api-key",
        model="claude-3-5-sonnet-20241022",
    )

    # 创建工具注册表
    tool_registry = ToolRegistry()

    # 创建 Agent 引擎
    engine = AgentEngine(
        provider=provider,
        tool_registry=tool_registry,
    )

    # 运行 Agent
    response = await engine.run("Hello, how can you help me?")
    print(response)

asyncio.run(main())
```

### 使用配置文件

```python
from pyagentforge import create_engine, AnthropicProvider, PluginConfig

async def main():
    # 加载配置
    config = PluginConfig.from_yaml("config.yaml")

    # 创建 Provider
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")

    # 创建引擎（自动加载插件）
    engine = await create_engine(
        provider=provider,
        plugin_config=config,
        working_dir="/path/to/workdir",
    )

    response = await engine.run("Analyze this codebase")
    print(response)

asyncio.run(main())
```

### 启动 REST API 服务

```python
import uvicorn
from pyagentforge.api.app import app

uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## API 分类索引

### 核心 API

| 组件 | 说明 | 文档 |
|------|------|------|
| `AgentEngine` | Agent 执行引擎 | [01-core-api.md](./01-core-api.md#1-agentengine) |
| `AgentConfig` | Agent 配置 | [01-core-api.md](./01-core-api.md#11-agentconfig) |
| `ContextManager` | 上下文管理器 | [01-core-api.md](./01-core-api.md#2-contextmanager) |
| `ToolExecutor` | 工具执行器 | [01-core-api.md](./01-core-api.md#3-toolexecutor) |
| `ToolRegistry` | 工具注册表 | [01-core-api.md](./01-core-api.md#4-toolregistry) |
| `BaseTool` | 工具基类 | [01-core-api.md](./01-core-api.md#6-basetool) |
| `BaseProvider` | Provider 基类 | [01-core-api.md](./01-core-api.md#7-baseprovider) |

### Provider API

| 组件 | 说明 | 文档 |
|------|------|------|
| `AnthropicProvider` | Anthropic Claude | [02-providers-api.md](./02-providers-api.md#3-anthropicprovider) |
| `OpenAIProvider` | OpenAI GPT | [02-providers-api.md](./02-providers-api.md#4-openaiprovider) |
| `GoogleProvider` | Google Gemini | [02-providers-api.md](./02-providers-api.md#5-googleprovider) |
| `create_provider()` | Provider 工厂 | [02-providers-api.md](./02-providers-api.md#6-工厂方法) |

### 工具 API

| 组件 | 说明 | 文档 |
|------|------|------|
| `BashTool` | 执行 Shell 命令 | [03-tools-api.md](./03-tools-api.md#21-bashtool) |
| `ReadTool` | 读取文件 | [03-tools-api.md](./03-tools-api.md#22-readtool) |
| `WriteTool` | 写入文件 | [03-tools-api.md](./03-tools-api.md#23-writetool) |
| `EditTool` | 编辑文件 | [03-tools-api.md](./03-tools-api.md#24-edittool) |
| `GlobTool` | 文件模式匹配 | [03-tools-api.md](./03-tools-api.md#25-globtool) |
| `GrepTool` | 内容搜索 | [03-tools-api.md](./03-tools-api.md#26-greptool) |
| `@tool` | 工具装饰器 | [03-tools-api.md](./03-tools-api.md#5-工具装饰器) |

### 命令与技能 API

| 组件 | 说明 | 文档 |
|------|------|------|
| `Command` | 命令模型 | [04-commands-skills-api.md](./04-commands-skills-api.md#22-command) |
| `CommandLoader` | 命令加载器 | [04-commands-skills-api.md](./04-commands-skills-api.md#3-commandloader) |
| `Skill` | 技能模型 | [04-commands-skills-api.md](./04-commands-skills-api.md#62-skill) |
| `SkillLoader` | 技能加载器 | [04-commands-skills-api.md](./04-commands-skills-api.md#7-skillloader) |

### 插件系统 API

| 组件 | 说明 | 文档 |
|------|------|------|
| `Plugin` | 插件基类 | [05-plugin-system-api.md](./05-plugin-system-api.md#5-plugin---插件基类) |
| `PluginType` | 插件类型枚举 | [05-plugin-system-api.md](./05-plugin-system-api.md#2-plugintype) |
| `PluginMetadata` | 插件元数据 | [05-plugin-system-api.md](./05-plugin-system-api.md#3-pluginmetadata) |
| `PluginContext` | 插件上下文 | [05-plugin-system-api.md](./05-plugin-system-api.md#4-plugincontext) |
| `PluginManager` | 插件管理器 | [05-plugin-system-api.md](./05-plugin-system-api.md#6-pluginmanager) |
| `HookType` | 钩子类型 | [05-plugin-system-api.md](./05-plugin-system-api.md#71-hooktype) |
| `HookRegistry` | 钩子注册表 | [05-plugin-system-api.md](./05-plugin-system-api.md#72-hookregistry) |

### 配置与协议 API

| 组件 | 说明 | 文档 |
|------|------|------|
| `Settings` | 应用配置 | [06-configuration-api.md](./06-configuration-api.md#1-settings---应用配置) |
| `PluginConfig` | 插件配置 | [06-configuration-api.md](./06-configuration-api.md#2-pluginconfig---插件配置) |
| `MCPServer` | MCP 服务端 | [06-configuration-api.md](./06-configuration-api.md#43-mcpserver) |
| `LSPClient` | LSP 客户端 | [06-configuration-api.md](./06-configuration-api.md#52-lspclient) |
| REST API | FastAPI 接口 | [06-configuration-api.md](./06-configuration-api.md#6-rest-api-接口) |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     Plugins Layer                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ Interface  │ │  Protocol  │ │   Tools    │ │  Skill   │ │
│  │ (REST API) │ │ (MCP, LSP) │ │ (Extended) │ │ (Loader) │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     Plugin Manager                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│  │   Registry   │ │    Hooks     │ │  DependencyResolver  ││
│  └──────────────┘ └──────────────┘ └──────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│                       Kernel Layer                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│  │ AgentEngine  │ │ContextManager│ │   ToolExecutor       ││
│  └──────────────┘ └──────────────┘ └──────────────────────┘│
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│  │ ToolRegistry │ │ BaseProvider │ │    Core Tools        ││
│  └──────────────┘ └──────────────┘ └──────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**设计原则:**
- **Kernel**: 最小核心，提供 Agent 执行的基础能力
- **Plugin System**: 扩展能力，通过插件添加功能

---

## 消息类型

PyAgentForge 使用统一的消息格式:

```python
# 文本块
TextBlock(type="text", text="Hello")

# 工具调用块
ToolUseBlock(type="tool_use", id="xxx", name="bash", input={"command": "ls"})

# 工具结果块
ToolResultBlock(type="tool_result", tool_use_id="xxx", content="...", is_error=False)

# 消息
Message(role="user", content="...")
Message(role="assistant", content=[TextBlock(...), ToolUseBlock(...)])

# Provider 响应
ProviderResponse(
    content=[...],
    stop_reason="end_turn",  # 或 "tool_use", "max_tokens"
    usage={"input_tokens": 100, "output_tokens": 50}
)
```

---

## 工厂函数

### create_engine()

```python
async def create_engine(
    provider: BaseProvider,
    config: Optional[Dict[str, Any]] = None,
    plugin_config: Optional[PluginConfig] = None,
    working_dir: Optional[str] = None,
) -> AgentEngine
```

创建配置好的 AgentEngine。

### create_minimal_engine()

```python
def create_minimal_engine(
    provider: BaseProvider,
    working_dir: Optional[str] = None,
) -> AgentEngine
```

创建最小化引擎（无插件）。

### create_provider()

```python
def create_provider(model_id: str, **kwargs) -> BaseProvider
```

根据模型 ID 自动创建 Provider。

---

## 版本信息

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | Kernel + Plugin 架构重构 |
| v1.x | 2026-02-01 | 初始版本 |

---

## 相关资源

- [PyAgentForge 分析报告](../PyAgentForge/PyAgentForge-vs-OpenCodeServer-2026-02-16-完整对比.md)
- [三方对比报告](../PyAgentForge/三方对比报告-OpenClaw-PyAgentForge-OpenCodeServer.md)
- [OpenCode Server 深度说明书](../OpenCode/OpenCode-Server深度功能说明书/README.md)
- [Claude Code 学习笔记](../learn/02-Claude-Code-学习笔记/)

---

*本文档由 Claude Code 自动生成*
