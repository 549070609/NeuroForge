# PyAgentForge 配置与协议支持 API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本文档详细说明 PyAgentForge 的配置系统和协议支持，包括 Settings、PluginConfig、MCP 和 LSP。

---

## 目录

- [1. Settings - 应用配置](#1-settings---应用配置)
- [2. PluginConfig - 插件配置](#2-pluginconfig---插件配置)
- [3. 环境变量配置](#3-环境变量配置)
- [4. MCP 协议支持](#4-mcp-协议支持)
- [5. LSP 协议支持](#5-lsp-协议支持)
- [6. REST API 接口](#6-rest-api-接口)

---

## 1. Settings - 应用配置

**位置:** `pyagentforge.config.settings.Settings`

使用 pydantic-settings 管理应用配置，支持环境变量和 .env 文件。

### 1.1 配置类定义

```python
class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
```

---

### 1.2 LLM 配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `anthropic_api_key` | `str` | `""` | `ANTHROPIC_API_KEY` | Anthropic API Key |
| `openai_api_key` | `str` | `""` | `OPENAI_API_KEY` | OpenAI API Key |
| `default_model` | `str` | `"claude-sonnet-4-20250514"` | `DEFAULT_MODEL` | 默认使用的模型 |
| `max_tokens` | `int` | `4096` | `MAX_TOKENS` | 最大输出 Token |
| `temperature` | `float` | `1.0` | `TEMPERATURE` | 温度参数 (0.0-2.0) |

---

### 1.3 服务配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `host` | `str` | `"0.0.0.0"` | `HOST` | 服务监听地址 |
| `port` | `int` | `8000` | `PORT` | 服务监听端口 |
| `debug` | `bool` | `False` | `DEBUG` | 调试模式 |

---

### 1.4 数据库配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `database_url` | `str` | `"sqlite+aiosqlite:///./data/pyagentforge.db"` | `DATABASE_URL` | 数据库连接 URL |

---

### 1.5 安全配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `jwt_secret_key` | `str` | `"change-me-in-production"` | `JWT_SECRET_KEY` | JWT 签名密钥 |
| `jwt_algorithm` | `str` | `"HS256"` | `JWT_ALGORITHM` | JWT 算法 |
| `access_token_expire_minutes` | `int` | `30` | `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 过期时间 |

---

### 1.6 存储配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `skills_dir` | `Path` | `./data/skills` | `SKILLS_DIR` | 技能目录 |
| `commands_dir` | `Path` | `./data/commands` | `COMMANDS_DIR` | 命令目录 |
| `data_dir` | `Path` | `./data` | `DATA_DIR` | 数据目录 |

---

### 1.7 日志配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `log_level` | `str` | `"INFO"` | `LOG_LEVEL` | 日志级别 |
| `log_format` | `str` | `"json"` | `LOG_FORMAT` | 日志格式 (json/text) |

---

### 1.8 Agent 配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `default_timeout` | `int` | `120` | `DEFAULT_TIMEOUT` | 默认超时时间(秒) |
| `tool_timeout` | `int` | `60` | `TOOL_TIMEOUT` | 工具执行超时(秒) |
| `max_subagent_depth` | `int` | `3` | `MAX_SUBAGENT_DEPTH` | 子代理最大递归深度 |
| `max_context_messages` | `int` | `100` | `MAX_CONTEXT_MESSAGES` | 最大上下文消息数 |
| `max_tool_output_length` | `int` | `50000` | `MAX_TOOL_OUTPUT_LENGTH` | 工具输出最大长度 |

---

### 1.9 上下文压缩配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `compaction_enabled` | `bool` | `True` | `COMPACTION_ENABLED` | 是否启用上下文压缩 |
| `compaction_reserve_tokens` | `int` | `8000` | `COMPACTION_RESERVE_TOKENS` | 压缩时预留的 tokens |
| `compaction_keep_recent_tokens` | `int` | `4000` | `COMPACTION_KEEP_RECENT_TOKENS` | 保留最近消息的 tokens |
| `compaction_threshold` | `float` | `0.8` | `COMPACTION_THRESHOLD` | 触发压缩的阈值 |
| `max_context_tokens` | `int` | `200000` | `MAX_CONTEXT_TOKENS` | 最大上下文 tokens |

---

### 1.10 思考级别配置

| 参数 | 类型 | 默认值 | 环境变量 | 说明 |
|------|------|--------|----------|------|
| `default_thinking_level` | `str` | `"off"` | `DEFAULT_THINKING_LEVEL` | 默认思考级别 |
| `thinking_budget_tokens` | `int \| None` | `None` | `THINKING_BUDGET_TOKENS` | 思考 token 预算 |

---

### 1.11 使用示例

```python
from pyagentforge.config.settings import get_settings

# 获取配置单例
settings = get_settings()

# 访问配置值
print(settings.default_model)
print(settings.max_tokens)
print(settings.skills_dir)

# 确保目录存在
settings.ensure_directories()
```

---

## 2. PluginConfig - 插件配置

**位置:** `pyagentforge.config.plugin_config.PluginConfig`

管理插件系统的配置。

### 2.1 配置类定义

```python
@dataclass
class PluginConfig:
    """插件配置"""
    preset: str = "minimal"  # minimal, standard, full
    enabled: List[str] = field(default_factory=list)
    disabled: List[str] = field(default_factory=list)
    plugin_dirs: List[str] = field(default_factory=lambda: ["plugins"])
    config: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `preset` | `str` | `"minimal"` | 预设名称 (minimal/standard/full) |
| `enabled` | `List[str]` | `[]` | 额外启用的插件 ID |
| `disabled` | `List[str]` | `[]` | 禁用的插件 ID |
| `plugin_dirs` | `List[str]` | `["plugins"]` | 插件搜索目录 |
| `config` | `Dict` | `{}` | 插件特定配置 |

---

### 2.2 类方法

#### `from_yaml()`

```python
@classmethod
def from_yaml(cls, path: str) -> "PluginConfig"
```

从 YAML 文件加载配置。

```python
config = PluginConfig.from_yaml("config.yaml")
```

**YAML 文件格式:**

```yaml
preset: standard
enabled:
  - tools.web_tools
  - middleware.thinking
disabled:
  - protocol.lsp
plugin_dirs:
  - plugins
  - custom_plugins
config:
  middleware.compaction:
    threshold: 0.75
  middleware.thinking:
    level: medium
```

---

#### `from_dict()`

```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig"
```

从字典创建配置。

---

#### `to_dict()`

```python
def to_dict(self) -> Dict[str, Any]
```

转换为字典。

---

### 2.3 实例方法

#### `get_effective_plugins()`

```python
def get_effective_plugins(self) -> List[str]
```

获取最终启用的插件列表。

**返回值:** `List[str]` - 有效插件 ID 列表

**计算逻辑:** `预设 + enabled - disabled`

---

#### `get_plugin_config()`

```python
def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]
```

获取特定插件的配置。

```python
compaction_config = config.get_plugin_config("middleware.compaction")
threshold = compaction_config.get("threshold", 0.8)
```

---

### 2.4 预设配置

| 预设 | 说明 | 包含的插件 |
|------|------|-----------|
| `minimal` | 最小化配置 | 无 |
| `standard` | 标准配置 | tools.code_tools, tools.file_tools, middleware.compaction, integration.events |
| `full` | 完整配置 | 所有插件 |

---

### 2.5 使用示例

```python
from pyagentforge.config.plugin_config import PluginConfig, load_preset

# 方法 1: 使用预设
config = load_preset("standard")

# 方法 2: 从 YAML 加载
config = PluginConfig.from_yaml("config.yaml")

# 方法 3: 从字典创建
config = PluginConfig.from_dict({
    "preset": "standard",
    "enabled": ["tools.web_tools"],
    "config": {
        "middleware.compaction": {
            "threshold": 0.75
        }
    }
})

# 获取有效插件
plugins = config.get_effective_plugins()

# 获取插件特定配置
plugin_cfg = config.get_plugin_config("middleware.compaction")
```

---

## 3. 环境变量配置

### 3.1 .env 文件示例

```env
# LLM 配置
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
DEFAULT_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=4096
TEMPERATURE=1.0

# 服务配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./data/pyagentforge.db

# 安全配置
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 存储配置
SKILLS_DIR=./data/skills
COMMANDS_DIR=./data/commands
DATA_DIR=./data

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json

# Agent 配置
DEFAULT_TIMEOUT=120
TOOL_TIMEOUT=60
MAX_SUBAGENT_DEPTH=3

# 上下文压缩配置
COMPACTION_ENABLED=true
COMPACTION_THRESHOLD=0.8
MAX_CONTEXT_TOKENS=200000

# 思考级别配置
DEFAULT_THINKING_LEVEL=off
```

### 3.2 环境变量命名规则

- 环境变量名称不区分大小写
- 使用下划线分隔单词
- 自动从 `.env` 文件加载

---

## 4. MCP 协议支持

### 4.1 概述

MCP (Model Context Protocol) 是一种用于暴露工具和资源的协议。PyAgentForge 支持作为 MCP 服务端和客户端。

---

### 4.2 MCP 协议类型

**位置:** `pyagentforge.mcp.server`

#### MCPRequest

```python
class MCPRequest(BaseModel):
    """MCP 请求"""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
```

#### MCPResponse

```python
class MCPResponse(BaseModel):
    """MCP 响应"""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
```

#### MCPServerInfo

```python
class MCPServerInfo(BaseModel):
    """MCP 服务器信息"""
    name: str = "PyAgentForge"
    version: str = "1.0.0"
```

#### MCPToolInfo

```python
class MCPToolInfo(BaseModel):
    """MCP 工具信息"""
    name: str
    description: str
    inputSchema: dict[str, Any]
```

---

### 4.3 MCPServer

**位置:** `pyagentforge.mcp.server.MCPServer`

作为 MCP 服务端暴露工具给外部调用。

#### 构造函数

```python
def __init__(
    self,
    tool_registry: ToolRegistry,
    server_info: MCPServerInfo | None = None,
) -> None
```

---

#### `handle_request()`

```python
async def handle_request(self, request: MCPRequest) -> MCPResponse
```

处理 MCP 请求。

**支持的方法:**
- `initialize` - 初始化连接
- `tools/list` - 列出可用工具
- `tools/call` - 调用工具
- `ping` - 心跳检测

---

#### 使用示例

```python
from pyagentforge.mcp.server import MCPServer, MCPRequest, MCPServerInfo
from pyagentforge.tools.registry import ToolRegistry

# 创建工具注册表
registry = ToolRegistry()
# ... 注册工具

# 创建 MCP 服务器
server = MCPServer(
    tool_registry=registry,
    server_info=MCPServerInfo(
        name="MyAgent",
        version="1.0.0"
    )
)

# 处理请求
request = MCPRequest(
    id=1,
    method="tools/list",
    params={}
)
response = await server.handle_request(request)
print(response.result)
```

---

### 4.4 MCPResource

```python
class MCPResource(BaseModel):
    """MCP 资源"""
    uri: str
    name: str
    description: str | None = None
    mimeType: str = "text/plain"
```

---

### 4.5 MCPResourceManager

```python
class MCPResourceManager:
    """MCP 资源管理器"""

    def register(self, resource: MCPResource) -> None
    def list_resources(self) -> list[MCPResource]
    def get_resource(self, uri: str) -> MCPResource | None
```

---

## 5. LSP 协议支持

### 5.1 概述

LSP (Language Server Protocol) 提供代码智能功能，如补全、跳转定义、诊断等。

---

### 5.2 LSPClient

**位置:** `pyagentforge.lsp.client.LSPClient`

通过 stdio 与 LSP 服务器通信。

#### 构造函数

```python
def __init__(
    self,
    config: LSPServerConfig,
    workspace_root: str | Path | None = None,
) -> None
```

**LSPServerConfig 包含:**
- `language` - 语言 ID
- `command` - 启动命令
- `initialization_options` - 初始化选项

---

#### 生命周期方法

##### `start()`

```python
async def start(self) -> bool
```

启动 LSP 服务器进程。

---

##### `initialize()`

```python
async def initialize(self) -> bool
```

初始化 LSP 连接。

---

##### `shutdown()`

```python
async def shutdown(self) -> None
```

关闭 LSP 连接。

---

#### 文档同步方法

##### `did_open()`

```python
async def did_open(
    self,
    file_path: str | Path,
    language_id: str | None = None,
    version: int = 1,
) -> None
```

通知服务器文档已打开。

---

##### `did_close()`

```python
async def did_close(self, file_path: str | Path) -> None
```

通知服务器文档已关闭。

---

##### `did_change()`

```python
async def did_change(
    self,
    file_path: str | Path,
    content: str,
    version: int = 2,
) -> None
```

通知服务器文档已更改。

---

#### 语言功能方法

##### `goto_definition()`

```python
async def goto_definition(
    self,
    file_path: str | Path,
    position: Position,
) -> list[Location | LocationLink]
```

跳转到定义。

---

##### `find_references()`

```python
async def find_references(
    self,
    file_path: str | Path,
    position: Position,
    include_declaration: bool = True,
) -> list[Location]
```

查找引用。

---

##### `hover()`

```python
async def hover(
    self,
    file_path: str | Path,
    position: Position,
) -> Hover | None
```

获取悬停信息。

---

##### `completion()`

```python
async def completion(
    self,
    file_path: str | Path,
    position: Position,
    trigger_kind: int = 1,
    trigger_character: str | None = None,
) -> CompletionList
```

获取补全列表。

---

##### `document_symbols()`

```python
async def document_symbols(
    self,
    file_path: str | Path,
) -> list[DocumentSymbol | SymbolInformation]
```

获取文档符号。

---

##### `rename()`

```python
async def rename(
    self,
    file_path: str | Path,
    position: Position,
    new_name: str,
) -> dict[str, Any] | None
```

重命名符号。

---

##### `formatting()`

```python
async def formatting(
    self,
    file_path: str | Path,
    tab_size: int = 4,
    insert_spaces: bool = True,
) -> list[dict[str, Any]]
```

格式化文档。

---

### 5.3 使用示例

```python
from pathlib import Path
from pyagentforge.lsp.client import LSPClient
from pyagentforge.lsp.protocol import LSPServerConfig, Position

# 配置 LSP 服务器
config = LSPServerConfig(
    language="python",
    command=["pylsp"],
)

# 创建客户端
client = LSPClient(
    config=config,
    workspace_root=Path.cwd(),
)

# 启动并初始化
await client.start()
await client.initialize()

# 打开文件
file_path = Path("src/main.py")
await client.did_open(file_path, language_id="python")

# 获取补全
position = Position(line=10, character=5)
completions = await client.completion(file_path, position)
for item in completions.items:
    print(f"{item.label}: {item.detail}")

# 跳转到定义
definition = await client.goto_definition(file_path, position)
for loc in definition:
    print(f"Definition at: {loc.uri}")

# 获取悬停信息
hover_info = await client.hover(file_path, position)
if hover_info:
    print(hover_info.contents)

# 关闭
await client.shutdown()
```

---

### 5.4 LSPManager

**位置:** `pyagentforge.lsp.manager.LSPManager`

管理多个语言的 LSP 客户端。

```python
class LSPManager:
    """LSP 管理器"""

    async def get_client(self, language: str) -> LSPClient | None
    async def start_all(self) -> None
    async def stop_all(self) -> None
```

---

## 6. REST API 接口

### 6.1 FastAPI 应用

**位置:** `pyagentforge.api.app`

```python
from pyagentforge.api.app import create_app, app

# 创建应用
app = create_app()

# 或使用默认实例
from pyagentforge.api.app import app
```

---

### 6.2 应用配置

```python
app = FastAPI(
    title="PyAgentForge",
    description="通用型 AI Agent 服务底座",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

---

### 6.3 API 端点

#### 健康检查

```
GET /health
```

**响应:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

#### 就绪检查

```
GET /readiness
```

**响应:**
```json
{
  "status": "ready",
  "version": "1.0.0"
}
```

---

#### 根路径

```
GET /
```

**响应:**
```json
{
  "name": "PyAgentForge",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

### 6.4 Session API

**路由前缀:** `/api/sessions`

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/` | 创建会话 |
| GET | `/{session_id}` | 获取会话 |
| DELETE | `/{session_id}` | 删除会话 |
| POST | `/{session_id}/messages` | 发送消息 |
| GET | `/{session_id}/messages` | 获取消息历史 |

---

### 6.5 Agent API

**路由前缀:** `/api/agents`

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/run` | 运行 Agent |
| POST | `/stream` | 流式运行 Agent |

---

### 6.6 WebSocket API

**路由前缀:** `/ws`

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/session');

// 发送消息
ws.send(JSON.stringify({
  type: 'message',
  content: 'Hello, Agent!'
}));

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

---

### 6.7 启动服务

```python
import uvicorn
from pyagentforge.api.app import app

# 启动服务
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8000,
)
```

或使用命令行:

```bash
uvicorn pyagentforge.api.app:app --host 0.0.0.0 --port 8000
```

---

### 6.8 API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 相关文档

- [核心 API 文档](./01-core-api.md)
- [Provider API 文档](./02-providers-api.md)
- [工具系统 API 文档](./03-tools-api.md)
- [命令与技能系统 API 文档](./04-commands-skills-api.md)
- [插件系统 API 文档](./05-plugin-system-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 初始版本，配置与协议支持 |

---

*本文档由 Claude Code 自动生成*
