# Migration Guide: v1.x → v2.0

本文档提供从 PyAgentForge v1.x 迁移到 v2.0 的详细指南。

## 📋 目录

- [重大变更概览](#重大变更概览)
- [API 迁移对照表](#api-迁移对照表)
- [逐步迁移指南](#逐步迁移指南)
- [常见问题](#常见问题)

---

## 重大变更概览

### 🎯 核心变化

v2.0 引入了**插件化架构**，将功能模块化到独立插件中。同时移除了 v1.x 的向后兼容层。

**主要影响：**
- ❌ 不再从顶层 `pyagentforge` 导出旧 API
- ✅ 核心模块 (`pyagentforge.core.*`) 仍然可用
- ✅ 新增插件系统 (`pyagentforge.plugins.*`)
- ✅ 新增工厂函数 (`create_engine`, `create_minimal_engine`)

---

## API 迁移对照表

### 1. 顶层导入变更

| v1.x (已移除) | v2.0 (推荐) | 说明 |
|--------------|------------|------|
| `from pyagentforge import ParallelSubagentExecutor` | `from pyagentforge.plugins.integration.parallel_executor import ParallelSubagentExecutor` | 并行子代理 |
| `from pyagentforge import SubagentStatus` | `from pyagentforge.plugins.integration.parallel_executor import SubagentStatus` | 子代理状态 |
| `from pyagentforge import SkillLoader` | `from pyagentforge.plugins.skills.skill_loader import SkillLoader` | Skill 加载器 |
| `from pyagentforge import create_provider` | `from pyagentforge.plugins.providers.<provider> import <Provider>` | 提供商工厂 |
| `from pyagentforge import get_supported_models` | `from pyagentforge.core.model_registry import get_supported_models` | 模型列表 |
| `from pyagentforge import ModelRegistry` | `from pyagentforge.core.model_registry import ModelRegistry` | 模型注册表 |
| `from pyagentforge import ModelConfig` | `from pyagentforge.core.model_registry import ModelConfig` | 模型配置 |
| `from pyagentforge import ProviderType` | `from pyagentforge.core.model_registry import ProviderType` | 提供商类型 |
| `from pyagentforge import ThinkingLevel` | `from pyagentforge.core.thinking import ThinkingLevel` | 思考级别 |
| `from pyagentforge import create_thinking_config` | `from pyagentforge.core.thinking import create_thinking_config` | 思考配置 |

### 2. 替代导入方式

所有旧 API 仍然可以通过子模块访问：

```python
# ✅ 方式 1: 从插件导入 (推荐)
from pyagentforge.plugins.integration.parallel_executor import ParallelSubagentExecutor
from pyagentforge.plugins.skills.skill_loader import SkillLoader

# ✅ 方式 2: 从核心模块导入 (仍然可用)
from pyagentforge.core.model_registry import ModelRegistry, ModelConfig, ProviderType
from pyagentforge.core.thinking import ThinkingLevel, create_thinking_config
from pyagentforge.core.parallel import ParallelSubagentExecutor, SubagentStatus
from pyagentforge.skills.loader import SkillLoader
```

---

## 逐步迁移指南

### 步骤 1: 更新导入语句

**Before (v1.x):**
```python
from pyagentforge import (
    ParallelSubagentExecutor,
    SkillLoader,
    ModelRegistry,
    ThinkingLevel,
    create_thinking_config,
)
```

**After (v2.0):**
```python
# 选项 1: 从插件导入
from pyagentforge.plugins.integration.parallel_executor import ParallelSubagentExecutor
from pyagentforge.plugins.skills.skill_loader import SkillLoader

# 选项 2: 从核心模块导入
from pyagentforge.core.model_registry import ModelRegistry
from pyagentforge.core.thinking import ThinkingLevel, create_thinking_config
```

### 步骤 2: 更新提供商创建

**Before (v1.x):**
```python
from pyagentforge import create_provider

provider = create_provider("anthropic", api_key="sk-...")
```

**After (v2.0):**
```python
from pyagentforge.plugins.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-...")
```

### 步骤 3: 使用新的工厂函数

**Before (v1.x):**
```python
from pyagentforge import AgentEngine, ToolRegistry
from pyagentforge import create_provider

provider = create_provider("anthropic", api_key="sk-...")
tools = ToolRegistry()
tools.register_builtin_tools()

engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
)
```

**After (v2.0) - 推荐:**
```python
from pyagentforge import create_engine
from pyagentforge.plugins.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-...")

# 自动注册核心工具
engine = await create_engine(
    provider=provider,
    working_dir="./",
)
```

**After (v2.0) - 最小化:**
```python
from pyagentforge import create_minimal_engine
from pyagentforge.plugins.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-...")
engine = create_minimal_engine(provider=provider, working_dir="./")
```

### 步骤 4: 更新并行子代理使用

**Before (v1.x):**
```python
from pyagentforge import ParallelSubagentExecutor, SubagentStatus

executor = ParallelSubagentExecutor(
    provider=provider,
    max_concurrent=3,
)
results = await executor.execute_subagents(tasks)
```

**After (v2.0):**
```python
from pyagentforge.plugins.integration.parallel_executor import (
    ParallelSubagentExecutor,
    SubagentStatus,
)

# 用法相同
executor = ParallelSubagentExecutor(
    provider=provider,
    max_concurrent=3,
)
results = await executor.execute_subagents(tasks)
```

---

## 常见问题

### Q1: 我必须更改代码吗？

**A:** 取决于你的导入方式：

- ✅ **无需修改**：如果你已经从子模块导入（如 `from pyagentforge.core.xxx import ...`）
- ❌ **需要修改**：如果你从顶层导入旧 API（如 `from pyagentforge import SkillLoader`）

### Q2: 旧代码会立即报错吗？

**A:** 是的。v2.0 移除了向后兼容层，导入不存在的 API 会触发 `ImportError`。

```python
# ❌ 会报错
from pyagentforge import SkillLoader
# ImportError: cannot import name 'SkillLoader' from 'pyagentforge'
```

### Q3: 核心功能有变化吗？

**A:** 没有。核心功能保持不变，只是组织结构变化：

- `pyagentforge.core.*` 模块完全相同
- `pyagentforge.skills.*` 模块完全相同
- `pyagentforge.providers.*` 模块完全相同

### Q4: 如何快速找到新的导入路径？

**A:** 使用以下规则：

1. **并行执行** → `pyagentforge.plugins.integration.parallel_executor`
2. **Skill 加载** → `pyagentforge.plugins.skills.skill_loader`
3. **模型注册** → `pyagentforge.core.model_registry`
4. **思考配置** → `pyagentforge.core.thinking`
5. **提供商** → `pyagentforge.plugins.providers.<provider_name>`

### Q5: 推荐使用哪种导入方式？

**A:** 优先级：

1. ⭐ **工厂函数** (最简洁): `from pyagentforge import create_engine`
2. ⭐ **插件导入** (最明确): `from pyagentforge.plugins.xxx import ...`
3. ⭐ **核心导入** (最直接): `from pyagentforge.core.xxx import ...`

### Q6: 插件系统是什么？

**A:** v2.0 的核心特性，允许：

- 动态加载功能模块
- 按需启用/禁用功能
- 统一的扩展点（Hooks）

详见 [PLUGIN_DEVELOPMENT.md](./docs/PLUGIN_DEVELOPMENT.md)

---

## 自动化迁移工具

### 使用 sed 批量替换

```bash
# 替换并行执行器导入
find . -name "*.py" -exec sed -i \
  's/from pyagentforge import ParallelSubagentExecutor/from pyagentforge.plugins.integration.parallel_executor import ParallelSubagentExecutor/g' {} +

# 替换 SkillLoader 导入
find . -name "*.py" -exec sed -i \
  's/from pyagentforge import SkillLoader/from pyagentforge.plugins.skills.skill_loader import SkillLoader/g' {} +

# 替换 ThinkingLevel 导入
find . -name "*.py" -exec sed -i \
  's/from pyagentforge import ThinkingLevel/from pyagentforge.core.thinking import ThinkingLevel/g' {} +
```

### 手动检查

```bash
# 查找可能的旧导入
grep -r "from pyagentforge import" --include="*.py" . | grep -E "(ParallelSubagentExecutor|SkillLoader|ModelRegistry|ThinkingLevel)"
```

---

## 获取帮助

如果遇到迁移问题：

1. 查看 [CHANGELOG.md](./CHANGELOG.md) 了解完整变更
2. 查看 [API_REFERENCE.md](./docs/API_REFERENCE.md) 了解新 API
3. 提交 Issue: https://github.com/your-org/pyagentforge/issues

---

**最后更新**: 2026-02-17
**版本**: v2.0.0