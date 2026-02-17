# PyAgentForge 核心 API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17
> **架构:** Kernel (最小核心) + Plugin System (扩展能力)

本文档涵盖 PyAgentForge v2.0 的核心 API，包括 AgentEngine、ContextManager、ToolExecutor 等核心组件。

---

## 目录

- [1. AgentEngine - Agent 执行引擎](#1-agentengine---agent-执行引擎)
- [2. ContextManager - 上下文管理器](#2-contextmanager---上下文管理器)
- [3. ToolExecutor - 工具执行器](#3-toolexecutor---工具执行器)
- [4. ToolRegistry - 工具注册表](#4-toolregistry---工具注册表)
- [5. 消息类型](#5-消息类型)
- [6. BaseTool - 工具基类](#6-basetool---工具基类)
- [7. BaseProvider - Provider 基类](#7-baseprovider---provider-基类)
- [8. PermissionChecker - 权限检查器](#8-permissionchecker---权限检查器)
- [9. 工厂函数](#9-工厂函数)

---

## 1. AgentEngine - Agent 执行引擎

Agent 执行引擎是 PyAgentForge 的核心组件，实现了 Agent 的主循环逻辑。

### 1.1 AgentConfig

**位置:** `pyagentforge.kernel.engine.AgentConfig`

Agent 配置数据类。

```python
@dataclass
class AgentConfig:
    """Agent 配置"""
    system_prompt: str = "You are a helpful AI assistant."
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 100
    permission_checker: Any = None
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `system_prompt` | `str` | `"You are a helpful AI assistant."` | 系统提示词 |
| `max_tokens` | `int` | `4096` | 最大生成 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 (0.0-2.0) |
| `max_iterations` | `int` | `100` | 最大迭代次数 |
| `permission_checker` | `Any` | `None` | 权限检查器实例 |

---

### 1.2 AgentEngine

**位置:** `pyagentforge.kernel.engine.AgentEngine`

核心执行引擎，实现 Agent 的主循环。

#### 构造函数

```python
def __init__(
    self,
    provider: BaseProvider,
    tool_registry: ToolRegistry,
    config: AgentConfig | None = None,
    context: ContextManager | None = None,
    ask_callback: AskCallback | None = None,
    plugin_manager: Any = None,
) -> None
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | `BaseProvider` | **必需** | LLM 提供商实例 |
| `tool_registry` | `ToolRegistry` | **必需** | 工具注册表 |
| `config` | `AgentConfig \| None` | `None` | Agent 配置 |
| `context` | `ContextManager \| None` | `None` | 上下文管理器 |
| `ask_callback` | `AskCallback \| None` | `None` | 用户确认回调函数 |
| `plugin_manager` | `Any` | `None` | 插件管理器 |

**AskCallback 类型定义:**
```python
AskCallback = Callable[[str, dict[str, Any]], bool]
```

---

#### 属性

##### `session_id`

```python
@property
def session_id(self) -> str
```

获取当前会话的唯一标识符。

**返回值:** `str` - UUID 格式的会话 ID

---

#### 方法

##### `run()`

```python
async def run(self, prompt: str) -> str
```

运行 Agent，执行用户请求。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str` | 用户输入的提示 |

**返回值:** `str` - Agent 的响应文本

**异常:** 无显式异常，错误通过返回值传达

**示例:**

```python
from pyagentforge import AgentEngine, ToolRegistry, AnthropicProvider

# 创建 Provider
provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")

# 创建工具注册表
tool_registry = ToolRegistry()

# 创建引擎
engine = AgentEngine(
    provider=provider,
    tool_registry=tool_registry,
)

# 运行 Agent
response = await engine.run("Hello, how are you?")
print(response)
```

---

##### `reset()`

```python
def reset(self) -> None
```

重置 Agent 状态，清空对话历史。

**返回值:** `None`

---

##### `get_context_summary()`

```python
def get_context_summary(self) -> dict[str, Any]
```

获取上下文摘要信息。

**返回值:** `dict[str, Any]` - 包含会话信息的字典

**返回结构:**

```python
{
    "session_id": str,           # 会话 ID
    "message_count": int,        # 消息数量
    "loaded_skills": list[str],  # 已加载的技能
    "config": {
        "model": str,            # 模型名称
        "max_tokens": int,       # 最大 Token 数
    }
}
```

---

## 2. ContextManager - 上下文管理器

**位置:** `pyagentforge.kernel.context.ContextManager`

管理 Agent 的对话历史和上下文。

### 构造函数

```python
def __init__(
    self,
    max_messages: int = 100,
    system_prompt: str | None = None,
)
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_messages` | `int` | `100` | 最大消息数量 |
| `system_prompt` | `str \| None` | `None` | 系统提示词 |

---

### 方法

#### `add_user_message()`

```python
def add_user_message(self, content: str) -> None
```

添加用户消息到历史。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 消息内容 |

---

#### `add_assistant_message()`

```python
def add_assistant_message(
    self,
    content: list[TextBlock | ToolUseBlock],
) -> None
```

添加助手消息到历史。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `content` | `list[TextBlock \| ToolUseBlock]` | 消息内容块列表 |

---

#### `add_assistant_text()`

```python
def add_assistant_text(self, text: str) -> None
```

添加助手文本消息。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 文本内容 |

---

#### `add_tool_result()`

```python
def add_tool_result(
    self,
    tool_use_id: str,
    result: str,
    is_error: bool = False,
) -> None
```

添加工具执行结果。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tool_use_id` | `str` | **必需** | 工具调用 ID |
| `result` | `str` | **必需** | 工具返回结果 |
| `is_error` | `bool` | `False` | 是否为错误结果 |

---

#### `get_messages_for_api()`

```python
def get_messages_for_api(self) -> list[dict[str, Any]]
```

获取用于 API 调用的消息列表。

**返回值:** `list[dict[str, Any]]` - API 格式的消息列表

---

#### `truncate()`

```python
def truncate(self, keep_last: int | None = None) -> int
```

截断消息历史。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keep_last` | `int \| None` | `None` | 保留最近 N 条消息 |

**返回值:** `int` - 截断的消息数量

---

#### `clear()`

```python
def clear(self) -> None
```

清空所有消息历史。

---

#### `mark_skill_loaded()`

```python
def mark_skill_loaded(self, skill_name: str) -> None
```

标记技能已加载。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `skill_name` | `str` | 技能名称 |

---

#### `is_skill_loaded()`

```python
def is_skill_loaded(self, skill_name: str) -> bool
```

检查技能是否已加载。

**返回值:** `bool` - 技能是否已加载

---

#### `get_loaded_skills()`

```python
def get_loaded_skills(self) -> set[str]
```

获取已加载的技能列表。

**返回值:** `set[str]` - 技能名称集合

---

#### 序列化方法

```python
def to_dict(self) -> dict[str, Any]
def to_json(self) -> str

@classmethod
def from_dict(cls, data: dict[str, Any]) -> "ContextManager"

@classmethod
def from_json(cls, json_str: str) -> "ContextManager"
```

支持上下文的序列化和反序列化，用于持久化存储。

---

## 3. ToolExecutor - 工具执行器

**位置:** `pyagentforge.kernel.executor.ToolExecutor`

负责执行工具调用并返回结果。

### 构造函数

```python
def __init__(
    self,
    tool_registry: ToolRegistry,
    timeout: int = 120,
    permission_checker: PermissionChecker | None = None,
    max_output_length: int = 50000,
) -> None
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tool_registry` | `ToolRegistry` | **必需** | 工具注册表 |
| `timeout` | `int` | `120` | 执行超时时间 (秒) |
| `permission_checker` | `PermissionChecker \| None` | `None` | 权限检查器 |
| `max_output_length` | `int` | `50000` | 最大输出长度 (字符) |

---

### 方法

#### `execute()`

```python
async def execute(
    self,
    tool_call: ToolUseBlock,
    ask_callback: Callable[[str, dict], Any] | None = None,
) -> str
```

执行单个工具调用。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_call` | `ToolUseBlock` | 工具调用信息 |
| `ask_callback` | `Callable[[str, dict], Any] \| None` | 用户确认回调 |

**返回值:** `str` - 工具执行结果

---

#### `execute_batch()`

```python
async def execute_batch(
    self,
    tool_calls: list[ToolUseBlock],
    ask_callback: Callable[[str, dict], Any] | None = None,
) -> list[tuple[str, str]]
```

批量执行工具调用（并行）。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_calls` | `list[ToolUseBlock]` | 工具调用列表 |
| `ask_callback` | `Callable[[str, dict], Any] \| None` | 用户确认回调 |

**返回值:** `list[tuple[str, str]]` - `[(tool_use_id, result), ...]` 列表

---

## 4. ToolRegistry - 工具注册表

**位置:** `pyagentforge.kernel.executor.ToolRegistry`

工具注册和管理中心。

### 方法

#### `register()`

```python
def register(self, tool: BaseTool) -> None
```

注册工具。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool` | `BaseTool` | 工具实例 |

---

#### `unregister()`

```python
def unregister(self, tool_name: str) -> None
```

注销工具。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `tool_name` | `str` | 工具名称 |

---

#### `get()`

```python
def get(self, tool_name: str) -> BaseTool | None
```

获取工具实例。

**返回值:** `BaseTool | None` - 工具实例或 None

---

#### `get_all()`

```python
def get_all(self) -> list[BaseTool]
```

获取所有已注册的工具。

**返回值:** `list[BaseTool]` - 工具列表

---

#### `get_schemas()`

```python
def get_schemas(self) -> list[dict[str, Any]]
```

获取所有工具的 JSON Schema。

**返回值:** `list[dict[str, Any]]` - 工具 Schema 列表

---

## 5. 消息类型

**位置:** `pyagentforge.kernel.message`

定义 Agent 通信所需的所有消息格式。

### 5.1 TextBlock

```python
class TextBlock(BaseModel):
    """文本内容块"""
    type: Literal["text"] = "text"
    text: str
```

---

### 5.2 ToolUseBlock

```python
class ToolUseBlock(BaseModel):
    """工具调用块"""
    type: Literal["tool_use"] = "tool_use"
    id: str = Field(..., description="工具调用唯一标识")
    name: str = Field(..., description="工具名称")
    input: dict[str, Any] = Field(default_factory=dict, description="工具输入参数")
```

---

### 5.3 ToolResultBlock

```python
class ToolResultBlock(BaseModel):
    """工具结果块"""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = Field(..., description="对应的工具调用 ID")
    content: str = Field(..., description="工具返回内容")
    is_error: bool = Field(default=False, description="是否为错误结果")
```

---

### 5.4 Message

```python
class Message(BaseModel):
    """对话消息"""
    role: Literal["user", "assistant"]
    content: MessageContent  # Union[str, list[Union[TextBlock, ToolUseBlock, ToolResultBlock]]]
```

#### 类方法

##### `user_message()`

```python
@classmethod
def user_message(cls, content: str) -> "Message"
```

创建用户消息。

---

##### `assistant_text()`

```python
@classmethod
def assistant_text(cls, text: str) -> "Message"
```

创建助手文本消息。

---

##### `assistant_tool_calls()`

```python
@classmethod
def assistant_tool_calls(
    cls,
    tool_calls: list[ToolUseBlock],
) -> "Message"
```

创建助手工具调用消息。

---

##### `tool_result()`

```python
@classmethod
def tool_result(
    cls,
    tool_use_id: str,
    content: str,
    is_error: bool = False,
) -> "Message"
```

创建工具结果消息。

---

### 5.5 ProviderResponse

```python
class ProviderResponse(BaseModel):
    """LLM 提供商响应"""
    content: list[Union[TextBlock, ToolUseBlock]]
    stop_reason: str  # end_turn, tool_use, max_tokens
    usage: dict[str, int] = Field(default_factory=dict)
```

#### 属性

- `text: str` - 提取文本内容
- `tool_calls: list[ToolUseBlock]` - 提取工具调用
- `has_tool_calls: bool` - 是否有工具调用

---

## 6. BaseTool - 工具基类

**位置:** `pyagentforge.kernel.base_tool.BaseTool`

所有工具的抽象基类。

### 类属性

```python
class BaseTool(ABC):
    name: str = "base_tool"
    description: str = "基础工具"
    parameters_schema: dict[str, Any] = {}
    timeout: int = 60
    risk_level: str = "low"  # low, medium, high
```

---

### 抽象方法

#### `execute()`

```python
@abstractmethod
async def execute(self, **kwargs: Any) -> str
```

执行工具逻辑（子类必须实现）。

**参数:** `**kwargs` - 工具参数

**返回值:** `str` - 工具执行结果

---

### 方法

#### `to_anthropic_schema()`

```python
def to_anthropic_schema(self) -> dict[str, Any]
```

转换为 Anthropic 工具格式。

---

#### `to_openai_schema()`

```python
def to_openai_schema(self) -> dict[str, Any]
```

转换为 OpenAI 工具格式。

---

### 自定义工具示例

```python
from pyagentforge import BaseTool

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "查询内容"
            }
        },
        "required": ["query"]
    }
    timeout = 30
    risk_level = "low"

    async def execute(self, query: str) -> str:
        """执行工具逻辑"""
        # 实现你的逻辑
        return f"处理结果: {query}"

# 注册工具
registry = ToolRegistry()
registry.register(MyCustomTool())
```

---

## 7. BaseProvider - Provider 基类

**位置:** `pyagentforge.kernel.base_provider.BaseProvider`

所有 LLM 提供商的抽象基类。

### 构造函数

```python
def __init__(
    self,
    model: str,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    **kwargs: Any,
) -> None
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str` | **必需** | 模型标识符 |
| `max_tokens` | `int` | `4096` | 最大 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 |
| `**kwargs` | `Any` | - | 额外参数 |

---

### 抽象方法

#### `create_message()`

```python
@abstractmethod
async def create_message(
    self,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    **kwargs: Any,
) -> ProviderResponse
```

创建消息（子类必须实现）。

---

#### `count_tokens()`

```python
@abstractmethod
async def count_tokens(self, messages: list[dict[str, Any]]) -> int
```

计算 Token 数量（子类必须实现）。

---

### 可选方法

#### `stream_message()`

```python
async def stream_message(
    self,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    **kwargs: Any,
)
```

流式创建消息（子类可选实现）。

---

## 8. PermissionChecker - 权限检查器

**位置:** `pyagentforge.kernel.executor.PermissionChecker`

简单的工具权限检查器。

### 构造函数

```python
def __init__(
    self,
    allowed_tools: set[str] | None = None,
    denied_tools: set[str] | None = None,
    ask_tools: set[str] | None = None,
)
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `allowed_tools` | `set[str] \| None` | `None` | 允许的工具集合 |
| `denied_tools` | `set[str] \| None` | `None` | 拒绝的工具集合 |
| `ask_tools` | `set[str] \| None` | `None` | 需要询问的工具集合 |

---

### 方法

#### `check()`

```python
def check(self, tool_name: str, tool_input: dict) -> str
```

检查工具权限。

**返回值:** `str` - `"allow"`, `"deny"`, 或 `"ask"`

---

## 9. 工厂函数

### `create_engine()`

**位置:** `pyagentforge.create_engine`

创建配置好的 AgentEngine。

```python
async def create_engine(
    provider: BaseProvider,
    config: Optional[Dict[str, Any]] = None,
    plugin_config: Optional[PluginConfig] = None,
    working_dir: Optional[str] = None,
    **kwargs,
) -> AgentEngine
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | `BaseProvider` | **必需** | LLM 提供商 |
| `config` | `Optional[Dict[str, Any]]` | `None` | Agent 配置 |
| `plugin_config` | `Optional[PluginConfig]` | `None` | 插件配置 |
| `working_dir` | `Optional[str]` | `None` | 工作目录 |
| `**kwargs` | `Any` | - | 其他参数 |

**返回值:** `AgentEngine` - 配置好的引擎实例

**示例:**

```python
from pyagentforge import create_engine, AnthropicProvider, PluginConfig

provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
plugin_config = PluginConfig.from_preset("standard")

engine = await create_engine(
    provider=provider,
    plugin_config=plugin_config,
    working_dir="/path/to/workdir",
)

response = await engine.run("Hello!")
```

---

### `create_minimal_engine()`

**位置:** `pyagentforge.create_minimal_engine`

创建最小化引擎（无插件）。

```python
def create_minimal_engine(
    provider: BaseProvider,
    working_dir: Optional[str] = None,
    **kwargs,
) -> AgentEngine
```

**返回值:** `AgentEngine` - 最小化引擎实例

**示例:**

```python
from pyagentforge import create_minimal_engine, AnthropicProvider

provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
engine = create_minimal_engine(provider=provider)

response = await engine.run("Hello!")
```

---

## 扩展阅读

- [Provider API 文档](./02-providers-api.md)
- [工具系统 API 文档](./03-tools-api.md)
- [插件系统 API 文档](./05-plugin-system-api.md)
- [配置 API 文档](./06-configuration-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 重构为 Kernel + Plugin 架构 |
| v1.x | 2026-02-01 | 初始版本 |

---

*本文档由 Claude Code 自动生成*