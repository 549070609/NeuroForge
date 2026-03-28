"""
Agent Builder

提供流畅的 API 来构建 Agent Schema
"""

from typing import Any, Literal, Self

from pyagentforge.agents.metadata import AgentCategory, AgentCost, AgentMetadata
from pyagentforge.building.schema import (
    AgentIdentity,
    AgentSchema,
    BehaviorDefinition,
    CapabilityDefinition,
    DependencyDefinition,
    ExecutionLimits,
    MemoryConfiguration,
    ModelConfiguration,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class AgentBuilder:
    """
    Agent 构建器

    提供流畅的 API 来逐步构建 Agent Schema
    """

    def __init__(self):
        """初始化构建器"""
        self._identity = AgentIdentity(name="unnamed-agent")
        self._category = AgentCategory.CODING
        self._cost = AgentCost.MODERATE

        self._model = ModelConfiguration()
        self._capabilities = CapabilityDefinition()
        self._behavior = BehaviorDefinition()
        self._limits = ExecutionLimits()
        self._dependencies = DependencyDefinition()
        self._memory = MemoryConfiguration()

        self._metadata: dict[str, Any] = {}

    # ==================== 身份配置 ====================

    def with_name(self, name: str) -> Self:
        """
        设置 Agent 名称

        Args:
            name: Agent 名称

        Returns:
            self
        """
        self._identity.name = name
        return self

    def with_version(self, version: str) -> Self:
        """
        设置版本号

        Args:
            version: 版本号（如 "1.0.0"）

        Returns:
            self
        """
        self._identity.version = version
        return self

    def with_description(self, description: str) -> Self:
        """
        设置描述

        Args:
            description: 描述信息

        Returns:
            self
        """
        self._identity.description = description
        return self

    def with_tags(self, tags: list[str]) -> Self:
        """
        设置标签

        Args:
            tags: 标签列表

        Returns:
            self
        """
        self._identity.tags = tags
        return self

    def add_tag(self, tag: str) -> Self:
        """
        添加单个标签

        Args:
            tag: 标签

        Returns:
            self
        """
        if tag not in self._identity.tags:
            self._identity.tags.append(tag)
        return self

    def with_namespace(self, namespace: str) -> Self:
        """
        设置命名空间

        Args:
            namespace: 命名空间

        Returns:
            self
        """
        self._identity.namespace = namespace
        return self

    def with_author(self, author: str) -> Self:
        """
        设置作者

        Args:
            author: 作者信息

        Returns:
            self
        """
        self._identity.author = author
        return self

    # ==================== 模型配置 ====================

    def with_model(self, model: str) -> Self:
        """
        设置模型名称

        Args:
            model: 模型名称（如 "default"）

        Returns:
            self
        """
        self._model.model = model
        return self

    def with_provider(self, provider: str) -> Self:
        """
        设置提供商

        Args:
            provider: 提供商名称（如 "anthropic"）

        Returns:
            self
        """
        self._model.provider = provider
        return self

    def with_temperature(self, temperature: float) -> Self:
        """
        设置温度参数

        Args:
            temperature: 温度值（0.0-2.0）

        Returns:
            self
        """
        self._model.temperature = temperature
        return self

    def with_max_tokens(self, max_tokens: int) -> Self:
        """
        设置最大输出 Token

        Args:
            max_tokens: 最大 Token 数

        Returns:
            self
        """
        self._model.max_tokens = max_tokens
        return self

    def with_reasoning_effort(
        self, effort: Literal["low", "medium", "high", "xhigh"]
    ) -> Self:
        """
        设置推理努力程度

        Args:
            effort: 努力程度

        Returns:
            self
        """
        self._model.reasoning_effort = effort
        return self

    def with_timeout(self, timeout: int) -> Self:
        """
        设置超时时间

        Args:
            timeout: 超时秒数

        Returns:
            self
        """
        self._model.timeout = timeout
        self._limits.timeout = timeout
        return self

    # ==================== 能力配置 ====================

    def add_tool(self, tool_name: str) -> Self:
        """
        添加单个工具

        Args:
            tool_name: 工具名称

        Returns:
            self
        """
        if tool_name not in self._capabilities.tools:
            self._capabilities.tools.append(tool_name)
        return self

    def add_tools(self, tool_names: list[str]) -> Self:
        """
        添加多个工具

        Args:
            tool_names: 工具名称列表

        Returns:
            self
        """
        for tool in tool_names:
            self.add_tool(tool)
        return self

    def with_all_tools(self) -> Self:
        """
        允许使用所有工具

        Returns:
            self
        """
        self._capabilities.tools = ["*"]
        return self

    def allow_tools(self, tools: list[str]) -> Self:
        """
        设置允许的工具列表

        Args:
            tools: 工具列表

        Returns:
            self
        """
        self._capabilities.tools = tools
        return self

    def deny_tools(self, tools: list[str]) -> Self:
        """
        设置拒绝的工具列表

        Args:
            tools: 工具列表

        Returns:
            self
        """
        self._capabilities.denied_tools = tools
        return self

    def ask_for_tools(self, tools: list[str]) -> Self:
        """
        设置需要确认的工具列表

        Args:
            tools: 工具列表

        Returns:
            self
        """
        self._capabilities.ask_tools = tools
        return self

    def add_skill(self, skill_name: str) -> Self:
        """
        添加技能

        Args:
            skill_name: 技能名称

        Returns:
            self
        """
        if skill_name not in self._capabilities.skills:
            self._capabilities.skills.append(skill_name)
        return self

    def add_command(self, command: str) -> Self:
        """
        添加命令

        Args:
            command: 命令

        Returns:
            self
        """
        if command not in self._capabilities.commands:
            self._capabilities.commands.append(command)
        return self

    # ==================== 行为配置 ====================

    def with_prompt(self, prompt: str) -> Self:
        """
        设置系统提示词

        Args:
            prompt: 提示词

        Returns:
            self
        """
        self._behavior.system_prompt = prompt
        return self

    def append_prompt(self, additional: str) -> Self:
        """
        追加到提示词

        Args:
            additional: 追加内容

        Returns:
            self
        """
        self._behavior.prompt_append = additional
        return self

    def with_trigger(self, domain: str, trigger: str) -> Self:
        """
        添加委托触发器

        Args:
            domain: 工作领域
            trigger: 触发条件

        Returns:
            self
        """
        self._behavior.triggers.append({"domain": domain, "trigger": trigger})
        return self

    def with_key_trigger(self, pattern: str) -> Self:
        """
        设置正则触发模式

        Args:
            pattern: 正则表达式

        Returns:
            self
        """
        self._behavior.key_trigger = pattern
        return self

    def use_when(self, keywords: list[str]) -> Self:
        """
        设置使用场景关键词

        Args:
            keywords: 关键词列表

        Returns:
            self
        """
        self._behavior.use_when = keywords
        return self

    def avoid_when(self, keywords: list[str]) -> Self:
        """
        设置避免场景关键词

        Args:
            keywords: 关键词列表

        Returns:
            self
        """
        self._behavior.avoid_when = keywords
        return self

    # ==================== 生命周期钩子 ====================

    def on_init(self, hook: str) -> Self:
        """
        设置初始化钩子

        Args:
            hook: 钩子函数名

        Returns:
            self
        """
        self._behavior.on_init = hook
        return self

    def on_activate(self, hook: str) -> Self:
        """
        设置激活钩子

        Args:
            hook: 钩子函数名

        Returns:
            self
        """
        self._behavior.on_activate = hook
        return self

    def on_deactivate(self, hook: str) -> Self:
        """
        设置停用钩子

        Args:
            hook: 钩子函数名

        Returns:
            self
        """
        self._behavior.on_deactivate = hook
        return self

    # ==================== 限制配置 ====================

    def readonly(self, readonly: bool = True) -> Self:
        """
        设置为只读模式

        Args:
            readonly: 是否只读

        Returns:
            self
        """
        self._limits.is_readonly = readonly
        return self

    def background(self, supports: bool = True) -> Self:
        """
        设置是否支持后台运行

        Args:
            supports: 是否支持

        Returns:
            self
        """
        self._limits.supports_background = supports
        return self

    def max_concurrent(self, max: int) -> Self:
        """
        设置最大并发数

        Args:
            max: 最大并发数

        Returns:
            self
        """
        self._limits.max_concurrent = max
        return self

    def with_max_iterations(self, max_iter: int) -> Self:
        """
        设置最大迭代次数

        Args:
            max_iter: 最大迭代次数

        Returns:
            self
        """
        self._limits.max_iterations = max_iter
        return self

    def with_max_subagent_depth(self, depth: int) -> Self:
        """
        设置子代理最大深度

        Args:
            depth: 最大深度

        Returns:
            self
        """
        self._limits.max_subagent_depth = depth
        return self

    # ==================== 依赖配置 ====================

    def requires(self, agent_ids: list[str]) -> Self:
        """
        设置必需的 Agent

        Args:
            agent_ids: Agent ID 列表

        Returns:
            self
        """
        self._dependencies.requires = agent_ids
        return self

    def optional_requires(self, agent_ids: list[str]) -> Self:
        """
        设置可选的 Agent

        Args:
            agent_ids: Agent ID 列表

        Returns:
            self
        """
        self._dependencies.optional_requires = agent_ids
        return self

    def conflicts_with(self, agent_ids: list[str]) -> Self:
        """
        设置冲突的 Agent

        Args:
            agent_ids: Agent ID 列表

        Returns:
            self
        """
        self._dependencies.conflicts_with = agent_ids
        return self

    # ==================== 记忆配置 ====================

    def with_memory(self, max_messages: int = 100) -> Self:
        """
        启用记忆

        Args:
            max_messages: 最大消息数

        Returns:
            self
        """
        self._memory.enabled = True
        self._memory.max_messages = max_messages
        return self

    def without_memory(self) -> Self:
        """
        禁用记忆

        Returns:
            self
        """
        self._memory.enabled = False
        return self

    def persistent_session(self, persistent: bool = True) -> Self:
        """
        设置是否持久化会话

        Args:
            persistent: 是否持久化

        Returns:
            self
        """
        self._memory.persistent_session = persistent
        return self

    # ==================== 分类配置 ====================

    def with_category(self, category: AgentCategory) -> Self:
        """
        设置类别

        Args:
            category: Agent 类别

        Returns:
            self
        """
        self._category = category
        return self

    def with_cost(self, cost: AgentCost) -> Self:
        """
        设置成本等级

        Args:
            cost: 成本等级

        Returns:
            self
        """
        self._cost = cost
        return self

    # ==================== 元数据配置 ====================

    def with_metadata(self, key: str, value: Any) -> Self:
        """
        设置元数据

        Args:
            key: 键
            value: 值

        Returns:
            self
        """
        self._metadata[key] = value
        return self

    # ==================== 继承与组合 ====================

    def inherit_from(self, schema: AgentSchema | str) -> Self:
        """
        从另一个 Schema 继承配置

        Args:
            schema: AgentSchema 实例或名称

        Returns:
            self
        """
        if isinstance(schema, str):
            # 从注册表查找
            from pyagentforge.agents.registry import get_agent_registry

            registry = get_agent_registry()
            metadata = registry.get(schema)
            if metadata:
                schema = AgentSchema.from_metadata(metadata)
            else:
                logger.warning(f"Agent '{schema}' not found in registry")
                return self

        # 继承配置（覆盖当前值）
        self._category = schema.category
        self._cost = schema.cost
        self._model = schema.model.model_copy()
        self._capabilities = schema.capabilities.model_copy()
        self._behavior = schema.behavior.model_copy()
        self._limits = schema.limits.model_copy()
        self._dependencies = schema.dependencies.model_copy()
        self._memory = schema.memory.model_copy()

        return self

    def extend_from(self, metadata: AgentMetadata) -> Self:
        """
        从 AgentMetadata 扩展

        Args:
            metadata: AgentMetadata 实例

        Returns:
            self
        """
        schema = AgentSchema.from_metadata(metadata)
        return self.inherit_from(schema)

    # ==================== 构建 ====================

    def build(self) -> AgentSchema:
        """
        构建 AgentSchema

        Returns:
            AgentSchema 实例
        """
        # 处理追加的提示词
        if self._behavior.prompt_append:
            self._behavior.system_prompt = (
                self._behavior.system_prompt + "\n\n" + self._behavior.prompt_append
            )

        return AgentSchema(
            identity=self._identity,
            category=self._category,
            cost=self._cost,
            model=self._model,
            capabilities=self._capabilities,
            behavior=self._behavior,
            limits=self._limits,
            dependencies=self._dependencies,
            memory=self._memory,
            metadata=self._metadata,
        )

    def build_and_register(self) -> AgentSchema:
        """
        构建并注册到 AgentRegistry

        Returns:
            AgentSchema 实例
        """
        schema = self.build()

        from pyagentforge.agents.registry import get_agent_registry

        registry = get_agent_registry()
        metadata = schema.to_agent_metadata()
        registry.register(metadata)

        logger.info(f"Built and registered agent: {schema.identity.name}")
        return schema


class AgentTemplate:
    """
    Agent 模板

    提供预定义的 Agent 配置模板
    """

    @staticmethod
    def explorer() -> AgentBuilder:
        """
        代码探索模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.EXPLORATION)
            .with_cost(AgentCost.FREE)
            .allow_tools(["bash", "read", "glob", "grep"])
            .readonly(True)
            .background(True)
            .max_concurrent(5)
            .with_prompt("你是一个探索代理，专门负责搜索和分析代码库。")
            .use_when(["搜索代码", "分析代码结构", "查找文件"])
            .avoid_when(["修改文件", "编写代码"])
            .with_key_trigger(r"\b(search|find|explore|grep|analyze|understand)\b")
        )

    @staticmethod
    def planner() -> AgentBuilder:
        """
        规划模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.PLANNING)
            .with_cost(AgentCost.CHEAP)
            .allow_tools(["bash", "read", "glob", "grep"])
            .readonly(True)
            .background(False)
            .max_concurrent(1)
            .with_prompt("你是一个规划代理，专门负责分析和制定实现计划。")
            .use_when(["规划功能", "分析需求", "制定计划"])
            .avoid_when(["执行实现", "编写代码"])
            .with_key_trigger(r"\b(plan|design|architect|analyze|breakdown)\b")
        )

    @staticmethod
    def coder() -> AgentBuilder:
        """
        编码模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.CODING)
            .with_cost(AgentCost.EXPENSIVE)
            .with_all_tools()
            .readonly(False)
            .background(True)
            .max_concurrent(2)
            .with_prompt("你是一个编码代理，专门负责高效实现代码更改。")
            .use_when(["实现功能", "编写代码", "修复 bug"])
            .avoid_when(["只是探索", "仅规划"])
            .with_key_trigger(r"\b(implement|write|create|fix|code|develop)\b")
        )

    @staticmethod
    def reviewer() -> AgentBuilder:
        """
        审查模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.REVIEW)
            .with_cost(AgentCost.CHEAP)
            .allow_tools(["bash", "read", "glob", "grep"])
            .readonly(True)
            .background(True)
            .max_concurrent(3)
            .with_prompt("你是一个代码审查代理，专门负责审查代码更改。")
            .use_when(["审查代码", "检查质量", "发现问题"])
            .avoid_when(["编写代码", "做修改"])
            .with_key_trigger(r"\b(review|check|audit|verify)\b")
        )

    @staticmethod
    def researcher() -> AgentBuilder:
        """
        研究模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.RESEARCH)
            .with_cost(AgentCost.FREE)
            .allow_tools(["webfetch", "read"])
            .readonly(True)
            .background(True)
            .max_concurrent(5)
            .with_prompt("你是一个文档代理，专门负责获取和总结外部文档。")
            .use_when(["获取文档", "查找 API", "研究库"])
            .avoid_when(["修改代码", "实现决策"])
            .with_key_trigger(r"\b(docs|documentation|api|library|reference)\b")
        )

    @staticmethod
    def advisor() -> AgentBuilder:
        """
        架构顾问模板

        Returns:
            AgentBuilder 实例
        """
        return (
            AgentBuilder()
            .with_category(AgentCategory.REASONING)
            .with_cost(AgentCost.EXPENSIVE)
            .with_reasoning_effort("xhigh")
            .allow_tools(["bash", "read", "glob", "grep"])
            .readonly(True)
            .background(False)
            .max_concurrent(1)
            .with_prompt("你是一个架构顾问代理，专门负责深度分析和设计决策。")
            .use_when(["架构决策", "深度分析", "复杂问题", "技术指导"])
            .avoid_when(["简单代码更改", "常规任务"])
            .with_key_trigger(r"\b(architecture|design|consult|advice|reasoning)\b")
        )
