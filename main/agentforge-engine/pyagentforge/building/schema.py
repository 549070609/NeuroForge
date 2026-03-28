"""
Agent Schema 定义

提供完整的 Agent 声明式定义，支持转换为 AgentMetadata 和 AgentConfig
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pyagentforge.kernel.engine import AgentConfig
from pyagentforge.agents.metadata import (
    AgentCategory,
    AgentCost,
    AgentMetadata,
    DelegationTrigger,
)


class AgentIdentity(BaseModel):
    """Agent 身份标识"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Agent 名称，唯一标识")
    version: str = Field(default="1.0.0", description="版本号")
    namespace: str = Field(default="default", description="命名空间，用于隔离")
    description: str = Field(default="", description="描述信息")
    tags: list[str] = Field(default_factory=list, description="标签，用于分类和搜索")
    author: str = Field(default="", description="作者信息")
    license: str = Field(default="MIT", description="许可证")

class ModelConfiguration(BaseModel):
    """模型配置"""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="anthropic", description="模型提供商")
    model: str = Field(default="default", description="模型名称")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, description="最大输出 Token")
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = Field(
        default="medium", description="推理努力程度"
    )
    timeout: int = Field(default=120, ge=1, description="请求超时(秒)")

class CapabilityDefinition(BaseModel):
    """能力定义"""

    model_config = ConfigDict(extra="forbid")

    # 工具配置
    tools: list[str] = Field(default_factory=lambda: ["*"], description="允许的工具列表")
    denied_tools: list[str] = Field(default_factory=list, description="拒绝的工具列表")
    ask_tools: list[str] = Field(default_factory=list, description="需要确认的工具列表")

    # 技能和命令
    skills: list[str] = Field(default_factory=list, description="技能列表")
    commands: list[str] = Field(default_factory=list, description="命令列表")

    # 权限
    allowed_paths: list[str] = Field(default_factory=list, description="允许的路径")
    denied_paths: list[str] = Field(default_factory=list, description="拒绝的路径")
    allowed_hosts: list[str] = Field(default_factory=list, description="允许的主机")
    denied_hosts: list[str] = Field(default_factory=list, description="拒绝的主机")
    command_whitelist: list[str] = Field(default_factory=list, description="命令白名单")
    command_blacklist: list[str] = Field(default_factory=list, description="命令黑名单")

class BehaviorDefinition(BaseModel):
    """行为定义"""

    model_config = ConfigDict(extra="forbid")

    # 提示词
    system_prompt: str = Field(default="", description="系统提示词")
    prompt_append: str = Field(default="", description="追加到提示词的内容")

    # 触发条件
    use_when: list[str] = Field(default_factory=list, description="使用场景关键词")
    avoid_when: list[str] = Field(default_factory=list, description="避免场景关键词")
    key_trigger: str = Field(default="", description="正则触发模式")

    # 委托触发器
    triggers: list[dict[str, str]] = Field(
        default_factory=list, description="委托触发器列表"
    )

    # 生命周期钩子
    on_init: str = Field(default="", description="初始化钩子函数名")
    on_activate: str = Field(default="", description="激活钩子函数名")
    on_deactivate: str = Field(default="", description="停用钩子函数名")

class ExecutionLimits(BaseModel):
    """执行限制"""

    model_config = ConfigDict(extra="forbid")

    is_readonly: bool = Field(default=False, description="是否只读")
    supports_background: bool = Field(default=True, description="是否支持后台运行")
    max_concurrent: int = Field(default=3, ge=1, description="最大并发实例数")
    timeout: int = Field(default=300, ge=1, description="执行超时(秒)")
    max_iterations: int = Field(default=50, ge=1, description="最大迭代次数")
    max_subagent_depth: int = Field(default=3, ge=1, description="子代理最大深度")

class DependencyDefinition(BaseModel):
    """依赖定义"""

    model_config = ConfigDict(extra="forbid")

    requires: list[str] = Field(
        default_factory=list, description="必需的 Agent ID 列表"
    )
    optional_requires: list[str] = Field(
        default_factory=list, description="可选的 Agent ID 列表"
    )
    conflicts_with: list[str] = Field(
        default_factory=list, description="冲突的 Agent ID 列表"
    )

