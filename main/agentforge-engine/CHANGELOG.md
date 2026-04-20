# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-04-20

### 💥 Breaking Changes — Hard Cutover

Removed every historical compatibility entry point. The SDK surface is now
restricted to `kernel`, `plugin(s)`, `tools/builtin`, `agents`, `config`,
`workflow`, `client`, and `foundation`.

The agent-description stack (`building`, `prompts`, `skills`, `commands`) was
merged into `pyagentforge.agents.*` so that everything describing *what an
agent is* lives in one place. Top-level `pyagentforge.building`,
`pyagentforge.prompts`, `pyagentforge.skills` and `pyagentforge.commands`
packages no longer exist — import from `pyagentforge.agents.building`,
`pyagentforge.agents.prompts`, `pyagentforge.agents.skills` and
`pyagentforge.agents.commands` instead.

Deleted top-level packages:

- `pyagentforge.foundation` — empty "base layer" declaration.
  - `foundation.config.env_parser` → `pyagentforge.config.env_parser`
    (also re-exported from `pyagentforge.config`)
  - `foundation.session.session_key` →
    `pyagentforge.plugins.integration.persistence.session_key`
    (also re-exported as `from pyagentforge.plugins.integration.persistence import SessionKey`)
- `pyagentforge.engine` — empty reserved namespace.
- `pyagentforge.providers` / `pyagentforge.adapters` — unused after v4.0 LLM
  client unification.
- `pyagentforge.compat` (incl. `compat.v2`) — v2 import shims.
- `pyagentforge.api` — REST API has moved to `main/Service`.
- `pyagentforge.models` — ORM models had no in-tree consumer.
- `pyagentforge.core` — split into `kernel/`, `plugins/integration/*`, and
  `plugins/middleware/*` per responsibility (see relocation table below).

Deleted duplicate files:

- `pyagentforge.kernel.base_tool` — use `pyagentforge.tools.base.BaseTool`.
- `pyagentforge.kernel.core_tools` — the six canonical tools now live under
  `pyagentforge.tools.builtin` together with `register_core_tools`.
- `pyagentforge.plugins.tools.file_tools` / `plugins.tools.interact_tools` /
  `plugins.tools.web_tools` — these wrapper plugins merely duplicated tools
  already provided by `pyagentforge.tools.builtin` (`LsTool`, `TruncationTool`,
  `QuestionTool`, `ConfirmTool`, `BatchTool`, `WebFetchTool`, `WebSearchTool`).
  `plugins/tools/` now only hosts genuinely pluggable/optional tooling
  (`ast_grep`, `python_ast`, `background_tools`, `call_agent`). The `standard`
  and `full` presets no longer list these plugin IDs.
- `pyagentforge.core.engine|message|executor|context` — canonical
  implementations are `pyagentforge.kernel.engine|message|executor|context`.
- `pyagentforge.core.events|model_registry|thinking|parallel|failover|persistence|context_aware|compaction`
  — shim re-exports removed; import from canonical locations directly.

### 🔁 Migration

```python
# Before                                               # After
from pyagentforge.kernel.base_tool import ...          from pyagentforge.tools.base import ...
from pyagentforge.kernel.core_tools import ...         from pyagentforge.tools.builtin import ...
from pyagentforge.core.message import ...              from pyagentforge.kernel.message import ...
from pyagentforge.core.executor import ...             from pyagentforge.kernel.executor import ...
from pyagentforge.core.engine import ...               from pyagentforge.kernel.engine import ...
from pyagentforge.core.context import ContextManager   from pyagentforge.kernel.context import ContextManager
from pyagentforge.core.background_manager import ...   from pyagentforge.kernel.background_manager import ...
from pyagentforge.core.concurrency_manager import ...  from pyagentforge.kernel.concurrency_manager import ...
from pyagentforge.core.cleanup import ...              from pyagentforge.kernel.cleanup import ...
from pyagentforge.core.category import ...             from pyagentforge.plugins.integration.category_system.category import ...
from pyagentforge.core.category_registry import ...    from pyagentforge.plugins.integration.category_system.category_registry import ...
from pyagentforge.core.llm_classifier import ...       from pyagentforge.plugins.integration.classifiers.llm_classifier import ...
from pyagentforge.core.semantic_classifier import ...  from pyagentforge.plugins.integration.classifiers.semantic_classifier import ...
from pyagentforge.core.knowledge_injector import ...   from pyagentforge.plugins.integration.knowledge_injection.knowledge_injector import ...
from pyagentforge.core.ralph_loop import ...           from pyagentforge.plugins.integration.ralph_loop.ralph_loop import ...
from pyagentforge.core.todo_tracker import ...         from pyagentforge.plugins.integration.todo_enforcer.todo_tracker import ...
from pyagentforge.core.context_monitor import ...      from pyagentforge.plugins.middleware.context_lifecycle.context_monitor import ...
from pyagentforge.core.context_usage import ...        from pyagentforge.plugins.middleware.context_lifecycle.context_usage import ...
from pyagentforge.core.error_recovery import ...       from pyagentforge.plugins.middleware.error_recovery.error_recovery import ...
from pyagentforge.core.compaction import Compactor     from pyagentforge.plugins.middleware.compaction.compaction import Compactor
from pyagentforge.compat.v2 import EventBus            from pyagentforge.plugins.integration.events.events import EventBus
from pyagentforge.api import create_app                # Removed — use Service/gateway
```

