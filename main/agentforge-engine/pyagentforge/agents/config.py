"""
Agent 配置

定义 Agent 的配置模型
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pyagentforge.tools.permission import PermissionChecker


class AgentConfig(BaseModel):
    """Agent 配置"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(default="default", description="Agent 名称")
    description: str = Field(default="", description="Agent 描述")
    version: str = Field(default="1.0.0", description="Agent 版本")

    # 运行配置
    model: str = Field(default="default", description="使用的模型")
    max_tokens: int = Field(default=4096, description="最大输出 Token")
    temperature: float = Field(default=1.0, description="温度参数")
    timeout: int = Field(default=120, description="执行超时(秒)")

    # 系统提示词
    system_prompt: str = Field(
        default="你是一个有帮助的 AI 助手。",
        description="系统提示词",
    )

    # 工具权限
    allowed_tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许使用的工具列表，'*' 表示所有",
    )
    denied_tools: list[str] = Field(
        default_factory=list,
        description="禁止使用的工具列表",
    )
    ask_tools: list[str] = Field(
        default_factory=list,
        description="需要用户确认的工具列表",
    )

    # 子代理配置
    max_subagent_depth: int = Field(default=3, description="子代理最大深度")

    # 内部使用
    permission_checker: Any = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        """初始化后处理"""
        # 创建权限检查器
        if self.permission_checker is None:
            from pyagentforge.tools.permission import PermissionConfig

            perm_config = PermissionConfig(
                allowed=self.allowed_tools,
                denied=self.denied_tools,
                ask=self.ask_tools,
            )
            self.permission_checker = PermissionChecker(perm_config)

class RuntimeConfig(BaseModel):
    """运行时配置"""

    mode: str = Field(default="primary", description="运行模式")
    max_messages: int = Field(default=100, description="最大消息数")
    compaction_threshold: int = Field(default=80, description="压缩阈值")


class PermissionConfig(BaseModel):
    """权限配置"""

    tools: dict[str, str] = Field(
        default_factory=dict,
        description="工具权限映射",
    )
    resources: list[str] = Field(
        default_factory=list,
        description="资源访问限制",
    )
    commands: list[str] = Field(
        default_factory=list,
        description="命令白名单",
    )
