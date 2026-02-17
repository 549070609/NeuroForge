# PyAgentForge Provider API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本文档详细说明 PyAgentForge 的 LLM 提供商集成接口和实现。

---

## 目录

- [1. 概述](#1-概述)
- [2. BaseProvider - Provider 基类](#2-baseprovider---provider-基类)
- [3. AnthropicProvider](#3-anthropicprovider)
- [4. OpenAIProvider](#4-openaiprovider)
- [5. GoogleProvider](#5-googleprovider)
- [6. 工厂方法](#6-工厂方法)
- [7. 自定义 Provider](#7-自定义-provider)

---

## 1. 概述

PyAgentForge 通过统一的 `BaseProvider` 接口支持多种 LLM 提供商：

| Provider | 支持模型 | 特性 |
|----------|---------|------|
| **AnthropicProvider** | Claude 3.5, Claude 3 | 流式输出、工具调用、Vision |
| **OpenAIProvider** | GPT-4, GPT-3.5 | 流式输出、工具调用、Vision |
| **GoogleProvider** | Gemini 2.0, Gemini 1.5 | 流式输出、工具调用、长上下文 |

所有 Provider 共享统一的接口，可以无缝切换。

---

## 2. BaseProvider - Provider 基类

**位置:** `pyagentforge.kernel.base_provider.BaseProvider`

所有 LLM 提供商的抽象基类，定义统一接口。

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
| `max_tokens` | `int` | `4096` | 最大生成 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 (0.0-2.0) |
| `**kwargs` | `Any` | - | 额外参数，存储在 `extra_params` |

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

创建消息并返回 LLM 响应。**子类必须实现此方法。**

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `system` | `str` | 系统提示词 |
| `messages` | `list[dict[str, Any]]` | 对话历史 |
| `tools` | `list[dict[str, Any]]` | 可用工具列表 |
| `**kwargs` | `Any` | 额外参数 |

**返回值:** `ProviderResponse` - 统一格式的响应对象

---

#### `count_tokens()`

```python
@abstractmethod
async def count_tokens(self, messages: list[dict[str, Any]]) -> int
```

计算消息列表的 Token 数量。**子类必须实现此方法。**

**返回值:** `int` - Token 数量

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

流式创建消息。子类可选实现，默认调用非流式方法。

**Yields:** 流式响应块

---

## 3. AnthropicProvider

**位置:** `pyagentforge.providers.anthropic_provider.AnthropicProvider`

Anthropic Claude 系列模型的 Provider 实现。

### 构造函数

```python
def __init__(
    self,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    temperature: float = 1.0,
    **kwargs: Any,
) -> None
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | `str` | **必需** | Anthropic API Key |
| `model` | `str` | `"claude-sonnet-4-20250514"` | 模型 ID |
| `max_tokens` | `int` | `4096` | 最大生成 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 |

**支持的模型:**

| 模型 ID | 上下文窗口 | 特性 |
|---------|-----------|------|
| `claude-sonnet-4-20250514` | 200K | 最新 Sonnet |
| `claude-3-5-sonnet-20241022` | 200K | Claude 3.5 Sonnet |
| `claude-3-5-haiku-20241022` | 200K | Claude 3.5 Haiku |
| `claude-3-opus-20240229` | 200K | Claude 3 Opus |

---

### 使用示例

```python
import os
from pyagentforge import AnthropicProvider

# 创建 Provider
provider = AnthropicProvider(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
)

# 创建消息
response = await provider.create_message(
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    tools=[],  # 可选：工具列表
)

print(response.text)
```

---

### 流式输出

```python
# 流式调用
async for event in provider.stream_message(
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}],
    tools=[],
):
    if hasattr(event, "text"):
        print(event.text, end="", flush=True)
```

---

## 4. OpenAIProvider

**位置:** `pyagentforge.providers.openai_provider.OpenAIProvider`

OpenAI GPT 系列模型的 Provider 实现。

### 构造函数

```python
def __init__(
    self,
    api_key: str,
    model: str = "gpt-4-turbo-preview",
    max_tokens: int = 4096,
    temperature: float = 1.0,
    base_url: str | None = None,
    **kwargs: Any,
) -> None
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | `str` | **必需** | OpenAI API Key |
| `model` | `str` | `"gpt-4-turbo-preview"` | 模型 ID |
| `max_tokens` | `int` | `4096` | 最大生成 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 |
| `base_url` | `str \| None` | `None` | API 基础 URL（用于兼容 API） |

**支持的模型:**

| 模型 ID | 上下文窗口 | 特性 |
|---------|-----------|------|
| `gpt-4-turbo-preview` | 128K | GPT-4 Turbo |
| `gpt-4` | 8K | GPT-4 |
| `gpt-4o` | 128K | GPT-4 Omni |
| `gpt-3.5-turbo` | 16K | GPT-3.5 Turbo |

---

### 使用示例

```python
import os
from pyagentforge import OpenAIProvider

# 创建 Provider
provider = OpenAIProvider(
    api_key=os.environ["OPENAI_API_KEY"],
    model="gpt-4-turbo-preview",
)

# 创建消息
response = await provider.create_message(
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    tools=[],
)

print(response.text)
```

---

### 使用兼容 API (如 Azure OpenAI)

```python
# Azure OpenAI 示例
provider = OpenAIProvider(
    api_key=os.environ["AZURE_OPENAI_KEY"],
    model="gpt-4",
    base_url="https://your-resource.openai.azure.com/",
)
```

---

## 5. GoogleProvider

**位置:** `pyagentforge.providers.google_provider.GoogleProvider`

Google Gemini 系列模型的 Provider 实现。

### 构造函数

```python
def __init__(
    self,
    model: str = "gemini-2.0-flash",
    api_key: str | None = None,
    max_tokens: int = 8192,
    temperature: float = 1.0,
    **kwargs: Any,
) -> None
```

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str` | `"gemini-2.0-flash"` | 模型 ID |
| `api_key` | `str \| None` | `None` | Google API Key（可从环境变量） |
| `max_tokens` | `int` | `8192` | 最大生成 Token 数 |
| `temperature` | `float` | `1.0` | 生成温度 |

**注意:** 如果未提供 `api_key`，将从环境变量 `GOOGLE_API_KEY` 读取。

**支持的模型:**

| 模型 ID | 上下文窗口 | 特性 |
|---------|-----------|------|
| `gemini-2.0-flash` | 1M | Gemini 2.0 Flash（快速） |
| `gemini-1.5-pro` | 2M | Gemini 1.5 Pro（长上下文） |
| `gemini-1.5-flash` | 1M | Gemini 1.5 Flash |

---

### 使用示例

```python
import os
from pyagentforge.providers.google_provider import GoogleProvider

# 创建 Provider（自动从环境变量读取 API Key）
provider = GoogleProvider(
    model="gemini-2.0-flash",
)

# 或显式提供 API Key
provider = GoogleProvider(
    api_key="your-google-api-key",
    model="gemini-1.5-pro",
    max_tokens=8192,
)

# 创建消息
response = await provider.create_message(
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    tools=[],
)

print(response.text)
```

---

### 流式输出

```python
# 流式调用
async for chunk in provider.stream_message(
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}],
    tools=[],
):
    if isinstance(chunk, dict) and chunk.get("type") == "text_delta":
        print(chunk["text"], end="", flush=True)
```

---

## 6. 工厂方法

### `create_provider()`

**位置:** `pyagentforge.providers.factory.create_provider`

根据模型 ID 自动创建对应的 Provider 实例。

```python
def create_provider(
    model_id: str,
    **kwargs: Any,
) -> BaseProvider
```

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `model_id` | `str` | 模型 ID |
| `**kwargs` | `Any` | 传递给 Provider 的额外参数 |

**返回值:** `BaseProvider` - Provider 实例

**示例:**

```python
from pyagentforge.providers import create_provider

# 创建 Claude Provider
provider = create_provider("claude-3-5-sonnet-20241022")

# 创建 GPT Provider
provider = create_provider("gpt-4-turbo-preview")

# 创建 Gemini Provider
provider = create_provider("gemini-2.0-flash")

# 传递额外参数
provider = create_provider(
    "claude-3-5-sonnet-20241022",
    max_tokens=8192,
    temperature=0.7,
)
```

---

### `get_supported_models()`

**位置:** `pyagentforge.providers.factory.get_supported_models`

获取所有支持的模型 ID 列表。

```python
def get_supported_models() -> list[str]
```

**返回值:** `list[str]` - 模型 ID 列表

**示例:**

```python
from pyagentforge.providers import get_supported_models

models = get_supported_models()
print(models)
# ['claude-3-5-sonnet-20241022', 'gpt-4-turbo-preview', 'gemini-2.0-flash', ...]
```

---

### `ModelAdapterFactory`

**位置:** `pyagentforge.providers.factory.ModelAdapterFactory`

高级工厂类，提供更多控制选项。

#### 方法

##### `create_provider()`

```python
def create_provider(
    self,
    model_id: str,
    **kwargs: Any,
) -> BaseProvider
```

创建 Provider 实例（带缓存）。

---

##### `get_supported_models()`

```python
def get_supported_models(self) -> list[str]
```

获取所有支持的模型 ID。

---

##### `get_model_info()`

```python
def get_model_info(self, model_id: str) -> dict[str, Any] | None
```

获取模型详细信息。

**返回结构:**

```python
{
    "id": str,                      # 模型 ID
    "name": str,                    # 显示名称
    "provider": str,                # 提供商类型
    "api_type": str,                # API 类型
    "supports_vision": bool,        # 是否支持视觉
    "supports_tools": bool,         # 是否支持工具
    "supports_streaming": bool,     # 是否支持流式
    "context_window": int,          # 上下文窗口大小
    "max_output_tokens": int,       # 最大输出 Token
    "cost_input": float,            # 输入成本（每 1K tokens）
    "cost_output": float,           # 输出成本（每 1K tokens）
}
```

---

## 7. 自定义 Provider

### 实现自定义 Provider

继承 `BaseProvider` 并实现必要方法：

```python
from pyagentforge import BaseProvider, ProviderResponse, TextBlock, ToolUseBlock
from typing import Any

class MyCustomProvider(BaseProvider):
    """自定义 Provider 示例"""

    def __init__(
        self,
        api_key: str,
        model: str = "my-model-v1",
        endpoint: str = "https://api.example.com/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self.api_key = api_key
        self.endpoint = endpoint
        # 初始化客户端...

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        实现消息创建逻辑

        1. 调用你的 LLM API
        2. 解析响应
        3. 返回 ProviderResponse
        """
        # 调用你的 API
        # response = await self.client.chat(...)

        # 解析响应
        content_blocks = []

        # 添加文本块
        # content_blocks.append(TextBlock(text=response.text))

        # 添加工具调用（如果有）
        # for tool_call in response.tool_calls:
        #     content_blocks.append(ToolUseBlock(
        #         id=tool_call.id,
        #         name=tool_call.name,
        #         input=tool_call.input,
        #     ))

        return ProviderResponse(
            content=content_blocks,
            stop_reason="end_turn",  # 或 "tool_use", "max_tokens"
            usage={
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """实现 Token 计数逻辑"""
        # 使用对应的 tokenizer
        # 或提供近似估算
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4  # 粗略估算
        return total

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """可选：实现流式输出"""
        # 流式调用 API
        # async for chunk in self.client.stream(...):
        #     yield chunk

        # 最终返回完整响应
        # yield ProviderResponse(...)
```

---

### 注册自定义 Provider

将自定义 Provider 注册到模型注册表：

```python
from pyagentforge.core.model_registry import (
    ModelRegistry,
    ModelConfig,
    ProviderType,
    register_model,
)
from pyagentforge.providers.factory import get_factory

# 方法 1: 直接注册模型配置
registry = ModelRegistry()
registry.register_model(ModelConfig(
    id="my-custom-model",
    name="My Custom Model",
    provider=ProviderType.CUSTOM,
    api_key_env="MY_API_KEY",
    context_window=8192,
    max_output_tokens=2048,
    supports_tools=True,
    supports_streaming=True,
))

# 方法 2: 注册 Provider 工厂
registry.register_provider(
    provider_type=ProviderType.CUSTOM,
    factory=lambda model, **kwargs: MyCustomProvider(
        api_key=os.environ.get("MY_API_KEY"),
        model=model,
        **kwargs,
    ),
)

# 使用工厂创建
factory = get_factory()
provider = factory.create_provider("my-custom-model")
```

---

## 完整示例

### 多 Provider 切换

```python
import os
from pyagentforge import AgentEngine, ToolRegistry
from pyagentforge.providers import create_provider

async def run_with_different_models():
    """演示在不同 Provider 之间切换"""

    models = [
        "claude-3-5-sonnet-20241022",
        "gpt-4-turbo-preview",
        "gemini-2.0-flash",
    ]

    for model_id in models:
        print(f"\n{'='*60}")
        print(f"Testing with {model_id}")
        print('='*60)

        # 创建 Provider
        provider = create_provider(model_id)

        # 创建引擎
        tool_registry = ToolRegistry()
        engine = AgentEngine(
            provider=provider,
            tool_registry=tool_registry,
        )

        # 运行 Agent
        response = await engine.run("What is 2+2?")
        print(f"Response: {response}")

        # 重置
        engine.reset()

# 运行
import asyncio
asyncio.run(run_with_different_models())
```

---

### 故障转移 (Failover)

```python
from pyagentforge.core.failover import ProviderPool, FailoverConfig
from pyagentforge.providers import AnthropicProvider, OpenAIProvider

# 创建 Provider 池
providers = [
    AnthropicProvider(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model="claude-3-5-sonnet-20241022",
    ),
    OpenAIProvider(
        api_key=os.environ["OPENAI_API_KEY"],
        model="gpt-4-turbo-preview",
    ),
]

# 配置故障转移
failover_config = FailoverConfig(
    max_retries=3,
    retry_delay=1.0,
    fallback_on_rate_limit=True,
    fallback_on_timeout=True,
)

# 创建 Provider 池
pool = ProviderPool(providers, failover_config)

# 使用（自动故障转移）
response = await pool.create_message(
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}],
    tools=[],
)
```

---

## 相关文档

- [核心 API 文档](./01-core-api.md)
- [工具系统 API 文档](./03-tools-api.md)
- [配置 API 文档](./06-configuration-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 统一 Provider 接口，添加工厂方法 |
| v1.x | 2026-02-01 | 初始实现 |

---

*本文档由 Claude Code 自动生成*