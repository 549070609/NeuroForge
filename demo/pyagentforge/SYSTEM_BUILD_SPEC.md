# PyAgentForge 系统构建规范说明

> **适用对象**: 大模型增量开发
> **版本**: v2.0.0
> **最后更新**: 2026-02-16

本文档定义 PyAgentForge 的架构规范、代码风格和开发约定，确保增量功能符合系统设计。

---

## 一、架构总览

### 1.1 核心理念

```
模型即代理 (Model IS the Agent)
代码即配置 (Code IS Configuration)
```

Agent 本质是一个**执行循环**，由 LLM 驱动工具调用：

```python
while iteration < max_iterations:
    response = llm.call(messages, tools)
    if not response.has_tool_calls:
        return response.text  # 任务完成
    results = execute_tools(response.tool_calls)
    messages.append(results)
```

### 1.2 v2.0 架构层级

```
┌─────────────────────────────────────────┐
│         应用层 (examples/api)            │
├─────────────────────────────────────────┤
│       Plugin System (插件系统)           │
│  - 扩展能力: Tools/Providers/Hooks       │
├─────────────────────────────────────────┤
│         Kernel (核心引擎)                │
│  - AgentEngine (执行循环)                │
│  - ToolExecutor (工具执行)               │
│  - ContextManager (上下文)               │
│  - BaseTool/BaseProvider (基类)         │
├─────────────────────────────────────────┤
│       Core Tools (最小工具集)            │
│  - Bash/Read/Write/Edit/Glob/Grep       │
├─────────────────────────────────────────┤
│       Providers (LLM提供商)              │
│  - AnthropicProvider/OpenAIProvider     │
└─────────────────────────────────────────┘
```

### 1.3 目录结构规范

```
pyagentforge/
├── kernel/              # 核心 (v2.0 新架构)
│   ├── engine.py        # AgentEngine - 核心执行循环
│   ├── executor.py      # ToolExecutor - 工具执行器
│   ├── context.py       # ContextManager - 上下文管理
│   ├── message.py       # Message 数据结构
│   ├── base_tool.py     # BaseTool 基类
│   ├── base_provider.py # BaseProvider 基类
│   └── core_tools/      # 核心工具集 (最小)
│       ├── bash.py
│       ├── read.py
│       ├── write.py
│       ├── edit.py
│       ├── glob.py
│       └── grep.py
│
├── plugin/              # 插件系统 (v2.0)
│   ├── base.py          # Plugin 基类
│   ├── manager.py       # PluginManager
│   ├── hooks.py         # Hook 系统
│   ├── loader.py        # 插件加载器
│   └── registry.py      # 插件注册表
│
├── plugins/             # 内置插件实现
│   ├── interface/       # API/CLI/WebSocket
│   ├── protocol/        # MCP/LSP
│   └── tool/            # 扩展工具包
│
├── tools/               # 扩展工具 (v1.x 兼容)
│   ├── base.py
│   ├── registry.py
│   └── builtin/         # 内置扩展工具
│       ├── todo.py
│       ├── websearch.py
│       ├── task.py
│       └── ...
│
├── providers/           # LLM 提供商
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   ├── google_provider.py
│   └── factory.py
│
├── core/                # 旧核心 (v1.x 兼容)
│   ├── parallel.py      # ParallelSubagentExecutor
│   ├── thinking.py      # 思维链配置
│   └── ...
│
├── skills/              # 技能系统
│   ├── loader.py
│   └── registry.py
│
├── commands/            # Command 系统
│   ├── parser.py
│   └── registry.py
│
├── mcp/                 # MCP 协议
│   ├── client.py
│   └── server.py
│
├── lsp/                 # LSP 协议
│   ├── client.py
│   └── manager.py
│
├── api/                 # REST API
│   ├── app.py
│   └── routes/
│
├── config/              # 配置系统
│   ├── settings.py
│   └── plugin_config.py
│
└── utils/               # 工具函数
    ├── logging.py
    └── gitignore.py
```

---

## 二、核心组件开发规范

### 2.1 BaseTool - 工具基类

**位置**: `kernel/base_tool.py`

**所有工具必须继承此类**:

