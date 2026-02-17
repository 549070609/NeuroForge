"""
技能模型

定义技能的数据结构
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """技能元数据"""

    name: str = Field(..., description="技能 ID")
    description: str = Field(..., description="技能描述")
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="", description="作者")
    tags: list[str] = Field(default_factory=list, description="标签")

    # 触发配置
    triggers: list[str] = Field(
        default_factory=list,
        description="触发关键词",
    )
    auto_load: bool = Field(default=False, description="是否自动加载")

    # 依赖
    dependencies: list[str] = Field(
        default_factory=list,
        description="依赖的其他技能",
    )

    # 工具权限
    tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许使用的工具",
    )


class Skill(BaseModel):
    """技能模型"""

    metadata: SkillMetadata
    body: str = Field(..., description="技能内容 (Markdown)")
    path: Path | None = Field(default=None, description="技能文件路径")

    class Config:
        arbitrary_types_allowed = True

    def get_full_content(self) -> str:
        """获取完整内容 (用于注入到上下文)"""
        return f"""# 技能: {self.metadata.name}

{self.body}"""

    def get_description_for_prompt(self) -> str:
        """获取用于系统提示词的描述"""
        return f"- **{self.metadata.name}**: {self.metadata.description}"

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def triggers(self) -> list[str]:
        return self.metadata.triggers
