# PyAgentForge 提示词适配系统

## 概述

提示词适配系统为 PyAgentForge 提供了模型特定的提示词变体和能力感知的提示词适配功能。该系统能够根据不同的模型（Anthropic、OpenAI、Google）自动选择和生成优化的系统提示词。

## 架构

```
AgentConfig.system_prompt
        ↓
PromptAdapterManager (适配管理器)
    ├── 选择模型变体 (Anthropic/Gemini/OpenAI)
    ├── 应用能力感知调整 (Vision/Parallel Tools)
    └── 组装最终提示词
        ↓
AgentEngine._adapt_system_prompt()
        ↓
Provider.create_message(system=...)
```

## 核心组件

### 1. PromptVariant (提示词变体)

为特定模型或提供商定义的提示词模板。

```python
from pyagentforge.prompts.base import PromptVariant

variant = PromptVariant(
    name="anthropic_extended_thinking",
    applies_to=lambda mid, cfg: (
        cfg.provider == ProviderType.ANTHROPIC and
        "claude-sonnet-4" in mid.lower()
    ),
    template_path="anthropic/extended_thinking.md",
    priority=100,
    description="Extended Thinking 模式",
)
```

### 2. CapabilityModule (能力模块)

根据模型能力动态添加的提示词片段。

```python
from pyagentforge.prompts.base import CapabilityModule, CapabilityType

module = CapabilityModule(
    capability=CapabilityType.VISION,
    condition=lambda cfg: cfg.supports_vision,
    template_section="## 图像处理\n你可以处理图像输入...",
    priority=60,
)
```

### 3. PromptTemplateRegistry (注册表)

管理所有变体和能力模块的注册与选择。

```python
from pyagentforge.prompts.registry import get_prompt_registry

registry = get_prompt_registry()

# 注册变体
registry.register_variant(variant)

# 注册能力模块
registry.register_capability(module)

# 选择变体
variant = registry.select_variant(model_id, model_config)
```

### 4. PromptAdapterManager (适配管理器)

协调适配过程的主控制器。

```python
from pyagentforge.prompts.adapter import get_prompt_adapter
from pyagentforge.prompts.base import AdaptationContext

adapter = get_prompt_adapter()
context = AdaptationContext(
    model_id="claude-sonnet-4-20250514",
    model_config=model_config,
    base_prompt="You are a helpful assistant.",
    available_tools=[...],
)

adapted_prompt = adapter.adapt_prompt(context)
```

## 内置变体

### 1. Anthropic Extended Thinking
- **适用模型**: Claude Sonnet 4, Claude Opus 4
- **优先级**: 100
- **特性**: 深度思考模式，适用于复杂推理任务

### 2. Anthropic Standard
- **适用模型**: 所有 Claude 模型
- **优先级**: 50
- **特性**: 标准 Anthropic 提示词模板

### 3. Google Gemini Concise
- **适用模型**: Gemini 系列
- **优先级**: 50
- **特性**: 简洁输出风格，3 行以内响应

### 4. OpenAI Autonomous
- **适用模型**: GPT 系列
- **优先级**: 50
- **特性**: 自主工作流，高度自我驱动

### 5. Default
- **适用模型**: 所有其他模型
- **优先级**: 10
- **特性**: 通用基础模板

## 内置能力模块

### 1. Vision Capability
- **条件**: `model_config.supports_vision == True`
- **优先级**: 60
- **内容**: 图像处理指南

### 2. Parallel Tools Capability
- **条件**: 默认启用
- **优先级**: 50
- **内容**: 并行工具调用指南

## 使用方法

### 基本使用（自动集成）

提示词适配已自动集成到 `AgentEngine` 中，无需额外配置：

```python
from pyagentforge import Agent

# Agent 会自动根据模型适配提示词
agent = Agent(model="claude-sonnet-4-20250514")
response = await agent.run("分析这段代码的性能瓶颈")
```

### 手动使用

如果需要手动获取适配后的提示词：