### 🧭 Workspace Reorganization (P2.4 / P2.5)

- `main/perception/` 已并入 SDK，新位置：
  `pyagentforge.plugins.integration.perception.*`（原脚本式 `sys.path` 注入改为标准相对导入）。
- `main/Agent/`、`main/Long-memory/long-memory/`、`main/Long-memory/embeddings/`
  均补齐了 `pyproject.toml`；历史的 `setup.py` / `pytest.ini` 已删除，相关配置
  合并进各子包的 `pyproject.toml`。
- 仓库根新增 `pyproject.toml`：统一 `testpaths` / `pythonpath` / `importmode`，
  支持在仓库根一条命令 `pytest` 跑完 SDK、Service、Agent、Long-memory 全部用例。
- `pyagentforge.plugins.integration.todo_continuation` / `task_system` 的
  `from pyagentforge.plugin.base import BasePlugin` 修正为
  `from pyagentforge.plugin.base import Plugin as BasePlugin`（`Plugin` 才是
  规范类名，`BasePlugin` 仅作向后兼容别名）。

## [3.0.0] - 2026-02-17

### 💥 Breaking Changes

#### Architecture Migration
- **Four-Layer Architecture** - Migrated from flat to hierarchical structure
  - Foundation Layer (Session Key, Config)
  - Engine Layer (reserved)
  - Middleware Layer (Pipeline, Telemetry)
  - Capabilities Layer (Channels)

- **Import Path Changes**
  ```python
  # v2.x
  from pyagentforge.core.events import EventBus

  # v3.0
  from pyagentforge.plugins.integration.events import EventBus
  # or use compat layer
  from pyagentforge.compat.v2 import EventBus
  ```

### ✨ Added

#### Foundation Layer
- **Session Key System** - Unified session identifier
  - Format: `{channel}:{conversation_id}[:{sub_key}]`
  - Multi-level sub-keys support
  - Hashable and comparable
  - Empty value validation

- **Environment Variable Parser** - Secure configuration
  - Syntax: `${VAR}` and `${VAR:-default}`
  - Recursive resolution
  - Circular dependency detection

#### Capabilities Layer

- **Channel System** - Unified message channel protocol
  - `BaseChannel` abstract class
  - `ChannelStatus` enum
  - `ChannelMessage` and `SendMessageResult`

- **WebChat Channel** - Web client integration
  - Session management with limits/timeout
  - WebSocket real-time push
  - Message queue polling
  - Streaming message support
  - Auto expired session cleanup

- **Webhook Channel** - External webhook receiver
  - Multiple path handlers
  - HMAC-SHA256 signature verification
  - Sync/async handler support
  - Auto message emission

#### Middleware Layer

- **Middleware Pipeline** - Standardized execution
  - `MiddlewareContext` with session/messages/tools
  - `BaseMiddleware` with priority
  - `MiddlewarePipeline` for chain execution

- **Telemetry Middleware** - Unified metrics
  - Request/token tracking
  - Session-level metrics
  - Latency percentiles (P50/P95/P99)
  - JSON/Prometheus export
  - EventBus/ProviderPool integration

#### Automation Layer

- **Automation System** - Built-in automation
  - Trigger types: TIME/EVENT/WEBHOOK
  - `AutomationTask` with tracking
  - `AutomationManager` for cron/webhook
  - EventBus integration
  - Conditional event filtering

### 🔧 Changed

- **Session Management** - Refactored to Session Key system
- **Provider Pool** - Added circuit breaker + weighted load balancing
- **Plugin Types** - Expanded from 7 to 10 (+Channel, +Automation)

### 🐛 Fixed

- SessionKey.parse() empty value validation
- Circular import in compat/v2/failover.py

### 📚 Documentation

- Complete v3.0 architecture design
- Migration guide with examples
- 7 comprehensive feature examples
- Phase completion reports (0-5)

### 🧪 Testing

- **Total Tests**: 208
- **Pass Rate**: 100%
- **Coverage**: ~97%

### 🔄 Migration Support

- Backward compatibility via `pyagentforge.compat.v2`
- Gradual migration path supported
- See `Docs/PyAgentForge/v3.0-migration-guide.md` for details

---

## [2.0.0] - 2026-02-17

