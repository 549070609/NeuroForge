"""
命令模型

定义用户自定义命令的数据结构
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CommandMetadata(BaseModel):
    """命令元数据"""

    name: str = Field(..., description="命令名称 (不含 / 前缀)")
    description: str = Field(..., description="命令描述")
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="", description="作者")

    # 命令配置
    alias: list[str] = Field(
        default_factory=list,
        description="命令别名",
    )
    category: str = Field(default="general", description="命令分类")

    # 工具权限
    tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许使用的工具",
    )

    # 执行配置
    timeout: int = Field(default=300, description="超时时间 (秒)")
    confirm: bool = Field(default=False, description="执行前是否需要确认")

    # 提示词配置
    model: str | None = Field(default=None, description="指定使用的模型")
    temperature: float | None = Field(default=None, description="温度参数")
    max_tokens: int | None = Field(default=None, description="最大输出 token")


class Command(BaseModel):
    """命令模型"""

    metadata: CommandMetadata
    body: str = Field(..., description="命令内容 (Markdown, 支持动态命令注入)")
    path: Path | None = Field(default=None, description="命令文件路径")

    class Config:
        arbitrary_types_allowed = True

    def get_full_content(self) -> str:
        """获取完整内容 (用于注入到上下文)"""
        return f"""# 命令: /{self.metadata.name}

{self.body}"""

    def get_description_for_prompt(self) -> str:
        """获取用于系统提示词的描述"""
        aliases = f" (别名: {', '.join(self.metadata.alias)})" if self.metadata.alias else ""
        return f"- **/{self.metadata.name}**: {self.metadata.description}{aliases}"

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def all_names(self) -> list[str]:
        """获取所有可用的命令名称 (包括别名)"""
        return [self.metadata.name] + self.metadata.alias
