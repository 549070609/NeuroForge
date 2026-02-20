# PyAgentForge 提示词适配系统 - 快速参考

## 🎯 一句话总结

为不同 AI 模型自动选择和生成优化的系统提示词。

## 📦 核心组件

```python
from pyagentforge.prompts import (
    get_prompt_adapter,      # 适配管理器
    get_prompt_registry,     # 注册表
    AdaptationContext,       # 适配上下文
    PromptVariant,           # 变体定义
    CapabilityModule,        # 能力模块
)
```

## 🚀 快速使用

### 自动模式（推荐）

```python
from pyagentforge import Agent

# 自动适配，无需配置
agent = Agent(model="claude-sonnet-4-20250514")
response = await agent.run("你的任务")
```

### 手动模式

```python
from pyagentforge.kernel.model_registry import get_model
from pyagentforge.prompts import get_prompt_adapter, AdaptationContext

model_config = get_model("claude-sonnet-4-20250514")
adapter = get_prompt_adapter()

context = AdaptationContext(
    model_id="claude-sonnet-4-20250514",
    model_config=model_config,
    base_prompt="You are a helpful assistant.",
)

adapted = adapter.adapt_prompt(context)
```

## 📋 内置变体

| 模型 | 变体名称 | 优先级 | 特性 |
|------|----------|--------|------|
| Claude Sonnet 4/Opus 4 | anthropic_extended_thinking | 100 | 深度思考 |
| 其他 Claude | anthropic_standard | 50 | 标准模板 |
| Gemini | google_concise | 50 | 简洁输出 |
| GPT 系列 | openai_autonomous | 50 | 自主工作流 |
| 其他 | default | 10 | 基础模板 |

## 🔧 自定义变体

```python
from pyagentforge.prompts import PromptVariant, get_prompt_registry

variant = PromptVariant(
    name="my_custom",
    applies_to=lambda mid, cfg: "my-model" in mid,
    template_path="custom/my_template.md",
    priority=80,
)

registry = get_prompt_registry()
registry.register_variant(variant)
```

## 📁 模板位置

```
pyagentforge/templates/prompts/
├── base.md                   # 基础模板
├── anthropic/
│   ├── standard.md          # Anthropic 标准
│   └── extended_thinking.md # Extended Thinking
├── openai/
│   └── autonomous.md        # OpenAI 自主工作流
└── google/
    └── concise.md           # Gemini 简洁输出
```

## ✅ 验证系统

```bash
python verify_prompt_adaptation.py
```

## 📊 效果示例

| 模型 | 基础长度 | 适配后长度 | 增加 |
|------|----------|------------|------|
| Claude Sonnet 4 | 28 | 1099 | +3914% |
| Claude 3.5 Sonnet | 28 | 610 | +2079% |
| Gemini 2.0 Flash | 28 | 999 | +3468% |
| GPT-4o | 28 | 948 | +3286% |

## 🎨 架构图

```
AgentConfig.system_prompt
        ↓
PromptAdapterManager
    ├── 1. 选择变体 (优先级)
    ├── 2. 加载模板
    ├── 3. 获取能力模块
    └── 4. 组装提示词
        ↓
AgentEngine._adapt_system_prompt()
        ↓
Provider.create_message(system=adapted)
```

## 📚 相关文档

- **完整文档**: `PROMPT_ADAPTATION_README.md`
- **实现总结**: `IMPLEMENTATION_SUMMARY.md`
- **完成报告**: `IMPLEMENTATION_COMPLETE_REPORT.md`

## 🐛 调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 日志会显示：
# - 选择的变体
# - 应用的能力模块
# - 提示词长度变化
```

## 💡 提示

1. **自动集成**: Agent 会自动调用适配，无需手动干预
2. **优雅降级**: 适配失败时自动回退到基础提示词
3. **性能优化**: 模板缓存，单例模式，< 1ms 开销
4. **易扩展**: 插件式架构，支持自定义变体和能力模块

---

**版本**: v1.0 | **日期**: 2026-02-20 | **状态**: ✅ 生产就绪
