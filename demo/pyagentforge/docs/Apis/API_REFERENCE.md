# PyAgentForge 接口文档

## 目录

- [1. 核心 API (Python SDK)](#1-核心-api-python-sdk)
- [2. REST API](#2-rest-api)
- [3. WebSocket API](#3-websocket-api)
- [4. CLI 命令](#4-cli-命令)
- [5. 内置工具](#5-内置工具)
- [6. Skills 系统](#6-skills-系统)

---

## 1. 核心 API (Python SDK)

### 1.1 AgentEngine

Agent 执行引擎，核心执行循环。

```python
from pyagentforge import AgentEngine, ContextManager, ToolRegistry
from pyagentforge.providers import AnthropicProvider

# 创建引擎
provider = AnthropicProvider(api_key="your-api-key", model="claude-sonnet-4-20250514")
tools = ToolRegistry()
tools.register_builtin_tools()

engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
    config=None,           # AgentConfig 可选
    context=None,          # ContextManager 可选
    ask_callback=None,     # 用户确认回调
)
```

**主要方法：**

| 方法 | 说明 | 返回 |
|------|------|------|
| `run(prompt: str)` | 同步运行 Agent | `str` |
| `run_stream(prompt: str)` | 流式运行 Agent | `AsyncGenerator` |
| `reset()` | 重置 Agent 状态 | `None` |
| `get_context_summary()` | 获取上下文摘要 | `dict` |

**属性：**

| 属性 | 说明 |
|------|------|
| `session_id` | 会话唯一标识 |
| `context` | ContextManager 实例 |
| `tools` | ToolRegistry 实例 |

### 1.2 ContextManager

管理对话历史和上下文。

```python
from pyagentforge.core import ContextManager

ctx = ContextManager(
    max_messages=100,
    system_prompt="You are a helpful assistant.",
)
```

**主要方法：**

| 方法 | 说明 |
|------|------|
| `add_user_message(content)` | 添加用户消息 |
| `add_assistant_message(content)` | 添加助手消息 |
| `add_assistant_text(text)` | 添加助手文本 |
| `add_tool_result(tool_use_id, result)` | 添加工具结果 |
| `get_messages_for_api()` | 获取 API 格式消息 |
| `truncate(keep_last)` | 截断历史 |
| `clear()` | 清空历史 |
| `mark_skill_loaded(name)` | 标记技能已加载 |
| `is_skill_loaded(name)` | 检查技能状态 |
| `to_json() / from_json()` | 序列化/反序列化 |

### 1.3 ToolRegistry

工具注册与管理。

```python
from pyagentforge.tools import ToolRegistry, BaseTool

registry = ToolRegistry()

# 注册内置工具
registry.register_builtin_tools()  # 核心 6 个
registry.register_p0_tools()       # 高优先级
registry.register_p1_tools()       # 中优先级
registry.register_p2_tools()       # 低优先级
registry.register_extended_tools() # 扩展工具
registry.register_all_tools()      # 全部注册

# 注册自定义工具
registry.register(my_tool)

# 过滤工具
filtered = registry.filter_by_permission(["bash", "read", "write"])
```

**主要方法：**

| 方法 | 说明 |
|------|------|
| `register(tool)` | 注册工具 |
| `unregister(name)` | 注销工具 |
| `get(name)` | 获取工具 |
| `has(name)` | 检查存在 |
| `get_all()` | 获取所有工具 |
| `get_schemas()` | 获取 JSON Schema |
| `filter_by_permission(allowed)` | 按权限过滤 |

### 1.4 自定义工具

**方式一：继承 BaseTool**

```python
from pyagentforge.tools import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "My custom tool"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "输入"}
        },
        "required": ["input"]
    }
    timeout = 60
    risk_level = "low"

    async def execute(self, input: str) -> str:
        return f"Processed: {input}"
```

**方式二：使用装饰器**

```python
from pyagentforge.tools import tool

@tool(
    name="greet",
    description="问候用户",
    parameters_schema={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"]
    }
)
async def greet(name: str) -> str:
    return f"Hello, {name}!"

# 注册
registry.register(greet)
```

### 1.5 Providers

**Anthropic Provider**

```python
from pyagentforge.providers import AnthropicProvider

provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=1.0,
)
```

**OpenAI Provider**

```python
from pyagentforge.providers import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4o",
    max_tokens=4096,
)
```

**统一接口 (BaseProvider)**

| 方法 | 说明 |
|------|------|
| `create_message(system, messages, tools, **kwargs)` | 创建消息 |
| `stream_message(system, messages, tools, **kwargs)` | 流式消息 |
| `count_tokens(messages)` | 计算 Token |

### 1.6 事件系统

```python
from pyagentforge.core import EventBus, EventType, get_event_bus

# 获取全局事件总线
bus = get_event_bus()

# 订阅事件
@bus.on(EventType.TOOL_START)
def on_tool_start(event):
    print(f"Tool started: {event.data}")

# 发布事件
bus.emit(Event(EventType.TOOL_START, {"tool": "bash"}))
```

### 1.7 并行 Subagent

```python
from pyagentforge.core import (
    ParallelSubagentExecutor,
    SubagentTask,
    SubagentStatus,
)

executor = ParallelSubagentExecutor(
    provider=provider,
    tool_registry=tools,
)

# 创建任务
tasks = [
    SubagentTask(id="1", prompt="Search for file X"),
    SubagentTask(id="2", prompt="Analyze code Y"),
]

# 并行执行
results = await executor.execute_all(tasks)
```

---

## 2. REST API

基础路径: `http://localhost:8000`

### 2.1 会话管理 `/api/sessions`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/sessions` | 创建会话 |
| `GET` | `/api/sessions` | 列出所有会话 |
| `GET` | `/api/sessions/{session_id}` | 获取会话详情 |
| `POST` | `/api/sessions/{session_id}/messages` | 发送消息 |
| `DELETE` | `/api/sessions/{session_id}` | 删除会话 |

**创建会话**

```http
POST /api/sessions
Content-Type: application/json

{
  "agent_id": "optional-agent-id",
  "system_prompt": "Optional system prompt"
}
```

**响应:**

```json
{
  "session_id": "uuid-string",
  "status": "created"
}
```

**发送消息**

```http
POST /api/sessions/{session_id}/messages
Content-Type: application/json

{
  "message": "Hello, Agent!",
  "stream": false
}
```

**响应:**

```json
{
  "role": "assistant",
  "content": "Hello! How can I help you today?"
}
```

### 2.2 Agent 管理 `/api/agents`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/agents` | 创建 Agent |
| `GET` | `/api/agents` | 列出所有 Agent |
| `GET` | `/api/agents/{agent_id}` | 获取 Agent 详情 |
| `PUT` | `/api/agents/{agent_id}` | 更新 Agent |
| `DELETE` | `/api/agents/{agent_id}` | 删除 Agent |

**创建 Agent**

```http
POST /api/agents
Content-Type: application/json

{
  "name": "code-assistant",
  "description": "Code review assistant",
  "system_prompt": "You are a code reviewer...",
  "allowed_tools": ["read", "glob", "grep"],
  "model": "claude-sonnet-4-20250514"
}
```

### 2.3 系统端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 服务信息 |
| `GET` | `/health` | 健康检查 |
| `GET` | `/readiness` | 就绪检查 |
| `GET` | `/docs` | Swagger 文档 |
| `GET` | `/redoc` | ReDoc 文档 |

---

## 3. WebSocket API

路径: `ws://localhost:8000/ws/{session_id}`

### 3.1 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session-123');

ws.onopen = () => {
    ws.send(JSON.stringify({ message: "Hello" }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```

### 3.2 消息格式

**发送消息:**

```json
{
  "message": "Your prompt here"
}
```

**接收事件:**

| type | 说明 | 附加字段 |
|------|------|----------|
| `start` | 开始处理 | `session_id` |
| `stream` | 流式输出 | `event` |
| `tool_start` | 工具开始 | `tool_name`, `tool_id` |
| `tool_result` | 工具结果 | `tool_id`, `result` |
| `complete` | 完成 | `text` |
| `error` | 错误 | `message` |

---

## 4. CLI 命令

```bash
# 查看版本
pyagentforge version

# 启动 API 服务
pyagentforge serve --host 0.0.0.0 --port 8000 --reload

# 初始化项目
pyagentforge init ./my-project

# 交互式对话
pyagentforge chat --model claude-sonnet-4-20250514
```

---

## 5. 内置工具

### 5.1 核心 6 工具 (builtin)

| 工具 | 说明 | 风险级别 |
|------|------|----------|
| `bash` | 执行 Shell 命令 | high |
| `read` | 读取文件 | low |
| `write` | 写入文件 | medium |
| `edit` | 编辑文件 | medium |
| `glob` | 文件模式匹配 | low |
| `grep` | 文件内容搜索 | low |

### 5.2 P0 高优先级工具

| 工具 | 说明 |
|------|------|
| `ls` | 列出目录 |
| `lsp` | LSP 语言服务 |
| `question` | 向用户提问 |
| `confirm` | 用户确认 |

### 5.3 P1 中优先级工具

| 工具 | 说明 |
|------|------|
| `codesearch` | 代码语义搜索 |
| `apply_patch` | 应用补丁 |
| `diff` | 生成差异 |
| `plan` | 计划工具 |

### 5.4 P2 低优先级工具

| 工具 | 说明 |
|------|------|
| `truncation` | 截断工具 |
| `context_compact` | 上下文压缩 |
| `invalid` | 无效工具提示 |
| `external_directory` | 外部目录 |
| `workspace` | 工作区管理 |

### 5.5 扩展工具

| 工具 | 说明 |
|------|------|
| `webfetch` | 抓取网页 |
| `websearch` | 网页搜索 |
| `todo_write` | 写入待办 |
| `todo_read` | 读取待办 |
| `multiedit` | 批量编辑 |

### 5.6 Task 工具 (Subagent)

```python
from pyagentforge.tools.builtin.task import TaskTool

task_tool = TaskTool(
    provider=provider,
    tool_registry=tools,
)
```

---

## 6. Skills 系统

### 6.1 Skill 结构

```
data/skills/
└── my-skill/
    └── SKILL.md
```

**SKILL.md 格式:**

```markdown
---
name: code-review
description: Code review best practices
triggers:
  - code review
  - review code
dependencies:
  - git-basics
---

# Code Review Skill

Your skill content here...
```

### 6.2 SkillLoader

```python
from pyagentforge.skills import SkillLoader, SkillParser, SkillRegistry

loader = SkillLoader(skills_dir=Path("./data/skills"))
loader.load_all()

# 获取技能内容
content = loader.get_skill_content("code-review")

# 匹配技能
matched = loader.match_skill("please review my code")

# 获取依赖
deps = loader.get_dependencies("code-review")
```

### 6.3 SkillRegistry

```python
from pyagentforge.skills import SkillRegistry

registry = SkillRegistry(loader)

# 检查加载状态
registry.is_loaded("code-review")

# 标记已加载
registry.mark_loaded("code-review")
```

### 6.4 SkillTool

将技能加载作为工具提供给 Agent：

```python
from pyagentforge.skills.tool import SkillTool
from pyagentforge.skills import SkillLoader

loader = SkillLoader()
loader.load_all()

skill_tool = SkillTool(loader)
registry.register(skill_tool)
```

---

## 快速开始示例

### Python SDK

```python
import asyncio
from pyagentforge import AgentEngine, ToolRegistry
from pyagentforge.providers import AnthropicProvider

async def main():
    # 初始化
    provider = AnthropicProvider(api_key="your-key")
    tools = ToolRegistry()
    tools.register_builtin_tools()

    engine = AgentEngine(provider=provider, tool_registry=tools)

    # 运行
    result = await engine.run("List files in current directory")
    print(result)

asyncio.run(main())
```

### REST API

```bash
# 创建会话
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

# 发送消息
curl -X POST http://localhost:8000/api/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/my-session');
ws.onopen = () => ws.send(JSON.stringify({message: "Hello"}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```
