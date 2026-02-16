# PyAgentForge

**版本**: v2.0.0 | [变更日志](./CHANGELOG.md) | [迁移指南](./MIGRATION.md)

通用型 AI Agent 服务底座 - 模型即代理，代码即配置

## 🎯 v2.0 重大更新

- ✨ **插件化架构**: 功能模块化，按需加载
- 🚀 **工厂函数**: `create_engine()` 快速启动
- 📦 **移除向后兼容**: 更清晰的 API 设计
- 📚 **完整文档**: [迁移指南](./MIGRATION.md) + [变更日志](./CHANGELOG.md)

> **从 v1.x 升级?** 请查看 [MIGRATION.md](./MIGRATION.md) 了解如何更新代码。

## 安装

```bash
pip install -e .
```

## 快速开始

```python
from pyagentforge import AgentEngine, ContextManager, ToolRegistry
from pyagentforge.providers import AnthropicProvider

# 创建提供商
provider = AnthropicProvider(api_key="your-api-key")

# 创建工具注册表
tools = ToolRegistry()
tools.register_builtin_tools()

# 创建 Agent 引擎
engine = AgentEngine(
    provider=provider,
    tool_registry=tools,
)

# 运行 Agent
result = await engine.run("你好，请介绍一下你自己")
print(result)
```

## 文档

详见 [docs](./docs/) 目录

## 许可证

MIT License
