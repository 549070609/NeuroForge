# PyAgentForge 插件系统 API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本文档详细说明 PyAgentForge v2.0 的插件系统，包括插件架构、基类、管理器和钩子系统。

---

## 目录

- [1. 插件架构概述](#1-插件架构概述)
- [2. PluginType - 插件类型枚举](#2-plugintype---插件类型枚举)
- [3. PluginMetadata - 插件元数据](#3-pluginmetadata---插件元数据)
- [4. PluginContext - 插件上下文](#4-plugincontext---插件上下文)
- [5. Plugin - 插件基类](#5-plugin---插件基类)
- [6. PluginManager - 插件管理器](#6-pluginmanager---插件管理器)
- [7. 钩子系统](#7-钩子系统)
- [8. 插件生命周期](#8-插件生命周期)
- [9. 开发自定义插件](#9-开发自定义插件)

---

## 1. 插件架构概述

PyAgentForge v2.0 采用 **Kernel (最小核心) + Plugin System (扩展能力)** 的架构设计。

### 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                     Plugins Layer                           │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ Interface  │ │  Protocol  │ │   Tools    │ │  Skill   │ │
│  │ (REST API) │ │ (MCP, LSP) │ │ (Extended) │ │ (Loader) │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │  Provider  │ │ Middleware │ │Integration │              │
│  │ (LLM API)  │ │(Compact等) │ │(Events等)  │              │
│  └────────────┘ └────────────┘ └────────────┘              │
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

### 插件类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `INTERFACE` | 接口插件 | REST API, WebSocket, CLI |
| `PROTOCOL` | 协议插件 | MCP Server/Client, LSP |
| `TOOL` | 工具插件 | Web 工具, 代码工具 |
| `SKILL` | 技能插件 | 技能加载器 |
| `PROVIDER` | Provider 插件 | OpenAI, Anthropic, Google |
| `MIDDLEWARE` | 中间件插件 | 上下文压缩, 故障转移, 思考级别 |
| `INTEGRATION` | 集成插件 | 事件系统, 持久化, 上下文感知 |

---

## 2. PluginType - 插件类型枚举

**位置:** `pyagentforge.plugin.base.PluginType`

```python
class PluginType(str, Enum):
    """插件类型"""
    INTERFACE = "interface"      # API, CLI, WebSocket
    PROTOCOL = "protocol"        # MCP, LSP
    TOOL = "tool"               # 扩展工具集
    SKILL = "skill"             # 知识加载器
    PROVIDER = "provider"       # LLM提供商
    MIDDLEWARE = "middleware"   # 中间件
    INTEGRATION = "integration" # 集成插件
```

---

## 3. PluginMetadata - 插件元数据

**位置:** `pyagentforge.plugin.base.PluginMetadata`

定义插件的基本信息。

```python
@dataclass
class PluginMetadata:
    """插件元数据"""
    id: str                              # 唯一标识，如 "interface.rest-api"
    name: str                            # 显示名称
    version: str                         # 语义版本
    type: PluginType                     # 插件类型
    description: str = ""                # 描述
    author: str = ""                     # 作者
    dependencies: List[str] = field(default_factory=list)          # 必需依赖
    optional_dependencies: List[str] = field(default_factory=list) # 可选依赖
    provides: List[str] = field(default_factory=list)              # 提供的能力标识
    conflicts: List[str] = field(default_factory=list)             # 冲突的插件ID
    priority: int = 0                    # 加载优先级（越高越先加载）
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `str` | **必需** | 唯一标识，如 "interface.rest-api" |
| `name` | `str` | **必需** | 显示名称 |
| `version` | `str` | **必需** | 语义版本 (semver) |
| `type` | `PluginType` | **必需** | 插件类型 |
| `description` | `str` | `""` | 描述 |
| `author` | `str` | `""` | 作者 |
| `dependencies` | `List[str]` | `[]` | 必需依赖的插件 ID |
| `optional_dependencies` | `List[str]` | `[]` | 可选依赖的插件 ID |
| `provides` | `List[str]` | `[]` | 提供的能力标识 |
| `conflicts` | `List[str]` | `[]` | 冲突的插件 ID |
| `priority` | `int` | `0` | 加载优先级 (越高越先) |

---

## 4. PluginContext - 插件上下文

**位置:** `pyagentforge.plugin.base.PluginContext`

提供插件访问系统资源的能力。

```python
@dataclass
class PluginContext:
    """插件上下文 - 提供插件访问系统资源的能力"""
    engine: Any  # AgentEngine
    config: dict  # 插件配置
    logger: Any  # 日志器
```

### 方法

#### `get_tool_registry()`

```python
def get_tool_registry(self) -> ToolRegistry | None
```

获取工具注册表。

**返回值:** `ToolRegistry | None` - 工具注册表实例

---

## 5. Plugin - 插件基类

**位置:** `pyagentforge.plugin.base.Plugin`

所有插件的抽象基类。

### 类定义

```python
class Plugin(ABC):
    """插件基类"""

    metadata: PluginMetadata

    def __init__(self):
        self._context: Optional[PluginContext] = None
        self._activated = False
```

---

### 属性

#### `context`

```python
@property
def context(self) -> PluginContext
```

获取插件上下文。

**异常:** `RuntimeError` - 如果上下文未设置

---

#### `is_activated`

```python
@property
def is_activated(self) -> bool
```

插件是否已激活。

---

### 生命周期方法

#### `on_plugin_load()`

```python
async def on_plugin_load(self, context: PluginContext) -> None
```

插件加载时调用。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `context` | `PluginContext` | 插件上下文 |

---

#### `on_plugin_activate()`

```python
async def on_plugin_activate(self) -> None
```

插件激活时调用。

---

#### `on_plugin_deactivate()`

```python
async def on_plugin_deactivate(self) -> None
```

插件停用时调用。

---

### 钩子方法

子类可选重写以下钩子方法:

```python
async def on_engine_init(self, engine) -> None:
    """引擎初始化时"""
    pass

async def on_engine_start(self, engine) -> None:
    """引擎启动时"""
    pass

async def on_engine_stop(self, engine) -> None:
    """引擎停止时"""
    pass

async def on_before_llm_call(self, messages: list) -> Optional[list]:
    """LLM调用前 - 返回修改后的消息或None"""
    return None

async def on_after_llm_call(self, response) -> Optional[Any]:
    """LLM调用后 - 返回修改后的响应或None"""
    return None

async def on_before_tool_call(self, tool_use) -> Optional[Any]:
    """工具执行前 - 返回替换的工具调用或None"""
    return None

async def on_after_tool_call(self, result: str) -> Optional[str]:
    """工具执行后 - 返回修改后的结果或None"""
    return None

async def on_context_overflow(self, token_count: int) -> bool:
    """上下文溢出时 - 返回True表示已处理"""
    return False

async def on_task_complete(self, result: str) -> None:
    """任务完成时"""
    pass

async def on_skill_load(self, skill) -> None:
    """技能加载时"""
    pass

async def on_subagent_spawn(self, subagent) -> None:
    """子Agent创建时"""
    pass
```

---

### 资源提供方法

#### `get_tools()`

```python
def get_tools(self) -> List[BaseTool]
```

返回插件提供的工具。

**返回值:** `List[BaseTool]` - 工具实例列表

---

#### `get_providers()`

```python
def get_providers(self) -> List[Type[BaseProvider]]
```

返回插件提供的 Provider 类。

**返回值:** `List[Type[BaseProvider]]` - Provider 类列表

---

#### `get_hooks()`

```python
def get_hooks(self) -> dict[str, Callable]
```

返回插件实现的钩子映射。

**返回值:** `dict[str, Callable]` - 钩子名称到回调函数的映射

---

## 6. PluginManager - 插件管理器

**位置:** `pyagentforge.plugin.manager.PluginManager`

协调插件的加载、激活和管理。

### 构造函数

```python
def __init__(self, engine: Any = None) -> None
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `engine` | `Any` | `None` | AgentEngine 实例 (可选) |

---

### 方法

#### `initialize()`

```python
async def initialize(
    self,
    config: Dict[str, Any],
    plugin_dirs: List[str] | None = None,
) -> None
```

初始化插件系统。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `Dict[str, Any]` | 配置字典 |
| `plugin_dirs` | `List[str] \| None` | 额外的插件搜索目录 |

**配置结构:**

```python
config = {
    "preset": "standard",  # minimal, standard, full
    "enabled": ["tools.web_tools"],
    "disabled": ["protocol.lsp"],
    "plugin_dirs": ["plugins"],
    "config": {
        "middleware.compaction": {
            "enabled": True,
            "threshold": 0.8,
        }
    }
}
```

---

#### `activate_plugin()`

```python
async def activate_plugin(self, plugin_id: str) -> bool
```

激活插件。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `plugin_id` | `str` | 插件 ID |

**返回值:** `bool` - 是否激活成功

---

#### `deactivate_plugin()`

```python
async def deactivate_plugin(self, plugin_id: str) -> bool
```

停用插件。

**返回值:** `bool` - 是否停用成功

---

#### `emit_hook()`

```python
async def emit_hook(
    self,
    hook_type: str | HookType,
    *args,
    **kwargs,
) -> List[Any]
```

触发钩子事件。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `hook_type` | `str \| HookType` | 钩子类型 |
| `*args` | `Any` | 位置参数 |
| `**kwargs` | `Any` | 关键字参数 |

**返回值:** `List[Any]` - 钩子返回值列表

---

#### `get_tools_from_plugins()`

```python
def get_tools_from_plugins(self) -> list
```

获取所有已激活插件提供的工具。

---

#### `get_summary()`

```python
def get_summary(self) -> Dict[str, Any]
```

获取插件系统摘要。

---

### 预设配置

```python
presets = {
    "minimal": set(),
    "standard": {
        "tools.code_tools",
        "tools.file_tools",
        "middleware.compaction",
        "integration.events",
    },
    "full": {
        "interface.rest_api",
        "protocol.mcp_server",
        "protocol.mcp_client",
        "protocol.lsp",
        "tools.web_tools",
        "tools.code_tools",
        "tools.file_tools",
        "tools.interact_tools",
        "middleware.compaction",
        "middleware.failover",
        "middleware.thinking",
        "middleware.rate_limit",
        "integration.persistence",
        "integration.events",
        "integration.context_aware",
    },
}
```

---

## 7. 钩子系统

### 7.1 HookType - 钩子类型

**位置:** `pyagentforge.plugin.hooks.HookType`

```python
class HookType(str, Enum):
    """钩子类型"""

    # 生命周期钩子
    ON_PLUGIN_LOAD = "on_plugin_load"
    ON_PLUGIN_ACTIVATE = "on_plugin_activate"
    ON_PLUGIN_DEACTIVATE = "on_plugin_deactivate"

    # 引擎钩子
    ON_ENGINE_INIT = "on_engine_init"
    ON_ENGINE_START = "on_engine_start"
    ON_ENGINE_STOP = "on_engine_stop"

    # 执行钩子
    ON_BEFORE_LLM_CALL = "on_before_llm_call"
    ON_AFTER_LLM_CALL = "on_after_llm_call"
    ON_BEFORE_TOOL_CALL = "on_before_tool_call"
    ON_AFTER_TOOL_CALL = "on_after_tool_call"

    # 上下文钩子
    ON_CONTEXT_OVERFLOW = "on_context_overflow"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_SKILL_LOAD = "on_skill_load"
    ON_SUBAGENT_SPAWN = "on_subagent_spawn"
```

---

### 7.2 HookRegistry - 钩子注册表

**位置:** `pyagentforge.plugin.hooks.HookRegistry`

管理所有插件的钩子注册和执行。

#### `register()`

```python
def register(
    self,
    hook_type: HookType,
    plugin: Any,
    callback: Callable,
) -> None
```

注册钩子。

---

#### `unregister()`

```python
def unregister(self, hook_type: HookType, plugin: Any) -> None
```

注销钩子。

---

#### `unregister_all()`

```python
def unregister_all(self, plugin: Any) -> None
```

注销插件的所有钩子。

---

#### `emit()`

```python
async def emit(
    self,
    hook_type: HookType,
    *args,
    **kwargs,
) -> List[Any]
```

触发钩子事件。

**返回值:** `List[Any]` - 所有非 None 的返回值列表

---

## 8. 插件生命周期

```
┌────────────────┐
│    Created     │
└───────┬────────┘
        │
        ▼
┌────────────────┐   on_plugin_load(context)
│     Loaded     │ ◄─────────────────────────
└───────┬────────┘
        │
        ▼
┌────────────────┐   on_plugin_activate()
│   Activated    │ ◄────────────────────────
└───────┬────────┘
        │
        │  ┌─────────────────────────────────┐
        │  │ 钩子执行 (运行时)                 │
        │  │ - on_engine_init                │
        │  │ - on_before_llm_call            │
        │  │ - on_after_llm_call             │
        │  │ - on_before_tool_call           │
        │  │ - on_after_tool_call            │
        │  │ - ...                           │
        │  └─────────────────────────────────┘
        │
        ▼
┌────────────────┐   on_plugin_deactivate()
│  Deactivated   │ ◄─────────────────────────
└────────────────┘
```

---

## 9. 开发自定义插件

### 9.1 基本插件结构

```python
# plugins/my_plugin/PLUGIN.py

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext
from pyagentforge.kernel.base_tool import BaseTool
from typing import List, Type

class MyCustomPlugin(Plugin):
    """自定义插件示例"""

    metadata = PluginMetadata(
        id="tools.my_custom",
        name="My Custom Plugin",
        version="1.0.0",
        type=PluginType.TOOL,
        description="提供自定义功能",
        author="Your Name",
        dependencies=[],
        priority=10,
    )

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时"""
        await super().on_plugin_load(context)
        context.logger.info(f"Loading {self.metadata.name}")

    async def on_plugin_activate(self) -> None:
        """插件激活时"""
        await super().on_plugin_activate()
        self.context.logger.info(f"Activating {self.metadata.name}")

    async def on_plugin_deactivate(self) -> None:
        """插件停用时"""
        self.context.logger.info(f"Deactivating {self.metadata.name}")
        await super().on_plugin_deactivate()

    def get_tools(self) -> List[BaseTool]:
        """返回插件提供的工具"""
        return [
            MyCustomTool(),
        ]
```

---

### 9.2 中间件插件示例

```python
# plugins/middleware/my_middleware/PLUGIN.py

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext
from typing import Optional, Any

class LoggingMiddlewarePlugin(Plugin):
    """日志中间件插件"""

    metadata = PluginMetadata(
        id="middleware.logging",
        name="Logging Middleware",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="增强日志记录",
    )

    async def on_before_llm_call(self, messages: list) -> Optional[list]:
        """LLM 调用前记录消息"""
        self.context.logger.info(
            "LLM call starting",
            extra_data={"message_count": len(messages)}
        )
        return None  # 不修改消息

    async def on_after_llm_call(self, response) -> Optional[Any]:
        """LLM 调用后记录响应"""
        self.context.logger.info(
            "LLM call completed",
            extra_data={
                "stop_reason": response.stop_reason,
                "usage": response.usage,
            }
        )
        return None  # 不修改响应

    async def on_before_tool_call(self, tool_use) -> Optional[Any]:
        """工具执行前记录"""
        self.context.logger.info(
            "Tool call starting",
            extra_data={
                "tool_name": tool_use.name,
                "tool_id": tool_use.id,
            }
        )
        return None

    async def on_after_tool_call(self, result: str) -> Optional[str]:
        """工具执行后记录"""
        self.context.logger.info(
            "Tool call completed",
            extra_data={"result_length": len(result)}
        )
        return None  # 不修改结果
```

---

### 9.3 Provider 插件示例

```python
# plugins/providers/my_provider/PLUGIN.py

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_provider import BaseProvider
from typing import List, Type

class MyProviderPlugin(Plugin):
    """自定义 Provider 插件"""

    metadata = PluginMetadata(
        id="providers.my_provider",
        name="My Custom Provider",
        version="1.0.0",
        type=PluginType.PROVIDER,
        description="自定义 LLM Provider",
        provides=["provider.my_llm"],
    )

    def get_providers(self) -> List[Type[BaseProvider]]:
        """返回 Provider 类"""
        return [MyCustomProvider]


class MyCustomProvider(BaseProvider):
    """自定义 Provider 实现"""

    def __init__(self, api_key: str, model: str = "my-model-v1", **kwargs):
        super().__init__(model, **kwargs)
        self.api_key = api_key

    async def create_message(
        self,
        system: str,
        messages: list,
        tools: list,
        **kwargs,
    ):
        """实现消息创建"""
        # 调用你的 LLM API
        # ...
        pass

    async def count_tokens(self, messages: list) -> int:
        """实现 Token 计数"""
        # 使用对应的 tokenizer
        pass
```

---

### 9.4 插件目录结构

```
plugins/
├── my_plugin/
│   ├── PLUGIN.py           # 插件入口文件
│   ├── __init__.py
│   ├── tools.py            # 插件提供的工具
│   └── README.md           # 插件文档
├── middleware/
│   ├── logging/
│   │   └── PLUGIN.py
│   └── rate_limit/
│       └── PLUGIN.py
└── providers/
    └── my_provider/
        └── PLUGIN.py
```

---

### 9.5 使用插件配置

```python
# config.yaml
preset: standard
enabled:
  - tools.my_custom
  - middleware.logging
disabled:
  - protocol.lsp
plugin_dirs:
  - plugins
config:
  middleware.logging:
    level: DEBUG
  tools.my_custom:
    option1: value1
```

```python
from pyagentforge.config.plugin_config import PluginConfig
from pyagentforge.plugin.manager import PluginManager

# 加载配置
config = PluginConfig.from_yaml("config.yaml")

# 初始化管理器
manager = PluginManager(engine)
await manager.initialize(config.to_dict())

# 手动激活插件
await manager.activate_plugin("tools.my_custom")

# 触发钩子
results = await manager.emit_hook("on_before_llm_call", messages)
```

---

## 相关文档

- [核心 API 文档](./01-core-api.md)
- [Provider API 文档](./02-providers-api.md)
- [工具系统 API 文档](./03-tools-api.md)
- [命令与技能系统 API 文档](./04-commands-skills-api.md)
- [配置 API 文档](./06-configuration-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 初始版本，完整的插件系统架构 |

---

*本文档由 Claude Code 自动生成*
