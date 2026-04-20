"""
AgentLoader Tests
"""

import json
import pytest
import tempfile
from pathlib import Path

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.agents.building.loader import AgentLoader, AgentLoadError, LoadState
from pyagentforge.agents.building.schema import AgentSchema, AgentIdentity, ModelConfiguration
from pyagentforge.agents.building.factory import AgentFactory
from pyagentforge.tools.registry import ToolRegistry
from unittest.mock import Mock


def create_test_factory() -> AgentFactory:
    """创建测试 Factory"""
    tool_registry = ToolRegistry()
    provider_factory = lambda name: Mock(name=name)

    return AgentFactory(
        provider_factory=provider_factory,
        tool_registry=tool_registry,
    )


def create_test_loader() -> AgentLoader:
    """创建测试 Loader"""
    factory = create_test_factory()
    return AgentLoader(factory)


class TestAgentLoaderYAML:
    """测试 YAML 加载"""

    def test_load_from_yaml(self):
        """测试从 YAML 加载"""
        loader = create_test_loader()

        yaml_content = """
identity:
  name: yaml-agent
  version: "1.0.0"
  description: "YAML test agent"
  tags:
    - test
    - yaml

category: coding
cost: moderate

model:
  provider: anthropic
  model: claude-sonnet-4-20250514
  temperature: 0.8
  max_tokens: 2048

capabilities:
  tools:
    - read
    - write
    - bash

behavior:
  system_prompt: "You are a YAML agent."
  use_when:
    - testing
    - yaml
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            tmp_path = f.name
        try:
            loaded = loader.load_from_yaml(tmp_path)

            assert loaded.state == LoadState.LOADED
            assert loaded.schema.identity.name == "yaml-agent"
            assert loaded.schema.identity.version == "1.0.0"
            assert "test" in loaded.schema.identity.tags
            assert loaded.schema.category == AgentCategory.CODING
            assert loaded.schema.model.temperature == 0.8
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_yaml_not_found(self):
        """测试加载不存在的 YAML"""
        loader = create_test_loader()

        with pytest.raises(AgentLoadError, match="File not found"):
            loader.load_from_yaml("non-existent.yaml")


class TestAgentLoaderJSON:
    """测试 JSON 加载"""

    def test_load_from_json(self):
        """测试从 JSON 加载"""
        loader = create_test_loader()

        json_content = {
            "identity": {
                "name": "json-agent",
                "version": "2.0.0",
                "description": "JSON test agent",
            },
            "category": "review",
            "cost": "cheap",
            "model": {
                "model": "claude-sonnet-4-20250514",
                "temperature": 0.5,
            },
            "capabilities": {
                "tools": ["read", "grep"],
            },
            "behavior": {
                "system_prompt": "You are a JSON agent.",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            tmp_path = f.name
        try:
            loaded = loader.load_from_json(tmp_path)

            assert loaded.state == LoadState.LOADED
            assert loaded.schema.identity.name == "json-agent"
            assert loaded.schema.category == AgentCategory.REVIEW
            assert loaded.schema.cost == AgentCost.CHEAP
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_json_not_found(self):
        """测试加载不存在的 JSON"""
        loader = create_test_loader()

        with pytest.raises(AgentLoadError, match="File not found"):
            loader.load_from_json("non-existent.json")


class TestAgentLoaderPython:
    """测试 Python 加载"""

    def test_load_from_python_with_schema_variable(self):
        """测试从 Python 加载（AGENT_SCHEMA 变量）"""
        loader = create_test_loader()

        python_code = '''
from pyagentforge.agents.building.schema import (
    AgentSchema,
    AgentIdentity,
    ModelConfiguration,
)
from pyagentforge.agents.metadata import AgentCategory

AGENT_SCHEMA = AgentSchema(
    identity=AgentIdentity(
        name="python-agent",
        version="1.0.0",
        description="Python test agent",
    ),
    category=AgentCategory.CODING,
    model=ModelConfiguration(model="claude-sonnet-4-20250514"),
)
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_code)
            tmp_path = f.name
        try:
            loaded = loader.load_from_python(tmp_path)

            assert loaded.state == LoadState.LOADED
            assert loaded.schema.identity.name == "python-agent"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_from_python_with_create_function(self):
        """测试从 Python 加载（create_schema 函数）"""
        loader = create_test_loader()

        python_code = '''
from pyagentforge.agents.building.schema import (
    AgentSchema,
    AgentIdentity,
)
from pyagentforge.agents.metadata import AgentCategory

def create_schema() -> AgentSchema:
    return AgentSchema(
        identity=AgentIdentity(name="function-agent"),
        category=AgentCategory.PLANNING,
    )
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_code)
            tmp_path = f.name
        try:
            loaded = loader.load_from_python(tmp_path)

            assert loaded.state == LoadState.LOADED
            assert loaded.schema.identity.name == "function-agent"
            assert loaded.schema.category == AgentCategory.PLANNING
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_python_no_schema(self):
        """测试加载没有 Schema 的 Python"""
        loader = create_test_loader()

        python_code = '''
# No schema defined
print("This file has no agent schema")
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(python_code)
            tmp_path = f.name
        try:
            with pytest.raises(AgentLoadError, match="No AGENT_SCHEMA"):
                loader.load_from_python(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestAgentLoaderAutoDetect:
    """测试自动检测格式"""

    def test_load_yaml_auto(self):
        """测试自动检测 YAML"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("identity:\n  name: auto-yaml\n")
            tmp_path = f.name
        try:
            loaded = loader.load(tmp_path)
            assert loaded.schema.identity.name == "auto-yaml"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_json_auto(self):
        """测试自动检测 JSON"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"identity": {"name": "auto-json"}}, f)
            tmp_path = f.name
        try:
            loaded = loader.load(tmp_path)
            assert loaded.schema.identity.name == "auto-json"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_python_auto(self):
        """测试自动检测 Python"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                "from pyagentforge.agents.building import AgentSchema, AgentIdentity\n"
                "AGENT_SCHEMA = AgentSchema(identity=AgentIdentity(name='auto-python'))\n"
            )
            tmp_path = f.name
        try:
            loaded = loader.load(tmp_path)
            assert loaded.schema.identity.name == "auto-python"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_load_unsupported_format(self):
        """测试不支持的格式"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some content")
            tmp_path = f.name
        try:
            with pytest.raises(AgentLoadError, match="Unsupported"):
                loader.load(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestAgentLoaderDirectory:
    """测试目录加载"""

    def test_load_directory(self):
        """测试加载目录"""
        loader = create_test_loader()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建多个 agent 文件
            yaml_path = Path(tmpdir) / "agent1.yaml"
            yaml_path.write_text(
                "identity:\n  name: dir-agent1\ncategory: coding\n"
            )

            json_path = Path(tmpdir) / "agent2.json"
            json_path.write_text('{"identity": {"name": "dir-agent2"}}')

            loaded = loader.load_directory(tmpdir)

            assert len(loaded) == 2
            names = [a.schema.identity.name for a in loaded]
            assert "dir-agent1" in names
            assert "dir-agent2" in names


class TestAgentLoaderUnload:
    """测试卸载"""

    def test_unload_agent(self):
        """测试卸载 Agent"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("identity:\n  name: unload-test\ncategory: coding\n")
            tmp_path = f.name
        try:
            loader.load(tmp_path)
            assert loader.get_loaded("unload-test") is not None

            result = loader.unload("unload-test")

            assert result
            assert loader.get_loaded("unload-test") is None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_unload_non_existent(self):
        """测试卸载不存在的 Agent"""
        loader = create_test_loader()

        result = loader.unload("non-existent")

        assert not result


