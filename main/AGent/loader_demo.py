"""
AgentLoader 使用示例

展示如何从 YAML/JSON/Python 文件加载 Agent
"""

import sys
from pathlib import Path

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))

from unittest.mock import Mock
from pyagentforge.building import AgentLoader, AgentFactory
from pyagentforge.tools.registry import ToolRegistry


def create_test_factory() -> AgentFactory:
    """创建测试用的 Factory"""
    tool_registry = ToolRegistry()
    provider_factory = lambda name: Mock(name=name)

    return AgentFactory(
        provider_factory=provider_factory,
        tool_registry=tool_registry,
    )


def demo_load_from_yaml():
    """演示从 YAML 加载"""
    print("=" * 60)
    print("1️⃣  从 YAML 加载构思专家")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    yaml_path = Path(__file__).parent / "agents" / "ideation.yaml"

    if yaml_path.exists():
        loaded = loader.load_from_yaml(str(yaml_path))

        print(f"✅ 加载成功：{loaded.schema.identity.name}")
        print(f"   - 状态：{loaded.state.value}")
        print(f"   - 文件：{loaded.file_path}")
        print(f"   - 版本：{loaded.schema.identity.version}")
        print(f"   - 描述：{loaded.schema.identity.description}")
        print(f"   - 标签：{', '.join(loaded.schema.identity.tags)}")
        print(f"   - 类别：{loaded.schema.category.value}")
        print(f"   - 成本：{loaded.schema.cost.value}")
        print(f"   - 温度：{loaded.schema.model.temperature}")
        print(f"   - 工具：{', '.join(loaded.schema.capabilities.tools)}")
        print(f"   - 依赖：{loaded.schema.dependencies.requires}")
        print()
    else:
        print(f"❌ 文件不存在：{yaml_path}")
        print()


def demo_load_from_json():
    """演示从 JSON 加载"""
    print("=" * 60)
    print("2️⃣  从 JSON 加载大纲专家")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    json_path = Path(__file__).parent / "agents" / "outline.json"

    if json_path.exists():
        loaded = loader.load_from_json(str(json_path))

        print(f"✅ 加载成功：{loaded.schema.identity.name}")
        print(f"   - 状态：{loaded.state.value}")
        print(f"   - 描述：{loaded.schema.identity.description}")
        print(f"   - 温度：{loaded.schema.model.temperature}")
        print(f"   - 依赖：{loaded.schema.dependencies.requires}")
        print(f"   - 使用场景：{', '.join(loaded.schema.behavior.use_when)}")
        print()
    else:
        print(f"❌ 文件不存在：{json_path}")
        print()


def demo_load_from_python():
    """演示从 Python 加载"""
    print("=" * 60)
    print("3️⃣  从 Python 加载写手")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    py_path = Path(__file__).parent / "agents" / "writer.py"

    if py_path.exists():
        loaded = loader.load_from_python(str(py_path))

        print(f"✅ 加载成功：{loaded.schema.identity.name}")
        print(f"   - 状态：{loaded.state.value}")
        print(f"   - 最大 Token：{loaded.schema.model.max_tokens}")
        print(f"   - 温度：{loaded.schema.model.temperature}")
        print(f"   - 依赖：{loaded.schema.dependencies.requires}")
        print(f"   - 可选依赖：{loaded.schema.dependencies.optional_requires}")
        print(f"   - 持久化会话：{loaded.schema.memory.persistent_session}")
        print()
    else:
        print(f"❌ 文件不存在：{py_path}")
        print()


def demo_auto_detect_format():
    """演示自动检测格式"""
    print("=" * 60)
    print("4️⃣  自动检测格式")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    agents_dir = Path(__file__).parent / "agents"

    for agent_file in agents_dir.iterdir():
        if agent_file.is_file() and agent_file.suffix in [".yaml", ".yml", ".json", ".py"]:
            if agent_file.name == "__init__.py":
                continue

            try:
                loaded = loader.load(str(agent_file))
                print(f"✅ {agent_file.name:20s} → {loaded.schema.identity.name}")
            except Exception as e:
                print(f"❌ {agent_file.name:20s} → 失败: {e}")

    print()


def demo_load_directory():
    """演示加载整个目录"""
    print("=" * 60)
    print("5️⃣  加载整个目录")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    agents_dir = Path(__file__).parent / "agents"

    if agents_dir.exists():
        loaded_agents = loader.load_directory(str(agents_dir))

        print(f"✅ 共加载 {len(loaded_agents)} 个 Agent：")
        for loaded in loaded_agents:
            print(f"   - {loaded.schema.identity.name:20s} ({loaded.schema.category.value})")
        print()
    else:
        print(f"❌ 目录不存在：{agents_dir}")
        print()


def demo_dependency_resolution():
    """演示依赖解析"""
    print("=" * 60)
    print("6️⃣  依赖解析")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    # 先加载所有 Agent
    agents_dir = Path(__file__).parent / "agents"
    if agents_dir.exists():
        loader.load_directory(str(agents_dir))

        # 解析依赖顺序
        agent_names = ["novel-ideation", "novel-outline", "novel-writer"]

        try:
            load_order = loader.resolve_dependencies(agent_names)

            print("📊 依赖解析结果（按加载顺序）：")
            for i, name in enumerate(load_order, 1):
                loaded = loader.get_loaded(name)
                if loaded:
                    deps = loaded.schema.dependencies.requires
                    print(f"   {i}. {name:20s} (依赖: {deps if deps else '无'})")

            print()
        except Exception as e:
            print(f"❌ 依赖解析失败：{e}")
            print()


def demo_list_and_state():
    """演示列出已加载和状态查询"""
    print("=" * 60)
    print("7️⃣  状态查询")
    print("=" * 60)

    factory = create_test_factory()
    loader = AgentLoader(factory)

    # 加载所有
    agents_dir = Path(__file__).parent / "agents"
    if agents_dir.exists():
        loader.load_directory(str(agents_dir))

        # 列出所有已加载
        loaded_list = loader.list_loaded()
        print(f"📋 已加载 Agent 数量：{len(loaded_list)}")
        print()

        # 查询每个 Agent 的状态
        print("📊 Agent 状态：")
        for name in loaded_list:
            state = loader.get_state(name)
            loaded = loader.get_loaded(name)
            if loaded:
                print(f"   - {name:20s} | {state.value:10s} | {loaded.schema.category.value}")
        print()


def main():
    """主演示流程"""
    print("\n" + "=" * 60)
    print("AgentLoader 功能演示")
    print("展示从 YAML/JSON/Python 三种格式加载 Agent")
    print("=" * 60 + "\n")

    # 1. 从 YAML 加载
    demo_load_from_yaml()

    # 2. 从 JSON 加载
    demo_load_from_json()

    # 3. 从 Python 加载
    demo_load_from_python()

    # 4. 自动检测格式
    demo_auto_detect_format()

    # 5. 加载整个目录
    demo_load_directory()

    # 6. 依赖解析
    demo_dependency_resolution()

    # 7. 状态查询
    demo_list_and_state()

    print("=" * 60)
    print("✅ AgentLoader 功能演示完成")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
