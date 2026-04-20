"""
技能注册表

管理技能的注册和状态
"""

from pyagentforge.agents.skills.loader import SkillLoader
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SkillRegistry:
    """技能注册表 - 跟踪已加载的技能"""

    def __init__(self, loader: SkillLoader) -> None:
        self.loader = loader
        self.loaded_skills: set[str] = set()

    def is_loaded(self, name: str) -> bool:
        """检查技能是否已加载到当前上下文"""
        return name in self.loaded_skills

    def mark_loaded(self, name: str) -> None:
        """标记技能为已加载"""
        self.loaded_skills.add(name)
        logger.debug(
            "Marked skill as loaded",
            extra_data={"skill": name},
        )

    def mark_unloaded(self, name: str) -> None:
        """标记技能为未加载"""
        self.loaded_skills.discard(name)

    def clear_loaded(self) -> None:
        """清除已加载记录"""
        self.loaded_skills.clear()

    def get_available_skills(self) -> list[str]:
        """获取所有可用技能"""
        return list(self.loader.skills.keys())

    def get_skill(self, name: str):
        """获取技能"""
        return self.loader.get(name)

    def get_loaded_skills(self) -> set[str]:
        """获取已加载的技能集合"""
        return self.loaded_skills.copy()

    def should_load(self, name: str) -> bool:
        """
        检查是否应该加载技能

        Args:
            name: 技能名称

        Returns:
            True 如果技能存在且未加载
        """
        return name in self.loader and name not in self.loaded_skills