### 💥 Breaking Changes

#### 移除向后兼容层
- **移除 v1.x 旧 API 的向后兼容导入**
  - 不再从顶层 `pyagentforge` 导出以下 v1.x API：
    - `ParallelSubagentExecutor`, `SubagentStatus` → 使用 `pyagentforge.plugins.integration.parallel_executor`
    - `SkillLoader` → 使用 `pyagentforge.plugins.skills.skill_loader`
    - `get_supported_models` → 使用 `pyagentforge.plugins.providers.*`
    - `ModelRegistry`, `ModelConfig`, `get_registry` → 使用 `pyagentforge.core.model_registry`
    - `ThinkingLevel`, `create_thinking_config` → 使用 `pyagentforge.core.thinking`

#### 迁移指南

**v1.x (旧) → v2.0 (新)**

```python
# ❌ v1.x - 不再支持
from pyagentforge import ParallelSubagentExecutor, SkillLoader

# ✅ v2.0 - 正确用法
from pyagentforge.plugins.integration.parallel_executor import ParallelSubagentExecutor
from pyagentforge.plugins.skills.skill_loader import SkillLoader
```

**或者从子模块直接导入：**

```python
# ✅ 直接从核心模块导入（仍然可用）
from pyagentforge.core.model_registry import ModelRegistry, ModelConfig
from pyagentforge.core.thinking import ThinkingLevel, create_thinking_config
from pyagentforge.core.parallel import ParallelSubagentExecutor
from pyagentforge.skills.loader import SkillLoader
```

### ✨ Added

#### 插件化架构 (v2.0)
- **核心系统** (`pyagentforge.kernel`)
  - `AgentEngine` - Agent 执行引擎
  - `ContextManager` - 上下文管理器
  - `ToolExecutor` - 工具执行器
  - `ToolRegistry` - 工具注册表
  - 统一消息类型: `Message`, `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `ProviderResponse`

- **插件系统** (`pyagentforge.plugin`)
  - `Plugin` - 插件基类
  - `PluginMetadata` - 插件元数据
  - `PluginContext` - 插件上下文
  - `PluginManager` - 插件管理器
  - `HookType` - 钩子类型枚举

- **工厂函数**
  - `create_engine()` - 创建完整配置的 AgentEngine
  - `create_minimal_engine()` - 创建最小化引擎

#### 插件生态
- **Providers** (模型提供商)
  - Anthropic Claude (支持 thinking 模式)
  - OpenAI GPT
  - Google Gemini

- **Middleware** (中间件)
  - `thinking` - 思考级别控制
  - `failover` - 故障转移与重试
  - `compaction` - 上下文压缩

- **Integration** (集成功能)
  - `parallel_executor` - 并行子代理执行器
  - `persistence` - 会话持久化
  - `context_aware` - 上下文感知
  - `events` - 事件系统

- **Interface** (接口层)
  - `rest_api` - RESTful API
  - `websocket` - WebSocket 实时通信

- **Protocol** (协议支持)
  - `mcp_client` - MCP 客户端
  - `mcp_server` - MCP 服务器
  - `lsp` - LSP 语言服务协议

- **Skills & Tools**
  - `skill_loader` - Skill 动态加载器
  - `file_tools` - 文件操作工具集
  - `web_tools` - 网络请求工具集
  - `interact_tools` - 用户交互工具

### 🔧 Changed

- **版本号统一**
  - `pyproject.toml` 版本从 `1.0.0` 升级到 `2.0.0`
  - 与 `pyagentforge.__version__` 保持一致

- **测试配置优化**
  - 移除 `filterwarnings = ["ignore::DeprecationWarning"]`
  - 现在测试时会正确显示弃用警告

### 🗑️ Removed

- **向后兼容层**
  - 删除 `_deprecated_import()` 函数（未实际使用）
  - 删除 v1.x 旧模块的兼容性导入
  - 从 `__all__` 列表中移除旧 API

### 📚 Documentation

- 新增 `CHANGELOG.md` 记录版本变更
- 更新项目版本至 v2.0.0

---

## [1.0.0] - 2026-01-XX (假设)

### Added
- 初始版本发布
- 基础 Agent 框架
- 多模型支持 (OpenAI, Anthropic, Google)
- 核心工具集 (bash, read, write, edit, glob, grep)
- Command 系统 + `!`cmd`` 语法
- 并行子代理 (ParallelSubAgent)
- 上下文压缩功能

---

## 版本说明

- **[2.0.0]** - 插件化架构重构，移除 v1.x 向后兼容
- **[1.0.0]** - 初始版本

---

> **Note**: 从 v1.x 升级到 v2.0 的用户，请参考上述迁移指南更新导入语句。核心模块 (`pyagentforge.core.*`, `pyagentforge.skills.*`) 仍然可用，只是不再从顶层 `pyagentforge` 直接导出。
