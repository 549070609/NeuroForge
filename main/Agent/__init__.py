"""
Agent 底座系统

提供 Agent 的目录管理、MateAgent 工具等功能。

目录结构:
main/Agent/
├── core/                 # 核心模块 (配置、目录扫描)
├── mate-agent/           # 元级 Agent (包含工具和模板)
│   ├── agent.yaml        # Agent 定义
│   ├── system_prompt.md  # 系统提示词
│   ├── tools/            # MateAgent 专用工具
│   ├── templates/        # Agent 模板
│   ├── subagents/        # 子Agent
│   └── docs/             # 文档
├── {agent-id}/           # 其他 Agent
│   ├── agent.yaml
│   └── system_prompt.md
└── config.yaml           # 配置文件

Agent ID 规则:
- Agent ID = 目录名 (如: mate-agent)

排除目录:
- core, __pycache__, .git, .backups
"""

# 核心模块
from .core import (
    AgentDirectory,
    AgentOrigin,
    AgentInfo,
    AgentBaseConfig,
    get_agent_base_config,
    PlanFileManager,
    PlanFile,
    PlanStep,
    PlanStatus,
    StepStatus,
)

# 从 mate-agent 导入工具和模板
# 使用动态导入处理带连字符的目录名
import sys
from pathlib import Path

_mate_agent_tools_path = Path(__file__).parent / "mate-agent" / "tools"
_mate_agent_templates_path = Path(__file__).parent / "mate-agent" / "templates"

def _import_module_from_path(module_name: str, file_path: Path):
    """从文件路径动态导入模块"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# 导入工具
_tools_init = _mate_agent_tools_path / "__init__.py"
_mate_agent_tools = _import_module_from_path("mate_agent_tools", _tools_init)

# 导入模板
_templates_init = _mate_agent_templates_path / "__init__.py"
_mate_agent_templates = _import_module_from_path("mate_agent_templates", _templates_init)

# 导出
MateAgentTool = _mate_agent_tools.MateAgentTool
MateAgentToolRegistry = _mate_agent_tools.MateAgentToolRegistry
get_tool_registry = _mate_agent_tools.get_tool_registry
TemplateLoader = _mate_agent_templates.TemplateLoader

__version__ = "1.0.0"
__all__ = [
    # Config
    "AgentBaseConfig",
    "get_agent_base_config",
    # Directory
    "AgentDirectory",
    "AgentOrigin",
    "AgentInfo",
    # Plan Manager
    "PlanFileManager",
    "PlanFile",
    "PlanStep",
    "PlanStatus",
    "StepStatus",
    # Tools
    "MateAgentTool",
    "MateAgentToolRegistry",
    "get_tool_registry",
    # Templates
    "TemplateLoader",
]
