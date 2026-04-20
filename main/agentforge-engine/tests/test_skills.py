"""
技能系统测试
"""

import pytest

from pyagentforge.agents.skills.models import Skill, SkillMetadata
from pyagentforge.agents.skills.parser import SkillParser
from pyagentforge.agents.skills.loader import SkillLoader


class TestSkillParser:
    """技能解析器测试"""

    def test_parse_with_frontmatter(self) -> None:
        """测试解析带 frontmatter 的技能"""
        content = """---
name: test-skill
description: A test skill
version: 1.0.0
triggers:
  - test
  - demo
---

# Test Skill

This is the skill body.
"""
        parser = SkillParser()
        skill = parser.parse(content)

        assert skill.metadata.name == "test-skill"
        assert skill.metadata.description == "A test skill"
        assert skill.metadata.version == "1.0.0"
        assert "test" in skill.metadata.triggers
        assert "Test Skill" in skill.body

    def test_parse_without_frontmatter(self) -> None:
        """测试解析不带 frontmatter 的技能"""
        content = "# Simple Skill\n\nJust content."
        parser = SkillParser()
        skill = parser.parse(content, path=None)

        assert "Simple Skill" in skill.body

    def test_validate_skill(self) -> None:
        """测试技能验证"""
        skill = Skill(
            metadata=SkillMetadata(
                name="test",
                description="Test skill",
            ),
            body="Content",
        )

        parser = SkillParser()
        errors = parser.validate(skill)

        assert len(errors) == 0


class TestSkillLoader:
    """技能加载器测试"""

    def test_get_descriptions(self, tmp_path) -> None:
        """测试获取技能描述"""
        # 创建测试技能文件
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test description
---
# Test
""")

        loader = SkillLoader(skills_dir=tmp_path)
        loader.load_all()

        descriptions = loader.get_descriptions()
        assert "test-skill" in descriptions

    def test_match_skill(self, tmp_path) -> None:
        """测试技能匹配"""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test
triggers:
  - python
  - code
---
# Test
""")

        loader = SkillLoader(skills_dir=tmp_path)
        loader.load_all()

        matched = loader.match_skill("I need help with python")
        assert matched == "test-skill"

        not_matched = loader.match_skill("I need help with cooking")
        assert not_matched is None
