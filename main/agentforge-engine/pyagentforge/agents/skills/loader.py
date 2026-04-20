"""
技能加载器

扫描和加载技能目录
"""

from pathlib import Path
from typing import Any

from pyagentforge.config.settings import get_settings
from pyagentforge.agents.skills.models import Skill
from pyagentforge.agents.skills.parser import SkillParser, SkillParseError
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SkillLoader:
    """技能加载器 - 扫描目录并加载所有技能"""

    def __init__(
        self,
        skills_dir: Path | None = None,
        parser: SkillParser | None = None,
    ) -> None:
        settings = get_settings()
        self.skills_dir = skills_dir or settings.skills_dir
        self.parser = parser or SkillParser()
        self.skills: dict[str, Skill] = {}
        self._load_errors: dict[str, str] = {}

    def load_all(self) -> dict[str, Skill]:
        """
        加载所有技能

        Returns:
            技能名称到技能对象的映射
        """
        if not self.skills_dir.exists():
            logger.warning(
                "Skills directory does not exist",
                extra_data={"path": str(self.skills_dir)},
            )
            return {}

        logger.info(
            "Loading skills from directory",
            extra_data={"path": str(self.skills_dir)},
        )

        self.skills.clear()
        self._load_errors.clear()

        # 遍历子目录
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                skill = self.parser.parse_file(skill_file)
                self.skills[skill.name] = skill
                logger.debug(
                    "Loaded skill",
                    extra_data={"name": skill.name, "path": str(skill_file)},
                )
            except SkillParseError as e:
                self._load_errors[str(skill_dir)] = str(e)
                logger.error(
                    "Failed to load skill",
                    extra_data={"path": str(skill_dir), "error": str(e)},
                )

        logger.info(
            "Skills loaded",
            extra_data={
                "count": len(self.skills),
                "errors": len(self._load_errors),
            },
        )

        return self.skills

    def get(self, name: str) -> Skill | None:
        """获取技能"""
        return self.skills.get(name)

    def get_skill_content(self, name: str) -> str:
        """
        获取技能内容 (用于注入到上下文)

        Args:
            name: 技能名称

        Returns:
            技能完整内容
        """
        skill = self.skills.get(name)
        if skill is None:
            return f"Error: Skill '{name}' not found"

        return f'<skill name="{name}">\n{skill.get_full_content()}\n</skill>'

    def get_descriptions(self) -> str:
        """
        获取所有技能的描述 (用于系统提示词)

        Returns:
            技能描述列表
        """
        if not self.skills:
            return "No skills available."

        lines = ["Available skills:"]
        for skill in self.skills.values():
            lines.append(skill.get_description_for_prompt())

        return "\n".join(lines)

    def get_trigger_keywords(self) -> dict[str, list[str]]:
        """
        获取所有技能的触发关键词

        Returns:
            技能名称到触发词列表的映射
        """
        return {
            name: skill.triggers
            for name, skill in self.skills.items()
            if skill.triggers
        }

    def match_skill(self, text: str) -> str | None:
        """
        根据文本匹配技能

        Args:
            text: 用户输入文本

        Returns:
            匹配的技能名称或 None
        """
        text_lower = text.lower()

        for name, skill in self.skills.items():
            for trigger in skill.triggers:
                if trigger.lower() in text_lower:
                    return name

        return None

    def get_dependencies(self, name: str) -> list[str]:
        """
        获取技能的依赖列表

        Args:
            name: 技能名称

        Returns:
            依赖的技能名称列表
        """
        skill = self.skills.get(name)
        if skill is None:
            return []

        # 递归获取所有依赖
        all_deps: set[str] = set()
        to_process = list(skill.metadata.dependencies)

        while to_process:
            dep_name = to_process.pop()
            if dep_name in all_deps:
                continue

            all_deps.add(dep_name)

            dep_skill = self.skills.get(dep_name)
            if dep_skill:
                for sub_dep in dep_skill.metadata.dependencies:
                    if sub_dep not in all_deps:
                        to_process.append(sub_dep)

        return list(all_deps)

    def get_load_errors(self) -> dict[str, str]:
        """获取加载错误"""
        return self._load_errors.copy()

    def reload(self) -> dict[str, Skill]:
        """重新加载所有技能"""
        return self.load_all()

    def __len__(self) -> int:
        return len(self.skills)

    def __contains__(self, name: str) -> bool:
        return name in self.skills

    def __iter__(self):
        return iter(self.skills.items())