```python
from pyagentforge.kernel.base_tool import BaseTool

class MyTool(BaseTool):
    # 1. 类属性 - 元数据
    name = "my_tool"                    # 工具名称 (唯一)
    description = "工具描述"             # 给 LLM 看的描述
    parameters_schema: dict = {        # JSON Schema
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "参数说明",
            }
        },
        "required": ["param1"],
    }
    timeout = 60                        # 超时秒数
    risk_level = "low"                  # low/medium/high

    def __init__(self, working_dir: str | None = None):
        """初始化工具（可选）"""
        self.working_dir = working_dir

    async def execute(self, **kwargs) -> str:
        """
        执行工具 - 必须实现

        Returns:
            str: 工具执行结果（文本形式）
        """
        param1 = kwargs.get("param1")
        result = do_something(param1)
        return str(result)
```

**关键约束**:

1. ✅ `execute()` **必须返回 str**
2. ✅ 错误信息格式: `f"Error: {error_details}"`
3. ✅ 使用 `logger` 记录关键操作
4. ✅ 参数验证依赖 JSON Schema (由 LLM 提供)
5. ⚠️  高风险工具需设置 `risk_level = "high"`

**示例参考**:
- 简单工具: `kernel/core_tools/read.py`
- 复杂工具: `tools/builtin/task.py`

---

### 2.2 BaseProvider - LLM 提供商基类

**位置**: `kernel/base_provider.py`

```python
from pyagentforge.kernel.base_provider import BaseProvider

class MyProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        """
        调用 LLM API

        Returns:
            ProviderResponse: 统一响应格式
        """
        # 调用 API
        response = await call_llm_api(...)

        # 解析响应
        return ProviderResponse(
            content=response_content,
            text=text_content,
            tool_calls=tool_calls_list,
            stop_reason=stop_reason,
        )
```

**关键约束**:

1. ✅ 必须实现 `create_message()`
2. ✅ 返回 `ProviderResponse` 对象
3. ✅ 支持 `tools` 参数（可能为空）
4. ✅ 正确处理 `stop_reason`:
   - `"tool_use"` - 有工具调用
   - `"end_turn"` - 对话结束

---

### 2.3 Plugin - 插件基类

**位置**: `plugin/base.py`

**插件开发模式**:

```python
from pyagentforge.plugin import Plugin, PluginMetadata, PluginType

class MyPlugin(Plugin):
    # 1. 元数据
    metadata = PluginMetadata(
        id="tool.advanced-tools",
        name="Advanced Tools Pack",
        version="1.0.0",
        type=PluginType.TOOL,
        description="提供高级工具集",
        dependencies=["core.base-tools"],      # 可选
        provides=["capability.advanced-edit"], # 可选
    )

    # 2. 生命周期钩子（可选实现）
    async def on_plugin_activate(self) -> None:
        """插件激活时"""
        self.context.logger.info("Plugin activated")

    # 3. 系统钩子（可选实现）
    async def on_before_tool_call(self, tool_use) -> Optional[Any]:
        """工具执行前拦截"""
        if tool_use.name == "bash":
            self.context.logger.info(f"Bash command: {tool_use.input}")
        return None  # 返回 None 不拦截

    # 4. 资源提供（必须实现以提供工具）
    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        return [
            AdvancedEditTool(),
            SmartSearchTool(),
        ]
```

**插件类型** (`PluginType`):

| Type | 用途 | 示例 |
|------|------|------|
| `INTERFACE` | API/CLI/WebSocket | REST API, WebSocket Server |
| `PROTOCOL` | 协议支持 | MCP Server, LSP Client |
| `TOOL` | 工具包 | Advanced Tools Pack |
| `SKILL` | 知识加载器 | Domain Knowledge Loader |
| `PROVIDER` | LLM 提供商 | Google Gemini Provider |
| `MIDDLEWARE` | 中间件 | Logging, Rate Limiting |
| `INTEGRATION` | 集成插件 | GitHub Integration |

**可用钩子**:

