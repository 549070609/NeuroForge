# PyAgentForge 工具系统 API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本文档详细说明 PyAgentForge 的工具系统，包括内置工具和自定义工具开发。

---

## 目录

- [1. 工具系统概述](#1-工具系统概述)
- [2. 内置工具列表](#2-内置工具列表)
- [3. BaseTool - 工具基类](#3-basetool---工具基类)
- [4. 自定义工具开发](#4-自定义工具开发)
- [5. 工具装饰器](#5-工具装饰器)
- [6. 工具权限控制](#6-工具权限控制)

---

## 1. 工具系统概述

PyAgentForge 采用双层工具系统：

### Kernel Core Tools (最小核心工具集)

位置: `pyagentforge/kernel/core_tools/`

提供 Agent 执行的最小工具集（6个核心工具）：

| 工具 | 功能 |
|------|------|
| `BashTool` | 执行 Shell 命令 |
| `ReadTool` | 读取文件 |
| `WriteTool` | 写入文件 |
| `EditTool` | 编辑文件 |
| `GlobTool` | 文件模式匹配 |
| `GrepTool` | 内容搜索 |

注册函数:
```python
from pyagentforge.kernel.core_tools import register_core_tools

tool_registry = ToolRegistry()
register_core_tools(tool_registry, working_dir="/path/to/workdir")
```

---

### Extended Tools (扩展工具集)

位置: `pyagentforge/tools/builtin/`

提供丰富的扩展工具（20+ 个工具）：

#### P1 重要工具
- `LsTool` - 列出目录
- `LSPTool` - LSP 集成
- `QuestionTool`, `ConfirmTool` - 用户交互
- `CodeSearchTool` - 代码搜索
- `ApplyPatchTool`, `DiffTool` - 补丁应用
- `PlanTool`, `PlanEnterTool`, `PlanExitTool` - 规划工具

#### P2 可选工具
- `TruncationTool`, `ContextCompactTool` - 上下文管理
- `InvalidTool`, `ToolSuggestionTool` - 错误处理
- `ExternalDirectoryTool`, `WorkspaceTool` - 工作区管理

#### 扩展工具
- `WebFetchTool` - 网页抓取
- `WebSearchTool` - 网页搜索
- `TodoWriteTool`, `TodoReadTool` - 任务管理
- `MultiEditTool` - 多文件编辑
- `BatchTool` - 批量执行
- `TaskTool` - 子任务工具

---

## 2. 内置工具列表

### 2.1 BashTool

执行 Shell 命令。

**参数:**

```json
{
  "command": "string - 要执行的命令",
  "timeout": "integer (可选) - 超时时间（秒），默认 120",
  "working_dir": "string (可选) - 工作目录"
}
```

**返回:** `string` - 命令输出

**风险级别:** `high`

---

### 2.2 ReadTool

读取文件内容。

**参数:**

```json
{
  "file_path": "string - 文件路径（绝对路径）",
  "offset": "integer (可选) - 起始行号",
  "limit": "integer (可选) - 读取行数"
}
```

**返回:** `string` - 文件内容（带行号）

**风险级别:** `low`

---

### 2.3 WriteTool

写入文件。

**参数:**

```json
{
  "file_path": "string - 文件路径（绝对路径）",
  "content": "string - 文件内容"
}
```

**返回:** `string` - 成功/失败消息

**风险级别:** `medium`

---

### 2.4 EditTool

编辑文件（精确字符串替换）。

**参数:**

```json
{
  "file_path": "string - 文件路径",
  "old_string": "string - 要替换的字符串",
  "new_string": "string - 新字符串",
  "replace_all": "boolean (可选) - 是否全部替换，默认 false"
}
```

**返回:** `string` - 操作结果

**风险级别:** `medium`

---

### 2.5 GlobTool

文件模式匹配。

**参数:**

```json
{
  "pattern": "string - Glob 模式（如 **/*.py）",
  "path": "string (可选) - 搜索目录，默认当前目录"
}
```

**返回:** `string` - 匹配的文件列表

**风险级别:** `low`

---

### 2.6 GrepTool

内容搜索。

**参数:**

```json
{
  "pattern": "string - 正则表达式模式",
  "path": "string (可选) - 搜索路径",
  "glob": "string (可选) - 文件过滤模式",
  "output_mode": "string - 输出模式: content/files_with_matches/count",
  "-i": "boolean (可选) - 忽略大小写",
  "-n": "boolean (可选) - 显示行号，默认 true"
}
```

**返回:** `string` - 搜索结果

**风险级别:** `low`

---

## 3. BaseTool - 工具基类

**位置:** `pyagentforge.kernel.base_tool.BaseTool`

所有工具的抽象基类。

### 类属性

```python
class BaseTool(ABC):
    name: str = "base_tool"              # 工具名称（唯一标识）
    description: str = "基础工具"          # 工具描述
    parameters_schema: dict[str, Any] = {}  # JSON Schema
    timeout: int = 60                    # 超时时间（秒）
    risk_level: str = "low"              # 风险级别: low/medium/high
```

---

### 抽象方法

#### `execute()`

```python
@abstractmethod
async def execute(self, **kwargs: Any) -> str
```

执行工具逻辑。**子类必须实现。**

**参数:** `**kwargs` - 从 `parameters_schema` 验证的参数

**返回:** `str` - 工具执行结果

---

### 方法

#### `to_anthropic_schema()`

```python
def to_anthropic_schema(self) -> dict[str, Any]
```

转换为 Anthropic 工具格式。

**返回格式:**

```python
{
    "name": "tool_name",
    "description": "Tool description",
    "input_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```

---

#### `to_openai_schema()`

```python
def to_openai_schema(self) -> dict[str, Any]
```

转换为 OpenAI 工具格式。

**返回格式:**

```python
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {...}
    }
}
```

---

## 4. 自定义工具开发

### 完整示例

```python
from pyagentforge import BaseTool
from typing import Any

class WeatherTool(BaseTool):
    """天气查询工具"""

    name = "get_weather"
    description = "获取指定城市的天气信息"
    timeout = 30
    risk_level = "low"

    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如 'Beijing'"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "温度单位",
                "default": "celsius"
            }
        },
        "required": ["city"]
    }

    async def execute(self, city: str, unit: str = "celsius") -> str:
        """
        执行天气查询

        Args:
            city: 城市名称
            unit: 温度单位

        Returns:
            天气信息字符串
        """
        # 实现你的逻辑
        # 例如调用天气 API
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = f"https://api.weather.com/{city}"
            async with session.get(url) as response:
                data = await response.json()

        # 格式化结果
        temp = data["temperature"]
        if unit == "fahrenheit":
            temp = temp * 9/5 + 32

        return f"{city} 当前温度: {temp}°{unit[0].upper()}, {data['condition']}"

# 注册工具
from pyagentforge import ToolRegistry

registry = ToolRegistry()
registry.register(WeatherTool())
```

---

### 带文件操作的工具

```python
class FileAnalyzerTool(BaseTool):
    """文件分析工具"""

    name = "analyze_file"
    description = "分析文件并返回统计信息"
    risk_level = "low"

    parameters_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要分析的文件路径"
            },
            "analysis_type": {
                "type": "string",
                "enum": ["lines", "words", "chars"],
                "description": "分析类型"
            }
        },
        "required": ["file_path"]
    }

    async def execute(
        self,
        file_path: str,
        analysis_type: str = "lines"
    ) -> str:
        """执行文件分析"""

        # 安全检查
        import os
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 分析
        if analysis_type == "lines":
            result = len(content.splitlines())
        elif analysis_type == "words":
            result = len(content.split())
        elif analysis_type == "chars":
            result = len(content)
        else:
            result = 0

        return f"File analysis ({analysis_type}): {result}"

# 注册
registry.register(FileAnalyzerTool())
```

---

## 5. 工具装饰器

PyAgentForge 提供 `@tool` 装饰器，用于快速创建工具。

### 使用示例

```python
from pyagentforge.tools.decorators import tool

@tool
async def calculate(expression: str) -> str:
    """
    计算数学表达式

    Args:
        expression: 数学表达式，如 '2+2'
    """
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"

# 工具自动注册
# name: "calculate"
# description: "计算数学表达式"
# parameters: 从函数签名自动推断
```

### 带完整配置

```python
from pyagentforge.tools.decorators import tool

@tool(
    name="custom_calculator",
    description="高级计算器工具",
    timeout=60,
    risk_level="medium"
)
async def advanced_calculator(
    expression: str,
    precision: int = 2
) -> str:
    """
    高级数学计算

    Args:
        expression: 数学表达式
        precision: 结果精度（小数位数）
    """
    try:
        result = eval(expression)
        formatted = f"{result:.{precision}f}"
        return f"Result: {formatted}"
    except Exception as e:
        return f"Error: {str(e)}"
```

---

## 6. 工具权限控制

### PermissionChecker

**位置:** `pyagentforge.kernel.executor.PermissionChecker`

控制工具执行权限。

```python
from pyagentforge import PermissionChecker, ToolRegistry

# 创建权限检查器
checker = PermissionChecker(
    allowed_tools={"read", "write", "bash"},  # 允许的工具
    denied_tools={"bash"},                    # 拒绝的工具（优先级更高）
    ask_tools={"write"},                      # 需要询问的工具
)

# 在执行器中使用
executor = ToolExecutor(
    tool_registry=registry,
    permission_checker=checker,
)

# 或在 Agent 配置中使用
from pyagentforge.kernel.engine import AgentConfig

config = AgentConfig(
    permission_checker=checker,
)
```

---

### 自定义权限检查器

```python
from pyagentforge.kernel.executor import PermissionChecker, PermissionResult

class CustomPermissionChecker(PermissionChecker):
    """自定义权限检查器"""

    def __init__(self, user_role: str):
        super().__init__()
        self.user_role = user_role

    def check(self, tool_name: str, tool_input: dict) -> str:
        """自定义权限检查逻辑"""

        # 管理员拥有所有权限
        if self.user_role == "admin":
            return PermissionResult.ALLOW

        # 访客只能使用只读工具
        if self.user_role == "guest":
            read_only_tools = {"read", "glob", "grep"}
            if tool_name in read_only_tools:
                return PermissionResult.ALLOW
            return PermissionResult.DENY

        # 普通用户需要确认危险操作
        dangerous_tools = {"bash", "write"}
        if tool_name in dangerous_tools:
            return PermissionResult.ASK

        return PermissionResult.ALLOW

# 使用
checker = CustomPermissionChecker(user_role="user")
config = AgentConfig(permission_checker=checker)
```

---

## 工具最佳实践

### 1. 错误处理

```python
async def execute(self, **kwargs) -> str:
    try:
        # 工具逻辑
        result = await some_operation()
        return result
    except FileNotFoundError as e:
        return f"Error: File not found - {e}"
    except PermissionError as e:
        return f"Error: Permission denied - {e}"
    except Exception as e:
        return f"Error: {type(e).__name__} - {str(e)}"
```

### 2. 输入验证

```python
async def execute(self, file_path: str) -> str:
    # 验证路径
    import os
    if not os.path.isabs(file_path):
        return "Error: file_path must be absolute"

    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    # 继续处理...
```

### 3. 超时控制

```python
import asyncio

async def execute(self, url: str) -> str:
    try:
        result = await asyncio.wait_for(
            fetch_url(url),
            timeout=self.timeout,
        )
        return result
    except asyncio.TimeoutError:
        return f"Error: Operation timed out after {self.timeout}s"
```

### 4. 输出截断

```python
async def execute(self, query: str) -> str:
    result = await long_operation()

    # 限制输出长度
    max_length = 10000
    if len(result) > max_length:
        result = result[:max_length] + f"\n... (truncated, total {len(result)} chars)"

    return result
```

---

## 相关文档

- [核心 API 文档](./01-core-api.md)
- [插件系统 API 文档](./05-plugin-system-api.md)
- [命令与技能系统 API 文档](./04-commands-skills-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 重构为双层工具系统 |
| v1.x | 2026-02-01 | 初始实现 |

---

*本文档由 Claude Code 自动生成*