class TestAgentLoaderReload:
    """测试重载"""

    def test_reload_agent(self):
        """测试重载 Agent"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("identity:\n  name: reload-test\n  description: Original\n")
            tmp_path = f.name
        try:
            loaded1 = loader.load(tmp_path)
            assert loaded1.schema.identity.description == "Original"

            # 修改文件
            Path(tmp_path).write_text(
                "identity:\n  name: reload-test\n  description: Modified\n"
            )

            loaded2 = loader.reload("reload-test")

            assert loaded2.schema.identity.description == "Modified"
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestAgentLoaderState:
    """测试状态查询"""

    def test_list_loaded(self):
        """测试列出已加载"""
        loader = create_test_loader()

        assert loader.list_loaded() == []

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("identity:\n  name: state-test\ncategory: coding\n")
            tmp_path = f.name
        try:
            loader.load(tmp_path)

            loaded = loader.list_loaded()

            assert len(loaded) == 1
            assert "state-test" in loaded
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_get_state(self):
        """测试获取状态"""
        loader = create_test_loader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("identity:\n  name: state-test2\ncategory: coding\n")
            tmp_path = f.name
        try:
            loader.load(tmp_path)

            state = loader.get_state("state-test2")

            assert state == LoadState.LOADED
        finally:
            Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