```python
# 引擎生命周期
on_engine_init(engine)
on_engine_start(engine)
on_engine_stop(engine)

# LLM 调用
on_before_llm_call(messages) -> Optional[list]  # 可修改消息
on_after_llm_call(response) -> Optional[Response]  # 可修改响应

# 工具调用
on_before_tool_call(tool_use) -> Optional[ToolUse]  # 可替换工具调用
on_after_tool_call(result) -> Optional[str]  # 可修改结果

# 其他
on_context_overflow(token_count) -> bool  # 处理上下文溢出
on_task_complete(result)
on_skill_load(skill)
on_subagent_spawn(subagent)
```

---

### 2.4 AgentEngine - 核心引擎

**位置**: `kernel/engine.py`

**不直接修改 Engine，通过插件扩展**

**配置 AgentConfig**:

```python
from pyagentforge.kernel.engine import AgentConfig

config = AgentConfig(
    system_prompt="You are a helpful assistant.",
    max_tokens=4096,
    temperature=1.0,
    max_iterations=100,
    permission_checker=my_checker,  # 可选
)
```

---

## 三、代码风格规范

### 3.1 类型注解

**必须使用类型注解**:

```python
# ✅ 正确
def execute(self, command: str, timeout: int = 120000) -> str:
    ...

async def load_plugin(self, plugin_id: str) -> Plugin:
    ...

# ❌ 错误
def execute(self, command, timeout=120000):
    ...
```

### 3.2 异步编程

**所有 I/O 操作必须异步**:

```python
# ✅ 正确
async def execute(self, file_path: str) -> str:
    async with aiofiles.open(file_path) as f:
        content = await f.read()
    return content

# ❌ 错误（阻塞）
def execute(self, file_path: str) -> str:
    with open(file_path) as f:
        return f.read()
```

### 3.3 日志规范

**使用结构化日志**:

```python
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

# ✅ 正确
logger.info(
    "Tool executed successfully",
    extra_data={
        "tool": self.name,
        "duration_ms": duration,
    }
)

logger.error(
    "Failed to execute command",
    extra_data={"error": str(e), "command": command},
)

# ❌ 错误
logger.info(f"Tool {self.name} executed in {duration}ms")
```

### 3.4 错误处理

**工具执行错误返回 str**:

```python
async def execute(self, command: str) -> str:
    try:
        result = await run_command(command)
        return result
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {self.timeout} seconds"
    except Exception as e:
        logger.error("Command failed", extra_data={"error": str(e)})
        return f"Error: {str(e)}"
```

### 3.5 数据类

**使用 dataclass 定义数据结构**:

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ToolResult:
    """工具执行结果"""
    tool_use_id: str
    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 四、新增功能开发指南

### 4.1 新增工具 (Tool)

**场景**: 添加一个新工具（如代码格式化工具）

**步骤**:

1. **确定位置**:
   - 核心工具 → `kernel/core_tools/` (仅最小工具集)
   - 扩展工具 → `tools/builtin/` (推荐)
   - 插件工具 → `plugins/tool/my_plugin/`

2. **创建工具类**:

```python
# tools/builtin/format.py
from pyagentforge.kernel.base_tool import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

class FormatTool(BaseTool):
    """代码格式化工具"""

    name = "format"
    description = """格式化代码文件。

支持多种编程语言，使用标准格式化工具（black, prettier 等）。
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件绝对路径",
            },
            "formatter": {
                "type": "string",
                "enum": ["auto", "black", "prettier"],
                "description": "格式化工具",
            },
        },
        "required": ["file_path"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        file_path: str,
        formatter: str = "auto",
    ) -> str:
        """执行代码格式化"""
        logger.info(
            "Formatting file",
            extra_data={"file_path": file_path, "formatter": formatter},
        )

        # 检测文件类型
        suffix = Path(file_path).suffix

        # 选择格式化工具
        if formatter == "auto":
            formatter = self._detect_formatter(suffix)

        # 执行格式化
        try:
            result = await self._run_formatter(formatter, file_path)
            return f"Successfully formatted {file_path}"
        except Exception as e:
            return f"Error: {str(e)}"

    def _detect_formatter(self, suffix: str) -> str:
        # 实现省略
        pass

    async def _run_formatter(self, formatter: str, file_path: str) -> None:
        # 实现省略
        pass
```

3. **注册工具**:

