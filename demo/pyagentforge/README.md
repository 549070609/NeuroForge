# PyAgentForge

**版本**: v2.0.0 | [变更日志](./CHANGELOG.md) | [迁移指南](./MIGRATION.md)

**通用型 AI Agent 服务底座 - 模型即代理，代码即配置**

---

## 📖 目录

- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [功能模块](#功能模块)
  - [1. Kernel - 核心引擎](#1-kernel---核心引擎)
  - [2. Providers - AI 提供商](#2-providers---ai-提供商)
  - [3. Tools - 工具系统](#3-tools---工具系统)
  - [4. Commands - 命令系统](#4-commands---命令系统)
  - [5. Skills - 技能系统](#5-skills---技能系统)
  - [6. Thinking - 扩展思考](#6-thinking---扩展思考)
  - [7. Compaction - 上下文压缩](#7-compaction---上下文压缩)
  - [8. Model Registry - 模型注册表](#8-model-registry---模型注册表)
  - [9. Plugin System - 插件系统](#9-plugin-system---插件系统)
  - [10. MCP - 协议支持](#10-mcp---协议支持)
  - [11. LSP - 语言服务器](#11-lsp---语言服务器)
  - [12. API Server - 服务接口](#12-api-server---服务接口)
- [使用场景](#使用场景)
- [配置说明](#配置说明)
- [进阶文档](#进阶文档)

---

## 🎯 核心特性

### v2.0 重大更新

- ✨ **插件化架构**: 功能模块化，按需加载
- 🚀 **工厂函数**: `create_engine()` 快速启动
- 📦 **清晰的 API**: 移除向后兼容，更简洁的设计
- 🧠 **扩展思考**: 支持 Claude Extended Thinking
- 🗜️ **智能压缩**: 自动上下文管理
- 📚 **完整文档**: [迁移指南](./MIGRATION.md) + [变更日志](./CHANGELOG.md)

### 设计理念

- **模型即代理**: LLM 驱动的自主决策
- **代码即配置**: Python 优先的配置方式
- **渐进增强**: 从简单到复杂的平滑过渡

---

## 🚀 快速开始

### 安装

```bash
pip install -e .
```

### 最小示例

```python
import asyncio
from pyagentforge import create_minimal_engine
from pyagentforge.providers import AnthropicProvider

async def main():
    # 创建 Provider
    provider = AnthropicProvider(api_key="your-api-key")

    # 创建 Agent 引擎
    engine = create_minimal_engine(provider=provider)

    # 运行 Agent
    result = await engine.run("你好，请介绍一下你自己")
    print(result)

asyncio.run(main())
```

### 带插件的完整示例

```python
import asyncio
from pyagentforge import create_engine
from pyagentforge.providers import AnthropicProvider
from pyagentforge.config.plugin_config import PluginConfig

async def main():
    # 创建 Provider
    provider = AnthropicProvider(api_key="your-api-key")

    # 配置插件
    plugin_config = PluginConfig.from_file("plugin_config.yaml")

    # 创建带插件的 Agent 引擎
    engine = await create_engine(
        provider=provider,
        plugin_config=plugin_config,
        working_dir="/path/to/project"
    )

    # 运行 Agent
    result = await engine.run("请帮我分析这个项目的结构")
    print(result)

asyncio.run(main())
```

---

## 📦 功能模块

### 1. Kernel - 核心引擎

**Agent 的心脏，实现核心执行循环**

#### 核心组件

- **AgentEngine**: Agent 执行引擎
- **ContextManager**: 上下文管理器
- **ToolExecutor**: 工具执行器
- **ToolRegistry**: 工具注册表

#### 使用示例

```python
from pyagentforge import AgentEngine, ContextManager, ToolRegistry
from pyagentforge.providers import AnthropicProvider

# 创建工具注册表
tools = ToolRegistry()
tools.register_builtin_tools()

# 创建上下文管理器
context = ContextManager(
    system_prompt="You are a helpful coding assistant."
)

# 创建引擎
engine = AgentEngine(
    provider=AnthropicProvider(api_key="your-key"),
    tool_registry=tools,
    context=context,
)

# 运行
result = await engine.run("帮我创建一个 Python 项目")
```

#### Agent 执行循环

```
User Input → Context → Model → Tool Calls → Execute → Results → Context → ...
                                    ↓
                              Final Response
```

---

### 2. Providers - AI 提供商

**多模型支持，统一接口**

#### 支持的提供商

| Provider | 模型示例 | 特性 |
|----------|---------|------|
| Anthropic | claude-sonnet-4, claude-opus-4 | Extended Thinking, Vision |
| OpenAI | gpt-4o, gpt-4-turbo | Function Calling |
| Google | gemini-2.0-flash-exp | Multi-modal |

#### 使用示例

```python
from pyagentforge.providers import AnthropicProvider, OpenAIProvider

# Anthropic
anthropic = AnthropicProvider(
    api_key="your-anthropic-key",
    model="claude-sonnet-4-20250514",
    max_tokens=4096
)

# OpenAI
openai = OpenAIProvider(
    api_key="your-openai-key",
    model="gpt-4o",
    temperature=0.7
)
```

#### 动态切换模型

```python
# 从模型注册表获取配置
from pyagentforge.core.model_registry import get_registry

registry = get_registry()
model_config = registry.get_model("claude-sonnet-4")

provider = AnthropicProvider(
    api_key="your-key",
    model=model_config.id,
    max_tokens=model_config.max_output_tokens
)
```

---

### 3. Tools - 工具系统

**丰富的内置工具，灵活的扩展机制**

#### 内置工具列表

| 工具名称 | 功能 | 示例场景 |
|---------|------|---------|
| **bash** | 执行 Shell 命令 | 运行测试、Git 操作 |
| **read** | 读取文件 | 查看代码内容 |
| **write** | 创建文件 | 生成新文件 |
| **edit** | 编辑文件 | 修改代码片段 |
| **glob** | 文件模式匹配 | 查找 `**/*.py` |
| **grep** | 内容搜索 | 搜索代码关键词 |
| **websearch** | 网络搜索 | 查找文档 |
| **webfetch** | 抓取网页 | 获取在线资源 |
| **todo** | 任务管理 | 规划工作流程 |
| **question** | 用户提问 | 收集用户需求 |
| **plan** | 规划工具 | 制定执行计划 |
| **task** | 子代理任务 | 复杂任务分解 |
| **ls** | 列出目录 | 查看项目结构 |
| **codesearch** | 代码搜索 | 查找函数定义 |
| **multiedit** | 批量编辑 | 修改多个文件 |

#### 使用示例

```python
from pyagentforge import ToolRegistry
from pyagentforge.tools.builtin import BashTool, ReadTool

# 方式 1: 注册内置工具
tools = ToolRegistry()
tools.register_builtin_tools()  # 注册所有内置工具

# 方式 2: 按需注册
tools = ToolRegistry()
tools.register(BashTool())
tools.register(ReadTool())

# 方式 3: 自定义工具
from pyagentforge import BaseTool

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "我的自定义工具"

    async def execute(self, **kwargs):
        # 实现工具逻辑
        return "执行结果"

tools.register(MyCustomTool())
```

#### 工具权限控制

```python
from pyagentforge.tools.permission import PermissionChecker

# 自定义权限检查器
checker = PermissionChecker(
    allowed_tools=["read", "write", "bash"],
    ask_callback=lambda tool, params: True  # 自动批准
)

engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    permission_checker=checker
)
```

---

### 4. Commands - 命令系统

**用户自定义命令，动态注入提示词**

#### 命令语法

```
!command`arguments`
```

#### 使用示例

```python
from pyagentforge.commands import CommandRegistry, CommandLoader

# 创建命令注册表
registry = CommandRegistry()

# 从目录加载命令
loader = CommandLoader(registry)
loader.load_from_dir(".agents/commands")

# 命令示例文件: .agents/commands/review.md
"""
---
name: review
description: 代码审查命令
---

请对以下代码进行全面的审查:

1. 代码质量和可读性
2. 潜在的 Bug
3. 性能问题
4. 安全隐患

代码内容:
{{args}}
"""

# 在 Agent 中使用
engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    command_registry=registry
)

# 用户输入: !review`src/main.py`
# 会自动展开为完整的提示词
```

#### 内置命令

- `!help` - 列出所有命令
- `!clear` - 清除对话历史
- `!compact` - 手动触发上下文压缩

---

### 5. Skills - 技能系统

**领域知识注入，按需加载**

#### 技能结构

```
skills/
├── python/
│   └── SKILL.md          # Python 开发技能
├── web-development/
│   └── SKILL.md          # Web 开发技能
└── database/
    └── SKILL.md          # 数据库技能
```

#### 技能文件示例

```markdown
---
name: python
description: Python 开发最佳实践
tags: [python, coding, best-practices]
---

# Python Development Skill

## Code Style
- Follow PEP 8
- Use type hints
- Write docstrings

## Testing
- Use pytest
- Aim for >80% coverage
- Test edge cases

## Common Patterns
...
```

#### 使用示例

```python
from pyagentforge.skills import SkillRegistry, SkillLoader

# 创建技能注册表
registry = SkillRegistry()

# 从目录加载技能
loader = SkillLoader(registry)
loader.load_from_dir("skills")

# 在 Agent 中使用
engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    skill_registry=registry
)

# Agent 会根据任务自动加载相关技能
# 例如: "帮我优化这段 Python 代码" → 加载 python 技能
```

---

### 6. Thinking - 扩展思考

**支持 Claude Extended Thinking，提升推理能力**

#### 思考级别

| 级别 | Budget Tokens | 适用场景 |
|-----|--------------|---------|
| `NONE` | 0 | 简单任务 |
| `LOW` | 1024 | 常规对话 |
| `MEDIUM` | 4096 | 复杂推理 |
| `HIGH` | 16384 | 深度分析 |

#### 使用示例

```python
from pyagentforge import AgentEngine
from pyagentforge.core.thinking import ThinkingLevel, create_thinking_config
from pyagentforge.providers import AnthropicProvider

# 检查模型是否支持思考
from pyagentforge.core.thinking import supports_thinking

model_id = "claude-sonnet-4-20250514"
if supports_thinking(model_id):
    print(f"{model_id} 支持扩展思考")

# 创建思考配置
thinking_config = create_thinking_config(
    level=ThinkingLevel.HIGH,
    model_id=model_id
)

# 在 Agent 中使用
provider = AnthropicProvider(api_key="your-key", model=model_id)
engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    thinking_level=ThinkingLevel.HIGH  # 设置思考级别
)

# 动态调整
engine.set_thinking_level(ThinkingLevel.MEDIUM)
```

---

### 7. Compaction - 上下文压缩

**自动压缩上下文，节省 Token**

#### 压缩策略

- 保留最近的消息
- 保留重要的系统消息
- 压缩或移除旧的对话内容
- 智能摘要中间内容

#### 使用示例

```python
from pyagentforge import AgentEngine
from pyagentforge.core.compaction import Compactor, CompactionSettings

# 创建压缩器
compactor = Compactor(
    provider=provider,
    settings=CompactionSettings(
        enabled=True,
        reserve_tokens=8000,        # 保留的 Token 数量
        keep_recent_tokens=4000,    # 保留最近消息的 Token
        trigger_threshold=0.8       # 触发压缩的阈值
    ),
    max_context_tokens=200000
)

# 在 Agent 中使用
engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    compactor=compactor  # 自动压缩
)

# 手动触发压缩
messages = [...]
if compactor.should_compact(messages):
    result = await compactor.compact(messages)
    print(f"压缩完成: 节省 {result.tokens_saved} tokens")
```

---

### 8. Model Registry - 模型注册表

**动态模型注册与管理**

#### 使用示例

```python
from pyagentforge.core.model_registry import (
    get_registry,
    register_model,
    ModelConfig,
    ProviderType
)

# 获取全局注册表
registry = get_registry()

# 查询内置模型
model = registry.get_model("claude-sonnet-4")
print(f"模型名称: {model.name}")
print(f"上下文窗口: {model.context_window}")
print(f"支持工具: {model.supports_tools}")

# 注册自定义模型
custom_model = ModelConfig(
    id="my-custom-model",
    name="My Custom Model",
    provider=ProviderType.OPENAI,
    api_type="openai-completions",
    context_window=32000,
    max_output_tokens=4096,
    base_url="https://api.example.com/v1",
    api_key_env="CUSTOM_API_KEY",
    cost_input=0.5,      # 每千 token 输入成本
    cost_output=1.5      # 每千 token 输出成本
)
register_model(custom_model, aliases=["custom", "mcm"])

# 通过别名查找
model = registry.get_model("custom")

# 计算调用成本
cost = model.calculate_cost(
    input_tokens=10000,
    output_tokens=2000
)
print(f"成本: ${cost:.4f}")

# 获取所有模型
all_models = registry.get_all_models()
print(f"已注册 {len(all_models)} 个模型")

# 按 Provider 过滤
anthropic_models = registry.get_models_by_provider(ProviderType.ANTHROPIC)
```

---

### 9. Plugin System - 插件系统

**插件化架构，按需扩展**

#### 插件类型

| 类型 | 说明 | 示例 |
|-----|------|------|
| `PROVIDER` | AI 提供商插件 | 自定义 API 接入 |
| `TOOL` | 工具插件 | 集成外部服务 |
| `HOOK` | 钩子插件 | 生命周期拦截 |
| `SKILL` | 技能插件 | 领域知识扩展 |

#### 使用示例

```python
from pyagentforge import Plugin, PluginMetadata, PluginType, HookType

class MyPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            description="我的自定义插件",
            plugin_type=PluginType.TOOL,
            author="Your Name"
        )

    async def initialize(self, context):
        # 初始化插件
        pass

    def get_tools(self):
        # 返回插件提供的工具
        return [MyCustomTool()]

# 插件配置文件: plugin_config.yaml
"""
plugins:
  - name: my-plugin
    enabled: true
    config:
      option1: value1
"""

# 加载插件
from pyagentforge.config.plugin_config import PluginConfig

plugin_config = PluginConfig.from_file("plugin_config.yaml")
engine = await create_engine(
    provider=provider,
    plugin_config=plugin_config
)
```

---

### 10. MCP - 协议支持

**Model Context Protocol 支持**

#### 支持的传输方式

- **HTTP**: HTTP/HTTPS 传输
- **Stdio**: 标准输入输出
- **SSE**: Server-Sent Events

#### 使用示例

```python
from pyagentforge.mcp import (
    MCPClient,
    MCPClientManager,
    create_transport
)

# 创建 MCP 客户端
transport = create_transport(
    transport_type="stdio",
    command="python",
    args=["mcp_server.py"]
)

client = MCPClient(transport)
await client.connect()

# 列出可用工具
tools = await client.list_tools()
for tool in tools:
    print(f"工具: {tool.name} - {tool.description}")

# 调用 MCP 工具
result = await client.call_tool(
    tool_name="example_tool",
    arguments={"param": "value"}
)

# 使用 MCP 客户端管理器
manager = MCPClientManager()
await manager.add_client("server1", client)

# 将 MCP 工具注册到 Agent
mcp_tools = manager.get_all_tools()
for tool in mcp_tools:
    tool_registry.register(tool)
```

---

### 11. LSP - 语言服务器

**Language Server Protocol 支持**

#### 支持的功能

- 代码补全
- 定义跳转
- 引用查找
- 符号搜索
- 诊断信息

#### 使用示例

```python
from pyagentforge.lsp import LSPManager

# 创建 LSP 管理器
manager = LSPManager()

# 启动 Python LSP
await manager.start_server(
    language="python",
    command=["pylsp"],
    workspace_root="/path/to/project"
)

# 获取补全
completions = await manager.get_completions(
    file_path="src/main.py",
    line=10,
    character=5
)

# 查找定义
definition = await manager.goto_definition(
    file_path="src/main.py",
    line=20,
    character=10
)

# 查找引用
references = await manager.find_references(
    file_path="src/main.py",
    line=15,
    character=8
)
```

---

### 12. API Server - 服务接口

**REST API 和 WebSocket 支持**

#### 启动 API 服务

```python
from pyagentforge.api import create_app

app = create_app()

# 运行服务
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### REST API 端点

| 端点 | 方法 | 说明 |
|-----|------|------|
| `/api/v1/sessions` | POST | 创建会话 |
| `/api/v1/sessions/{id}` | GET | 获取会话信息 |
| `/api/v1/sessions/{id}/messages` | POST | 发送消息 |
| `/api/v1/agents` | GET | 列出可用 Agent |
| `/api/v1/tools` | GET | 列出工具 |

#### WebSocket 使用

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session-id');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'message',
    content: '你好，Agent'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('收到消息:', data);
};
```

---

## 🎯 使用场景

### 1. 代码助手

```python
engine = await create_engine(
    provider=provider,
    working_dir="/path/to/project",
    config={
        "system_prompt": "你是一个专业的代码助手"
    }
)

result = await engine.run("帮我重构这个函数，提高可读性")
```

### 2. 自动化测试

```python
result = await engine.run("""
请为 src/calculator.py 中的所有函数编写单元测试:
- 使用 pytest
- 覆盖边界情况
- 包含类型检查
""")
```

### 3. 项目分析

```python
result = await engine.run("""
分析这个项目的技术栈:
1. 识别使用的主要框架和库
2. 评估项目结构
3. 提出改进建议
""")
```

### 4. 文档生成

```python
result = await engine.run("""
为 src/api/ 目录下的所有模块生成 API 文档:
- 使用 Google 风格的 docstring
- 包含使用示例
- 标注参数类型
""")
```

---

## ⚙️ 配置说明

### 环境变量

创建 `.env` 文件:

```bash
# Anthropic
ANTHROPIC_API_KEY=your-anthropic-key

# OpenAI
OPENAI_API_KEY=your-openai-key

# Google
GOOGLE_API_KEY=your-google-key

# 日志级别
LOG_LEVEL=INFO
```

### Agent 配置

```python
from pyagentforge.kernel.engine import AgentConfig

config = AgentConfig(
    system_prompt="You are a helpful assistant",
    max_tokens=4096,
    temperature=1.0,
    max_iterations=100,  # 最大工具调用迭代次数
    permission_checker=my_checker  # 权限检查器
)

engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    config=config
)
```

---

## 📚 进阶文档

| 文档 | 说明 |
|-----|------|
| [变更日志](./CHANGELOG.md) | 版本更新记录 |
| [迁移指南](./MIGRATION.md) | 从 v1.x 迁移 |
| [API 文档](./docs/api.md) | 详细 API 参考 |
| [示例代码](./examples/) | 完整示例集合 |

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

---

**Happy Coding with PyAgentForge! 🚀**