class MemoryConfiguration(BaseModel):
    """记忆配置"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(default=True, description="是否启用记忆")
    max_messages: int = Field(default=100, ge=1, description="最大消息数")
    persistent_session: bool = Field(default=False, description="是否持久化会话")
    compaction_threshold: int = Field(default=80, ge=1, description="压缩阈值")

class AgentSchema(BaseModel):
    """
    Agent Schema 完整定义

    提供声明式的 Agent 定义，可转换为 AgentMetadata 和 AgentConfig
    """

    identity: AgentIdentity = Field(description="身份标识")
    category: AgentCategory = Field(default=AgentCategory.CODING, description="类别")
    cost: AgentCost = Field(default=AgentCost.MODERATE, description="成本等级")

    capabilities: CapabilityDefinition = Field(
        default_factory=CapabilityDefinition, description="能力定义"
    )
    model: ModelConfiguration = Field(
        default_factory=ModelConfiguration, description="模型配置"
    )
    behavior: BehaviorDefinition = Field(
        default_factory=BehaviorDefinition, description="行为定义"
    )
    limits: ExecutionLimits = Field(
        default_factory=ExecutionLimits, description="执行限制"
    )
    dependencies: DependencyDefinition = Field(
        default_factory=DependencyDefinition, description="依赖定义"
    )
    memory: MemoryConfiguration = Field(
        default_factory=MemoryConfiguration, description="记忆配置"
    )

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    def to_agent_metadata(self) -> AgentMetadata:
        """
        转换为 AgentMetadata

        Returns:
            AgentMetadata 实例
        """
        # 转换委托触发器
        triggers = [
            DelegationTrigger(domain=t.get("domain", ""), trigger=t.get("trigger", ""))
            for t in self.behavior.triggers
        ]

        return AgentMetadata(
            name=self.identity.name,
            description=self.identity.description,
            category=self.category,
            cost=self.cost,
            tools=self.capabilities.tools,
            system_prompt=self.behavior.system_prompt,
            use_when=self.behavior.use_when,
            avoid_when=self.behavior.avoid_when,
            key_trigger=self.behavior.key_trigger,
            model_preference=self.model.model,
            max_tokens=self.model.max_tokens,
            temperature=self.model.temperature,
            is_readonly=self.limits.is_readonly,
            supports_background=self.limits.supports_background,
            max_concurrent=self.limits.max_concurrent,
            triggers=triggers,
            reasoning_effort=self.model.reasoning_effort,
        )

    def to_agent_config(self) -> AgentConfig:
        """
        转换为 AgentConfig

        Returns:
            AgentConfig 实例
        """
        return AgentConfig(
            name=self.identity.name,
            description=self.identity.description,
            version=self.identity.version,
            model=self.model.model,
            max_tokens=self.model.max_tokens,
            temperature=self.model.temperature,
            timeout=self.model.timeout,
            system_prompt=self.behavior.system_prompt,
            allowed_tools=self.capabilities.tools,
            denied_tools=self.capabilities.denied_tools,
            ask_tools=self.capabilities.ask_tools,
            max_iterations=self.limits.max_iterations,
            max_subagent_depth=self.limits.max_subagent_depth,
            permission_checker=None,  # 将在 post_init 中创建
        )

    @classmethod
    def from_metadata(cls, metadata: AgentMetadata) -> "AgentSchema":
        """
        从 AgentMetadata 创建 Schema

        Args:
            metadata: AgentMetadata 实例

        Returns:
            AgentSchema 实例
        """
        # 转换委托触发器
        triggers = [t.to_dict() for t in metadata.triggers]

        return cls(
            identity=AgentIdentity(
                name=metadata.name,
                description=metadata.description,
            ),
            category=metadata.category,
            cost=metadata.cost,
            capabilities=CapabilityDefinition(
                tools=metadata.tools,
            ),
            model=ModelConfiguration(
                model=metadata.model_preference or "default",
                max_tokens=metadata.max_tokens,
                temperature=metadata.temperature,
                reasoning_effort=metadata.reasoning_effort,
            ),
            behavior=BehaviorDefinition(
                system_prompt=metadata.system_prompt,
                use_when=metadata.use_when,
                avoid_when=metadata.avoid_when,
                key_trigger=metadata.key_trigger,
                triggers=triggers,
            ),
            limits=ExecutionLimits(
                is_readonly=metadata.is_readonly,
                supports_background=metadata.supports_background,
                max_concurrent=metadata.max_concurrent,
            ),
        )

    def compute_content_hash(self) -> str:
        """
        计算内容哈希，用于完整性校验

        Returns:
            SHA256 哈希字符串
        """
        import hashlib
        import json

        # 序列化为 JSON
        content = json.dumps(
            self.model_dump(mode="json", exclude_none=True),
            sort_keys=True,
            ensure_ascii=False,
        )

        # 计算 SHA256
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_full_name(self) -> str:
        """
        获取完整名称（namespace/name）

        Returns:
            完整名称
        """
        if self.identity.namespace == "default":
            return self.identity.name
        return f"{self.identity.namespace}/{self.identity.name}"

    def __hash__(self) -> int:
        """支持哈希"""
        return hash(self.get_full_name())

    def __eq__(self, other: object) -> bool:
        """支持相等比较"""
        if not isinstance(other, AgentSchema):
            return False
        return self.get_full_name() == other.get_full_name()
    model_config = ConfigDict(extra="forbid", use_enum_values=False)