```python
# tools/builtin/__init__.py
from .format import FormatTool

__all__ = [
    # ... 其他工具
    "FormatTool",
]

# 在注册函数中添加
def register_builtin_tools(registry: ToolRegistry) -> None:
    # ... 其他工具
    registry.register(FormatTool())
```

---

### 4.2 新增插件 (Plugin)

**场景**: 创建一个提供高级编辑工具的插件

**步骤**:

1. **创建插件目录**:

```
plugins/
└── tool/
    └── advanced-edit/
        ├── __init__.py
        ├── plugin.py       # 插件主类
        ├── tools.py        # 工具实现
        └── plugin.toml     # 元数据配置
```

2. **实现插件类**:

```python
# plugins/tool/advanced-edit/plugin.py
from pyagentforge.plugin import Plugin, PluginMetadata, PluginType
from .tools import SmartEditTool, MultiFileEditTool

class AdvancedEditPlugin(Plugin):
    """高级编辑工具插件"""

    metadata = PluginMetadata(
        id="tool.advanced-edit",
        name="Advanced Edit Tools",
        version="1.0.0",
        type=PluginType.TOOL,
        description="提供智能编辑、多文件编辑等高级功能",
        author="PyAgentForge Team",
        dependencies=["core.base-tools"],
        provides=["capability.advanced-edit"],
    )

    async def on_plugin_activate(self) -> None:
        """插件激活"""
        self.context.logger.info("Advanced Edit Tools activated")

    def get_tools(self):
        """返回插件提供的工具"""
        return [
            SmartEditTool(),
            MultiFileEditTool(),
        ]
```

3. **配置插件**:

```toml
# plugins/tool/advanced-edit/plugin.toml
[plugin]
id = "tool.advanced-edit"
name = "Advanced Edit Tools"
version = "1.0.0"
type = "tool"

[dependencies]
required = ["core.base-tools"]

[config]
enable_smart_edit = true
enable_multifile = true
```

---

### 4.3 新增 LLM Provider

**场景**: 添加 Google Gemini 支持

**步骤**:

1. **实现 Provider 类**:

```python
# providers/google_provider.py
import google.generativeai as genai
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.message import ProviderResponse

class GoogleProvider(BaseProvider):
    """Google Gemini Provider"""

    def __init__(self, api_key: str, model: str = "gemini-pro"):
        genai.configure(api_key=api_key)
        self.model = model
        self.client = genai.GenerativeModel(model)

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        """调用 Gemini API"""
        # 转换消息格式
        gemini_messages = self._convert_messages(messages)

        # 调用 API
        response = await self.client.generate_content_async(
            gemini_messages,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
            tools=self._convert_tools(tools) if tools else None,
        )

        # 解析响应
        return self._parse_response(response)

    def _convert_messages(self, messages: list[dict]) -> list:
        # 实现省略
        pass

    def _convert_tools(self, tools: list[dict]) -> list:
        # 实现省略
        pass

    def _parse_response(self, response) -> ProviderResponse:
        # 实现省略
        pass
```

2. **注册到工厂**:

```python
# providers/factory.py
from .google_provider import GoogleProvider

SUPPORTED_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,  # 新增
}

def create_provider(
    provider_type: str,
    api_key: str,
    model: str,
) -> BaseProvider:
    """创建 Provider 实例"""
    provider_class = SUPPORTED_PROVIDERS.get(provider_type)
    if not provider_class:
        raise ValueError(f"Unsupported provider: {provider_type}")
    return provider_class(api_key=api_key, model=model)
```

---

## 五、工具系统分层规范

### 5.1 三层工具架构

```
┌─────────────────────────────────────────┐
│   Core Tools (kernel/core_tools/)       │
│   - 最小工具集                           │
│   - Agent 基本能力                       │
│   - 6 个工具: Bash/Read/Write/Edit/     │
│               Glob/Grep                 │
│   - 必须随 Engine 自动注册               │
└─────────────────────────────────────────┘
           ↓ 不依赖
┌─────────────────────────────────────────┐
│   Builtin Tools (tools/builtin/)        │
│   - 扩展工具集                           │
│   - 高级功能: Todo/WebSearch/Task/      │
│               Plan/CodeSearch/...       │
│   - 按需注册                             │
└─────────────────────────────────────────┘
           ↓ 不依赖
┌─────────────────────────────────────────┐
│   Plugin Tools (plugins/tool/)          │
│   - 专项工具包                           │
│   - 通过插件系统加载                      │
│   - 可插拔                               │
└─────────────────────────────────────────┘
```

