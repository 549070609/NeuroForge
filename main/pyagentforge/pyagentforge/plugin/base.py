"""
插件基类

定义插件的标准接口和元数据
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional, Type

from pyagentforge.kernel.base_tool import BaseTool
from pyagentforge.kernel.base_provider import BaseProvider


class PluginType(str, Enum):
    """插件类型"""
    INTERFACE = "interface"      # API, CLI, WebSocket
    PROTOCOL = "protocol"        # MCP, LSP
    TOOL = "tool"               # 扩展工具集
    SKILL = "skill"             # 知识加载器
    PROVIDER = "provider"       # LLM提供商
    MIDDLEWARE = "middleware"   # 中间件
    INTEGRATION = "integration" # 集成插件


@dataclass
class PluginMetadata:
    """插件元数据"""
    id: str                              # 唯一标识，如 "interface.rest-api"
    name: str                            # 显示名称
    version: str                         # 语义版本
    type: PluginType                     # 插件类型
    description: str = ""                # 描述
    author: str = ""                     # 作者
    dependencies: List[str] = field(default_factory=list)          # 必需依赖
    optional_dependencies: List[str] = field(default_factory=list) # 可选依赖
    provides: List[str] = field(default_factory=list)              # 提供的能力标识
    conflicts: List[str] = field(default_factory=list)             # 冲突的插件ID
    priority: int = 0                    # 加载优先级（越高越先加载）


@dataclass
class PluginContext:
    """插件上下文 - 提供插件访问系统资源的能力"""
    engine: Any  # AgentEngine
    config: dict  # 插件配置
    logger: Any  # 日志器

    def get_tool_registry(self):
        """获取工具注册表"""
        return self.engine.tools if self.engine else None


class Plugin(ABC):
    """插件基类"""

    metadata: PluginMetadata

    def __init__(self):
        self._context: Optional[PluginContext] = None
        self._activated = False

    @property
    def context(self) -> PluginContext:
        """获取插件上下文"""
        if self._context is None:
            raise RuntimeError("Plugin context not set. Call on_plugin_load first.")
        return self._context

    @property
    def is_activated(self) -> bool:
        """插件是否已激活"""
        return self._activated

    # ============ 生命周期方法 ============

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时调用"""
        self._context = context

    async def on_plugin_activate(self) -> None:
        """插件激活时调用"""
        self._activated = True

    async def on_plugin_deactivate(self) -> None:
        """插件停用时调用"""
        self._activated = False

    # ============ 钩子方法 - 子类可选重写 ============

    async def on_engine_init(self, engine) -> None:
        """引擎初始化时"""
        pass

    async def on_engine_start(self, engine) -> None:
        """引擎启动时"""
        pass

    async def on_engine_stop(self, engine) -> None:
        """引擎停止时"""
        pass

    async def on_before_llm_call(self, messages: list) -> Optional[list]:
        """LLM调用前 - 返回修改后的消息或None"""
        return None

    async def on_after_llm_call(self, response) -> Optional[Any]:
        """LLM调用后 - 返回修改后的响应或None"""
        return None

    async def on_before_tool_call(self, tool_use) -> Optional[Any]:
        """工具执行前 - 返回替换的工具调用或None"""
        return None

    async def on_after_tool_call(self, result: str) -> Optional[str]:
        """工具执行后 - 返回修改后的结果或None"""
        return None

    async def on_context_overflow(self, token_count: int) -> bool:
        """上下文溢出时 - 返回True表示已处理"""
        return False

    async def on_task_complete(self, result: str) -> None:
        """任务完成时"""
        pass

    async def on_skill_load(self, skill) -> None:
        """技能加载时"""
        pass

    async def on_subagent_spawn(self, subagent) -> None:
        """子Agent创建时"""
        pass

    # ============ 资源提供方法 ============

    def get_tools(self) -> List[BaseTool]:
        """返回插件提供的工具"""
        return []

    def get_providers(self) -> List[Type[BaseProvider]]:
        """返回插件提供的Provider类"""
        return []

    def get_hooks(self) -> dict[str, Callable]:
        """返回插件实现的钩子映射"""
        hooks = {}
        for hook_name in [
            "on_engine_init", "on_engine_start", "on_engine_stop",
            "on_before_llm_call", "on_after_llm_call",
            "on_before_tool_call", "on_after_tool_call",
            "on_context_overflow", "on_task_complete",
            "on_skill_load", "on_subagent_spawn",
        ]:
            method = getattr(self, hook_name, None)
            if method and method.__func__ is not getattr(Plugin, hook_name, None):
                hooks[hook_name] = method
        return hooks
