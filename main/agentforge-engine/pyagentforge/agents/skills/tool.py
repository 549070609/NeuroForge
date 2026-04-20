"""
Skill 工具

加载技能获取专业知识
"""

from typing import Any

from pyagentforge.agents.skills.loader import SkillLoader
from pyagentforge.agents.skills.registry import SkillRegistry
from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SkillTool(BaseTool):
    """Skill 工具 - 加载技能获取专业知识"""

    name = "Skill"
    description = """加载技能以获取专业知识。

当用户的请求涉及以下场景时，应该主动加载相应的技能:
- 需要特定领域的知识
- 需要遵循特定的指南或最佳实践
- 需要使用特定的工具或方法

加载技能后，相关知识会被注入到上下文中，帮助你更好地完成任务。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "要加载的技能名称",
            },
        },
        "required": ["skill"],
    }
    timeout = 10
    risk_level = "low"

    def __init__(
        self,
        skill_loader: SkillLoader,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.loader = skill_loader
        self.registry = skill_registry or SkillRegistry(skill_loader)

    async def execute(self, skill: str) -> str:
        """加载技能"""
        logger.info(
            "Loading skill",
            extra_data={"skill": skill},
        )

        # 检查技能是否存在
        if skill not in self.loader:
            available = ", ".join(self.loader.skills.keys())
            return f"Error: Skill '{skill}' not found. Available skills: {available}"

        # 检查是否已加载
        if self.registry.is_loaded(skill):
            return f"Skill '{skill}' is already loaded in this context."

        # 获取技能内容
        content = self.loader.get_skill_content(skill)

        # 标记为已加载
        self.registry.mark_loaded(skill)

        # 加载依赖
        deps = self.loader.get_dependencies(skill)
        dep_contents = []

        for dep_name in deps:
            if not self.registry.is_loaded(dep_name):
                dep_content = self.loader.get_skill_content(dep_name)
                dep_contents.append(dep_content)
                self.registry.mark_loaded(dep_name)
                logger.debug(
                    "Loaded skill dependency",
                    extra_data={"skill": skill, "dependency": dep_name},
                )

        # 构建返回内容
        result_parts = [content]

        if dep_contents:
            result_parts.append("\n\n---\n\nLoaded dependencies:\n")
            result_parts.extend(dep_contents)

        logger.info(
            "Skill loaded successfully",
            extra_data={"skill": skill, "dependencies": len(deps)},
        )

        return "\n".join(result_parts)