### 5.2 工具归属判定

**问题**: 新工具应该放在哪一层？

**判定流程**:

```
新工具
  │
  ├─ 是否 Agent 执行最小必需？
  │   ├─ Yes → kernel/core_tools/
  │   └─ No → 继续
  │
  ├─ 是否通用功能（非领域特定）？
  │   ├─ Yes → tools/builtin/
  │   └─ No → plugins/tool/
  │
  └─ 是否需要额外依赖？
      ├─ Yes (轻量) → tools/builtin/
      └─ Yes (重量/可选) → plugins/tool/
```

**示例**:

| 工具 | 归属 | 理由 |
|------|------|------|
| Bash | Core Tools | Agent 最小必需 |
| Read | Core Tools | Agent 最小必需 |
| TodoWrite | Builtin Tools | 通用辅助工具 |
| WebSearch | Builtin Tools | 通用功能 |
| LSP Integration | Plugin Tools | 需要额外依赖，专业领域 |
| GitHub API | Plugin Tools | 特定平台集成 |

---

## 六、配置系统规范

### 6.1 配置文件格式

**插件配置** (`config/plugin_config.py`):

```python
from pydantic import BaseModel
from typing import Literal

class PluginConfig(BaseModel):
    """插件系统配置"""
    enabled_plugins: list[str] = []
    plugin_dirs: list[str] = ["plugins"]
    auto_discover: bool = True
    load_order: list[str] = []  # 手动指定加载顺序

    class Config:
        extra = "allow"  # 允许额外字段
```

**使用示例**:

```python
from pyagentforge.config.plugin_config import PluginConfig

config = PluginConfig(
    enabled_plugins=[
        "tool.advanced-edit",
        "protocol.mcp-server",
    ],
    auto_discover=False,
)
```

### 6.2 环境变量

**.env 文件**:

```bash
# LLM Providers
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
GOOGLE_API_KEY=xxx

# Agent Config
AGENT_MAX_TOKENS=4096
AGENT_TEMPERATURE=1.0
AGENT_MAX_ITERATIONS=100

# Plugin System
PLUGIN_AUTO_DISCOVER=true
PLUGIN_ENABLED=tool.advanced-edit,protocol.mcp

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=structured
```

**加载配置**:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str | None = None
    agent_max_tokens: int = 4096

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

---

## 七、测试规范

### 7.1 单元测试

**位置**: `tests/`

**命名**: `test_<module>_<function>.py`

**示例**:

```python
# tests/tools/test_format.py
import pytest
from pyagentforge.tools.builtin.format import FormatTool

@pytest.mark.asyncio
async def test_format_python_file():
    """测试 Python 文件格式化"""
    tool = FormatTool()
    result = await tool.execute(
        file_path="test_data/sample.py",
        formatter="black",
    )
    assert "Successfully formatted" in result

@pytest.mark.asyncio
async def test_format_invalid_file():
    """测试无效文件"""
    tool = FormatTool()
    result = await tool.execute(
        file_path="/nonexistent/file.py",
    )
    assert result.startswith("Error:")
```

### 7.2 集成测试

```python
# tests/integration/test_engine_with_tools.py
import pytest
from pyagentforge import AgentEngine, ToolRegistry
from pyagentforge.providers import AnthropicProvider
from pyagentforge.kernel.core_tools import register_core_tools

@pytest.mark.asyncio
async def test_engine_with_custom_tool():
    """测试 Engine 加载自定义工具"""
    # Setup
    provider = AnthropicProvider(api_key="test-key")
    registry = ToolRegistry()
    register_core_tools(registry)
    registry.register(FormatTool())  # 自定义工具

    engine = AgentEngine(
        provider=provider,
        tool_registry=registry,
    )

    # Test
    result = await engine.run("Format the file /tmp/test.py")
    assert result is not None
```

---

## 八、性能与安全规范

### 8.1 性能优化

**异步并发**:

