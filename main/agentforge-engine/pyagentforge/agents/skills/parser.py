"""
技能解析器

解析 SKILL.md 文件，支持动态命令注入 (!`cmd`)
"""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from pyagentforge.agents.skills.models import Skill, SkillMetadata
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SkillParseError(Exception):
    """技能解析错误"""
    pass


# 复用 commands 模块的动态命令执行器
def _get_dynamic_executor():
    """延迟导入以避免循环依赖"""
    from pyagentforge.agents.commands.parser import DynamicCommandExecutor
    return DynamicCommandExecutor()


class SkillParser:
    """技能解析器 - 解析 YAML frontmatter + Markdown 格式，支持动态命令注入"""

    # 匹配 YAML frontmatter
    FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n(.*)$",
        re.DOTALL,
    )

    def __init__(
        self,
        enable_dynamic_injection: bool = True,
        dynamic_executor: Any = None,
    ) -> None:
        """
        初始化技能解析器

        Args:
            enable_dynamic_injection: 是否启用动态命令注入
            dynamic_executor: 动态命令执行器 (None 则使用默认)
        """
        self.enable_dynamic_injection = enable_dynamic_injection
        self._dynamic_executor = dynamic_executor

    @property
    def dynamic_executor(self):
        """获取动态命令执行器 (延迟加载)"""
        if self._dynamic_executor is None:
            self._dynamic_executor = _get_dynamic_executor()
        return self._dynamic_executor

    def parse(self, content: str, path: Path | None = None, inject_dynamic: bool | None = None) -> Skill:
        """
        解析技能文件内容

        Args:
            content: 文件内容
            path: 文件路径
            inject_dynamic: 是否注入动态命令 (None 使用默认设置)

        Returns:
            技能对象

        Raises:
            SkillParseError: 解析错误
        """
        match = self.FRONTMATTER_PATTERN.match(content)

        if not match:
            # 没有 frontmatter，整个内容作为 body
            logger.warning(
                "No frontmatter found, using entire content as body",
                extra_data={"path": str(path) if path else "unknown"},
            )
            body = content.strip()
            metadata = SkillMetadata(
                name=path.stem if path else "unknown",
                description="No description",
            )
        else:
            frontmatter_str = match.group(1)
            body = match.group(2).strip()

            try:
                metadata_dict = yaml.safe_load(frontmatter_str)
            except yaml.YAMLError as e:
                raise SkillParseError(f"Invalid YAML frontmatter: {e}") from e

            if not isinstance(metadata_dict, dict):
                raise SkillParseError("Frontmatter must be a YAML mapping")

            # 提取必需字段
            name = metadata_dict.pop("name", path.stem if path else "unknown")
            description = metadata_dict.pop("description", "")

            # 构建 metadata
            metadata = SkillMetadata(
                name=name,
                description=description,
                **{
                    k: v
                    for k, v in metadata_dict.items()
                    if k in SkillMetadata.model_fields
                },
            )

        # 动态命令注入
        should_inject = inject_dynamic if inject_dynamic is not None else self.enable_dynamic_injection
        if should_inject:
            body = self.dynamic_executor.inject(body)

        logger.debug(
            "Parsed skill",
            extra_data={"name": metadata.name, "path": str(path) if path else "unknown"},
        )

        return Skill(metadata=metadata, body=body, path=path)

    def parse_file(self, file_path: Path, inject_dynamic: bool | None = None) -> Skill:
        """
        解析技能文件

        Args:
            file_path: 文件路径
            inject_dynamic: 是否注入动态命令

        Returns:
            技能对象
        """
        if not file_path.exists():
            raise SkillParseError(f"Skill file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return self.parse(content, file_path, inject_dynamic)

    async def parse_async(self, content: str, path: Path | None = None, inject_dynamic: bool | None = None) -> Skill:
        """
        异步解析技能 (支持并行执行多个动态命令)

        Args:
            content: 文件内容
            path: 文件路径
            inject_dynamic: 是否注入动态命令

        Returns:
            技能对象
        """
        match = self.FRONTMATTER_PATTERN.match(content)

        if not match:
            body = content.strip()
            metadata = SkillMetadata(
                name=path.stem if path else "unknown",
                description="No description",
            )
        else:
            frontmatter_str = match.group(1)
            body = match.group(2).strip()

            try:
                metadata_dict = yaml.safe_load(frontmatter_str)
            except yaml.YAMLError as e:
                raise SkillParseError(f"Invalid YAML frontmatter: {e}") from e

            if not isinstance(metadata_dict, dict):
                raise SkillParseError("Frontmatter must be a YAML mapping")

            name = metadata_dict.pop("name", path.stem if path else "unknown")
            description = metadata_dict.pop("description", "")

            metadata = SkillMetadata(
                name=name,
                description=description,
                **{
                    k: v
                    for k, v in metadata_dict.items()
                    if k in SkillMetadata.model_fields
                },
            )

        # 异步动态命令注入
        should_inject = inject_dynamic if inject_dynamic is not None else self.enable_dynamic_injection
        if should_inject:
            body = await self.dynamic_executor.inject_async(body)

        return Skill(metadata=metadata, body=body, path=path)

    def validate(self, skill: Skill) -> list[str]:
        """
        验证技能

        Args:
            skill: 技能对象

        Returns:
            验证错误列表 (空列表表示通过)
        """
        errors: list[str] = []

        if not skill.metadata.name:
            errors.append("Skill name is required")

        if not skill.metadata.description:
            errors.append("Skill description is required")

        if not skill.body:
            errors.append("Skill body is empty")

        # 检查依赖循环
        if skill.metadata.name in skill.metadata.dependencies:
            errors.append(f"Skill depends on itself: {skill.metadata.name}")

        return errors