```python
from pyagentforge.kernel.model_registry import get_model
from pyagentforge.prompts.adapter import get_prompt_adapter
from pyagentforge.prompts.base import AdaptationContext

model_config = get_model("claude-sonnet-4-20250514")
adapter = get_prompt_adapter()

context = AdaptationContext(
    model_id="claude-sonnet-4-20250514",
    model_config=model_config,
    base_prompt="You are a helpful assistant.",
    available_tools=[{"name": "bash", "description": "Execute commands"}],
)

adapted_prompt = adapter.adapt_prompt(context)
print(adapted_prompt)
```

## 自定义变体

### 创建自定义变体

```python
from pyagentforge.prompts.base import PromptVariant
from pyagentforge.prompts.registry import get_prompt_registry

# 定义变体
custom_variant = PromptVariant(
    name="my_custom_variant",
    applies_to=lambda mid, cfg: (
        cfg.provider == ProviderType.CUSTOM and
        "my-model" in mid
    ),
    template_path="custom/my_template.md",
    priority=80,
    description="自定义模型优化模板",
)

# 注册变体
registry = get_prompt_registry()
registry.register_variant(custom_variant)
```

### 创建自定义模板

在 `pyagentforge/templates/prompts/custom/my_template.md`:

```markdown
# 自定义模型系统提示词

你是一个为特定用途优化的 AI 助手。

## 特殊能力
- 能力 1: 描述
- 能力 2: 描述

## 工作流程
1. 步骤 1
2. 步骤 2
```

## 自定义能力模块

```python
from pyagentforge.prompts.base import CapabilityModule, CapabilityType
from pyagentforge.prompts.registry import get_prompt_registry

# 定义能力模块
custom_capability = CapabilityModule(
    capability=CapabilityType.STREAMING,
    condition=lambda cfg: cfg.supports_streaming,
    template_section="""## 流式输出
你可以实时流式输出内容。在使用流式输出时...""",
    priority=55,
)

# 注册模块
registry = get_prompt_registry()
registry.register_capability(custom_capability)
```

## 验证

运行验证脚本确认系统正常工作：

```bash
python verify_prompt_adaptation.py
```

## 示例

查看示例脚本：

```bash
python example_prompt_adaptation.py
```

## 目录结构

```
pyagentforge/
├── prompts/                      # 提示词适配模块
│   ├── __init__.py
│   ├── base.py                   # 基础类型定义
│   ├── registry.py               # 注册表
│   ├── adapter.py                # 适配管理器
│   ├── variants/                 # 模型变体
│   │   ├── __init__.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── google.py
│   │   └── default.py
│   └── capabilities/             # 能力模块
│       ├── __init__.py
│       └── modules.py
└── templates/                    # 模板文件
    └── prompts/
        ├── base.md               # 基础模板
        ├── anthropic/
        │   ├── standard.md
        │   └── extended_thinking.md
        ├── openai/
        │   └── autonomous.md
        └── google/
            └── concise.md
```

## 设计原则

1. **复用现有基础设施**: 使用现有的 `ModelRegistry` 和工具系统
2. **最小侵入性**: 只在 `AgentEngine._call_llm()` 中添加适配逻辑
3. **优先级选择**: 变体按 priority 降序排序，选择第一个匹配的
4. **单例模式**: Registry 和 Adapter 使用全局单例，避免重复初始化
5. **模板缓存**: 模板文件加载后缓存，避免重复 I/O

## 调试

启用调试日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 运行 Agent
agent = Agent(model="claude-sonnet-4-20250514")
```

日志会显示：
- 选择的变体名称
- 应用的能力模块
- 提示词长度变化

## 未来扩展

- [ ] 支持自定义模板目录
- [ ] 添加更多能力模块（如代码执行、文件操作）
- [ ] 支持提示词版本管理
- [ ] 添加提示词效果评估
- [ ] 支持动态模板变量替换

## 参考

本实现参考了：
- **OpenCode Server**: 模型特定提示词模板（anthropic.txt, gemini.txt）
- **OpenClaw**: 模块化提示词构建系统

---

**最后更新**: 2026-02-20