```python
# ✅ 正确 - 并发执行
async def execute_batch(self, commands: list[str]) -> list[str]:
    tasks = [self._run_command(cmd) for cmd in commands]
    return await asyncio.gather(*tasks)

# ❌ 错误 - 顺序执行
async def execute_batch(self, commands: list[str]) -> list[str]:
    results = []
    for cmd in commands:
        results.append(await self._run_command(cmd))
    return results
```

**上下文管理**:

```python
# 使用 ContextManager 的截断功能
if len(self.context) > self.context.max_messages * 0.8:
    self.context.truncate()
```

### 8.2 安全规范

**路径检查**:

```python
from pyagentforge.tools.permission import PermissionChecker, PermissionResult

class ReadTool(BaseTool):
    def __init__(self, permission_checker: PermissionChecker | None = None):
        self.permission_checker = permission_checker

    async def execute(self, file_path: str) -> str:
        # 检查路径权限
        if self.permission_checker:
            result = self.permission_checker.check_path(file_path)
            if result == PermissionResult.DENY:
                return f"Error: Access to '{file_path}' is denied"

        # 继续执行
        ...
```

**敏感信息过滤**:

```python
# ❌ 不要在日志中记录敏感信息
logger.info(f"API Key: {api_key}")  # 错误！

# ✅ 使用脱敏
logger.info(f"API Key: {mask_sensitive(api_key)}")  # sk-ant-***xxx
```

---

## 九、迁移与兼容性

### 9.1 v1.x → v2.0 迁移

**旧代码 (v1.x)**:

```python
from pyagentforge.core.engine import AgentEngine  # 旧导入
from pyagentforge.tools.registry import ToolRegistry
```

**新代码 (v2.0)**:

```python
from pyagentforge.kernel import AgentEngine  # 新导入
from pyagentforge.kernel import ToolRegistry
```

**兼容性处理**:

```python
# __init__.py 已处理向后兼容
# 旧导入会触发 DeprecationWarning，但仍然可用
```

### 9.2 弃用策略

1. **标记弃用**:
```python
import warnings

warnings.warn(
    "Importing from pyagentforge.core is deprecated. "
    "Use pyagentforge.kernel instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

2. **保留一个主版本**
3. **下个主版本移除**

---

## 十、开发工作流

### 10.1 功能开发流程

```
1. 创建分支
   git checkout -b feature/my-new-tool

2. 实现功能
   - 编写代码 (遵循规范)
   - 添加类型注解
   - 添加文档字符串

3. 编写测试
   - 单元测试
   - 集成测试

4. 代码检查
   ruff check .
   mypy pyagentforge

5. 运行测试
   pytest tests/

6. 提交代码
   git add .
   git commit -m "feat: add format tool for code formatting"

7. 推送分支
   git push origin feature/my-new-tool
```

### 10.2 代码审查清单

- [ ] 遵循类型注解规范
- [ ] 使用 async/await
- [ ] 错误处理返回 `Error: ...` 格式
- [ ] 添加结构化日志
- [ ] 更新 `__all__` 导出
- [ ] 添加单元测试
- [ ] 更新相关文档
- [ ] 通过 ruff 和 mypy 检查

---

## 十一、常见问题

### Q1: 何时使用 Plugin vs 直接注册 Tool？

**Plugin**:
- 需要生命周期管理
- 需要钩子拦截
- 需要依赖管理
- 提供多个相关工具

**直接注册 Tool**:
- 简单工具
- 无需插件上下文
- 快速原型

### Q2: 如何处理工具依赖？

**轻量依赖** (pip install):
```toml
# pyproject.toml
dependencies = [
    "anthropic>=0.18.0",
    "your-light-dependency>=1.0.0",
]
```

**重量依赖** (可选):
```toml
[project.optional-dependencies]
advanced = ["heavy-dependency>=2.0.0"]
```

### Q3: 如何调试工具执行？

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 或使用结构化日志
from pyagentforge.utils.logging import get_logger
logger = get_logger(__name__)
logger.setLevel("DEBUG")
```

---

## 十二、参考资源

### 12.1 代码示例

| 资源 | 位置 |
|------|------|
| 基础示例 | `examples/basic_usage.py` |
| 高级功能 | `examples/advanced_features_demo.py` |
| 插件示例 | `plugins/tool/*/plugin.py` |
| 工具示例 | `tools/builtin/*.py` |

