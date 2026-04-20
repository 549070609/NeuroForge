"""
Skill Loader Plugin

Provides skills system functionality for loading and managing domain knowledge
"""

from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class SkillTool(BaseTool):
    """Skill Tool - Load and apply domain knowledge"""

    name = "skill"
    description = """Load domain-specific knowledge and skills.

    Use scenarios:
    - Load programming language knowledge
    - Load framework documentation
    - Load domain expertise

    Skills provide contextual knowledge to help with specific tasks.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill to load",
            },
            "action": {
                "type": "string",
                "enum": ["load", "unload", "list", "info"],
                "description": "Action to perform",
                "default": "load",
            },
        },
        "required": ["skill_name"],
    }
    timeout = 30
    risk_level = "low"

    def __init__(self, skill_loader: "SkillLoaderPlugin") -> None:
        self.skill_loader = skill_loader

    async def execute(
        self,
        skill_name: str,
        action: str = "load",
    ) -> str:
        """Execute skill action"""
        if action == "load":
            return await self.skill_loader.load_skill(skill_name)
        elif action == "unload":
            return await self.skill_loader.unload_skill(skill_name)
        elif action == "list":
            skills = self.skill_loader.list_skills()
            return "Available skills:\n" + "\n".join(f"  - {s}" for s in skills)
        elif action == "info":
            info = self.skill_loader.get_skill_info(skill_name)
            if info:
                return f"Skill: {skill_name}\n{info}"
            return f"Skill '{skill_name}' not found"
        else:
            return f"Unknown action: {action}"


class SkillLoaderPlugin(Plugin):
    """Skills system plugin"""

    metadata = PluginMetadata(
        id="skill.loader",
        name="Skill Loader",
        version="1.0.0",
        type=PluginType.SKILL,
        description="Provides skills system for loading and managing domain knowledge",
        author="PyAgentForge",
        provides=["skills"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._skills_dir: Path | None = None
        self._loaded_skills: dict[str, str] = {}
        self._available_skills: dict[str, dict] = {}

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Get skills directory from config
        config = self.context.config or {}
        skills_dir = config.get("skills_dir", "./skills")
        self._skills_dir = Path(skills_dir)

        # Scan for available skills
        await self._scan_skills()

        self.context.logger.info(
            "Skill loader plugin initialized",
            extra_data={
                "skills_dir": str(self._skills_dir),
                "available_skills": len(self._available_skills),
            },
        )

    async def _scan_skills(self) -> None:
        """Scan skills directory for available skills"""
        if not self._skills_dir or not self._skills_dir.exists():
            return

        self._available_skills.clear()

        # Look for SKILL.md files
        for skill_file in self._skills_dir.rglob("SKILL.md"):
            skill_name = skill_file.parent.name
            self._available_skills[skill_name] = {
                "path": str(skill_file),
                "name": skill_name,
            }

    async def load_skill(self, skill_name: str) -> str:
        """
        Load a skill by name

        Args:
            skill_name: Name of the skill to load

        Returns:
            Skill content or error message
        """
        if skill_name in self._loaded_skills:
            return f"Skill '{skill_name}' is already loaded."

        if skill_name not in self._available_skills:
            return f"Skill '{skill_name}' not found. Available skills: {list(self._available_skills.keys())}"

        skill_info = self._available_skills[skill_name]
        skill_path = Path(skill_info["path"])

        try:
            with open(skill_path, encoding="utf-8") as f:
                content = f.read()

            self._loaded_skills[skill_name] = content

            self.context.logger.info(
                "Skill loaded",
                extra_data={"skill_name": skill_name},
            )

            return f"Skill '{skill_name}' loaded successfully.\n\n{content[:1000]}..." if len(content) > 1000 else f"Skill '{skill_name}' loaded successfully.\n\n{content}"

        except Exception as e:
            self.context.logger.error(
                "Failed to load skill",
                extra_data={"skill_name": skill_name, "error": str(e)},
            )
            return f"Failed to load skill '{skill_name}': {str(e)}"

    async def unload_skill(self, skill_name: str) -> str:
        """
        Unload a skill

        Args:
            skill_name: Name of the skill to unload

        Returns:
            Status message
        """
        if skill_name not in self._loaded_skills:
            return f"Skill '{skill_name}' is not loaded."

        del self._loaded_skills[skill_name]

        self.context.logger.info(
            "Skill unloaded",
            extra_data={"skill_name": skill_name},
        )

        return f"Skill '{skill_name}' unloaded."

    def list_skills(self) -> list[str]:
        """
        List available skills

        Returns:
            List of skill names
        """
        return list(self._available_skills.keys())

    def list_loaded_skills(self) -> list[str]:
        """
        List currently loaded skills

        Returns:
            List of loaded skill names
        """
        return list(self._loaded_skills.keys())

    def get_skill_info(self, skill_name: str) -> str | None:
        """
        Get skill information

        Args:
            skill_name: Skill name

        Returns:
            Skill info or None
        """
        if skill_name in self._available_skills:
            info = self._available_skills[skill_name]
            return f"Path: {info['path']}"
        return None

    def get_loaded_content(self, skill_name: str) -> str | None:
        """
        Get loaded skill content

        Args:
            skill_name: Skill name

        Returns:
            Skill content or None
        """
        return self._loaded_skills.get(skill_name)

    def get_all_loaded_content(self) -> str:
        """
        Get all loaded skill content

        Returns:
            Combined content of all loaded skills
        """
        if not self._loaded_skills:
            return ""

        sections = []
        for name, content in self._loaded_skills.items():
            sections.append(f"## Skill: {name}\n\n{content}")

        return "\n\n---\n\n".join(sections)

    def get_tools(self) -> list[BaseTool]:
        """Return plugin provided tools"""
        return [SkillTool(self)]
