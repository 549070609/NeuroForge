# MateAgent 文档

## 概述

MateAgent 是一个元级 Agent，专门负责构建、配置和管理其他 Agent。

## 目录结构

```
mate-agent/
├── agent.yaml           # Agent 定义配置
├── system_prompt.md     # 系统提示词
├── tools/               # MateAgent 专用工具
│   ├── base.py          # 工具基类
│   ├── registry.py      # 工具注册表
│   ├── crud/            # CRUD 工具
│   ├── analysis/        # 分析工具
│   ├── config/          # 配置工具
│   └── system/          # 系统工具
├── templates/           # Agent 模板
│   ├── loader.py        # 模板加载器
│   ├── simple-agent/    # 简单模板
│   ├── tool-agent/      # 工具模板
│   └── reasoning-agent/ # 推理模板
├── subagents/           # 子Agent 目录
│   ├── builder-agent/   # 构建子Agent
│   ├── modifier-agent/  # 修改子Agent
│   ├── analyzer-agent/  # 分析子Agent
│   └── tester-agent/    # 测试子Agent
└── docs/                # 文档
```

## 可用工具

### CRUD 工具
- `create_agent` - 创建新 Agent
- `modify_agent` - 修改现有 Agent
- `delete_agent` - 删除 Agent
- `list_agents` - 列出所有 Agent

### 分析工具
- `validate_agent` - 验证 Agent 配置
- `analyze_requirements` - 分析需求
- `check_dependencies` - 检查依赖关系

### 配置工具
- `render_template` - 渲染模板
- `edit_config` - 编辑配置
- `write_prompt` - 写入提示词

### 系统工具
- `spawn_subagent` - 调度子Agent

## 子Agent

| Agent | 用途 |
|-------|------|
| builder-agent | 构建 Agent 文件 |
| modifier-agent | 修改 Agent 配置 |
| analyzer-agent | 分析需求和验证 |
| tester-agent | 测试 Agent 功能 |

## 使用示例

```python
from main.Agent import MateAgentToolRegistry

# 获取工具注册表
registry = MateAgentToolRegistry()

# 创建 Agent
tool = registry.get('create_agent')
result = await tool.execute(
    agent_id='my-agent',
    spec={'description': 'My custom agent'},
    template='simple'
)
```

## API 兼容性

工具完全兼容 Anthropic Messages API 格式：

```python
tools = registry.to_anthropic_tools()
# 可直接用于 anthropic.Messages.create()
```