### 12.2 架构文档

- [OpenClaw 功能说明书](../../Docs/OpenClaw/00-系统总览.md)
- [三方对比报告](../../Docs/PyAgentForge/三方对比报告-OpenClaw-PyAgentForge-OpenCodeServer.md)
- [PyAgentForge vs OpenCode](../../Docs/PyAgentForge/PyAgentForge-vs-OpenCodeServer-2026-02-16-完整对比.md)

### 12.3 外部参考

- [Anthropic API Docs](https://docs.anthropic.com/)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Pydantic Docs](https://docs.pydantic.dev/)

---

## 附录 A: 工具开发模板

```python
"""
{Tool Name} 工具

{Brief description}
"""

import asyncio
from pathlib import Path
from typing import Any

from pyagentforge.kernel.base_tool import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class {ToolName}Tool(BaseTool):
    """{Tool Name} 工具 - {Short description}"""

    name = "{tool_name}"
    description = """{Detailed description for LLM}.

Key behaviors:
- Behavior 1
- Behavior 2

Usage: {Usage examples}
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter 1 description",
            },
            "param2": {
                "type": "integer",
                "description": "Parameter 2 description",
                "default": 100,
            },
        },
        "required": ["param1"],
    }
    timeout = 60
    risk_level = "low"  # low/medium/high

    def __init__(self, working_dir: str | None = None) -> None:
        """Initialize tool"""
        self.working_dir = working_dir

    async def execute(
        self,
        param1: str,
        param2: int = 100,
    ) -> str:
        """Execute tool"""
        logger.info(
            "Executing {tool_name}",
            extra_data={"param1": param1, "param2": param2},
        )

        try:
            # Main logic here
            result = await self._do_work(param1, param2)

            logger.info(
                "{Tool name} completed",
                extra_data={"result_length": len(result)},
            )

            return result

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(
                "{Tool name} failed",
                extra_data={"error": str(e)},
            )
            return error_msg

    async def _do_work(self, param1: str, param2: int) -> str:
        """Main implementation"""
        # Your implementation here
        return "Success"
```

---

## 附录 B: 插件开发模板

```python
"""
{Plugin Name} Plugin

{Brief description}
"""

from pyagentforge.plugin import (
    Plugin,
    PluginMetadata,
    PluginType,
)
from pyagentforge.kernel.base_tool import BaseTool
from .tools import Tool1, Tool2


class {PluginName}Plugin(Plugin):
    """{Plugin Name} Plugin - {Short description}"""

    metadata = PluginMetadata(
        id="{type}.{plugin-name}",
        name="{Plugin Display Name}",
        version="1.0.0",
        type=PluginType.{TYPE},  # TOOL/PROTOCOL/INTERFACE/...
        description="{Detailed description}",
        author="{Author Name}",
        dependencies=[  # Optional
            "core.base-tools",
        ],
        provides=[  # Optional
            "capability.{capability-name}",
        ],
    )

    async def on_plugin_activate(self) -> None:
        """Called when plugin is activated"""
        self.context.logger.info(f"{self.metadata.name} activated")

        # Optional: Initialize resources
        await self._setup()

    async def on_plugin_deactivate(self) -> None:
        """Called when plugin is deactivated"""
        self.context.logger.info(f"{self.metadata.name} deactivated")

        # Optional: Cleanup resources
        await self._cleanup()

    def get_tools(self) -> list[BaseTool]:
        """Return tools provided by this plugin"""
        return [
            Tool1(),
            Tool2(),
        ]

    # Optional hooks
    async def on_before_tool_call(self, tool_use) -> Any:
        """Intercept tool calls"""
        if tool_use.name == "bash":
            self.context.logger.info(
                f"Bash command: {tool_use.input.get('command')}"
            )
        return None  # Don't intercept

    async def _setup(self) -> None:
        """Initialize plugin resources"""
        pass

    async def _cleanup(self) -> None:
        """Cleanup plugin resources"""
        pass
```

---

**文档结束**

> 本规范将随项目演进持续更新。
> 如有疑问，请参考现有代码实现或提交 Issue。