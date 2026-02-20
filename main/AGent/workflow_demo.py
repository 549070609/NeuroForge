"""
完整工作流示例

展示如何使用三个 Agent 协作完成小说创作
"""

import sys
from pathlib import Path

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))

from unittest.mock import Mock
from pyagentforge.building import AgentLoader, AgentFactory
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.agents.registry import get_agent_registry


def create_test_factory() -> AgentFactory:
    """创建测试用的 Factory"""
    tool_registry = ToolRegistry()
    provider_factory = lambda name: Mock(name=name)
    registry = get_agent_registry()

    return AgentFactory(
        provider_factory=provider_factory,
        tool_registry=tool_registry,
        agent_registry=registry,
    )


def demo_workflow():
    """演示完整的工作流"""
    print("\n" + "=" * 70)
    print("📚 小说创作工作流演示")
    print("=" * 70 + "\n")

    # Step 1: 创建 Factory 和 Loader
    print("🔧 Step 1: 初始化...")
    factory = create_test_factory()
    loader = AgentLoader(factory)
    print("   ✅ Factory 和 Loader 已创建\n")

    # Step 2: 加载所有 Agent
    print("📂 Step 2: 加载 Agent 定义...")
    agents_dir = Path(__file__).parent / "agents"
    loaded_agents = loader.load_directory(str(agents_dir))

    print(f"   ✅ 共加载 {len(loaded_agents)} 个 Agent：")
    for loaded in loaded_agents:
        print(f"      - {loaded.schema.identity.name}")
    print()

    # Step 3: 解析依赖
    print("🔗 Step 3: 解析依赖关系...")
    agent_names = ["novel-ideation", "novel-outline", "novel-writer"]

    try:
        load_order = loader.resolve_dependencies(agent_names)
        print(f"   ✅ 正确的加载顺序：")
        for i, name in enumerate(load_order, 1):
            loaded = loader.get_loaded(name)
            if loaded:
                deps = loaded.schema.dependencies.requires
                deps_str = f" ← {', '.join(deps)}" if deps else " (基础层)"
                print(f"      {i}. {name}{deps_str}")
        print()
    except Exception as e:
        print(f"   ❌ 依赖解析失败：{e}\n")
        return

    # Step 4: 创建 Agent 实例
    print("🏭 Step 4: 创建 Agent 实例...")
    engines = {}
    for name in load_order:
        engine = factory.create_from_name(name)
        engines[name] = engine
        print(f"   ✅ 创建实例：{name}")
    print()

    # Step 5: 显示 Agent 配置
    print("📊 Step 5: Agent 配置概览...\n")

    for name, engine in engines.items():
        config = engine.config
        loaded = loader.get_loaded(name)

        if loaded:
            schema = loaded.schema
            print(f"   📝 {name}")
            print(f"      - 类别：{schema.category.value}")
            print(f"      - 成本：{schema.cost.value}")
            print(f"      - 模型：{schema.model.model}")
            print(f"      - 温度：{schema.model.temperature}")
            print(f"      - 最大 Token：{schema.model.max_tokens}")
            print(f"      - 工具：{', '.join(schema.capabilities.tools)}")
            print(f"      - 标签：{', '.join(schema.identity.tags)}")
            print()

    # Step 6: 模拟工作流执行
    print("🚀 Step 6: 模拟工作流执行...\n")

    project_name = "my-sci-fi-novel"
    novel_dir = Path(__file__).parent / "novels" / project_name

    # 创建目录结构
    print(f"   📁 创建项目目录：{project_name}")
    (novel_dir / "ideation").mkdir(parents=True, exist_ok=True)
    (novel_dir / "outline").mkdir(parents=True, exist_ok=True)
    (novel_dir / "chapters").mkdir(parents=True, exist_ok=True)
    print()

    # 模拟三个阶段
    stages = [
        {
            "name": "novel-ideation",
            "task": "为科幻小说《时空裂隙》创建构思",
            "output": "ideation/world-building.md, ideation/characters.md",
        },
        {
            "name": "novel-outline",
            "task": "基于构思创建10章大纲",
            "output": "outline/chapter-outline.md",
        },
        {
            "name": "novel-writer",
            "task": "撰写第1章：裂隙初现",
            "output": "chapters/chapter-01.md",
        },
    ]

    for i, stage in enumerate(stages, 1):
        print(f"   🎬 阶段 {i}: {stage['name']}")
        print(f"      - 任务：{stage['task']}")
        print(f"      - 输出：{stage['output']}")
        print(f"      - 状态：⏸️  模拟（需要实际 AI 模型）")
        print()

    # Step 7: 展示协作关系
    print("🤝 Step 7: Agent 协作关系...\n")
    print("   工作流图：")
    print()
    print("   ┌─────────────────┐")
    print("   │  novel-ideation │ (构思专家)")
    print("   │  - 世界观构建   │")
    print("   │  - 人物设定     │")
    print("   │  - 主题确定     │")
    print("   └────────┬────────┘")
    print("            │ 输出: ideation/")
    print("            ↓")
    print("   ┌─────────────────┐")
    print("   │  novel-outline  │ (大纲专家)")
    print("   │  - 章节规划     │")
    print("   │  - 情节设计     │")
    print("   │  - 节奏控制     │")
    print("   └────────┬────────┘")
    print("            │ 输出: outline/")
    print("            ↓")
    print("   ┌─────────────────┐")
    print("   │  novel-writer   │ (写手)")
    print("   │  - 章节撰写     │")
    print("   │  - 场景描写     │")
    print("   │  - 对话创作     │")
    print("   └─────────────────┘")
    print("            │")
    print("            ↓ 输出: chapters/")
    print("   ┌─────────────────┐")
    print("   │  完整小说作品   │")
    print("   └─────────────────┘")
    print()

    # Step 8: 使用 Registry 查询
    print("🔍 Step 8: Registry 查询功能...\n")
    registry = get_agent_registry()

    # 按标签查询
    print("   📌 按标签查询 [novel]:")
    novel_agents = registry.find_by_tags(["novel"])
    for agent in novel_agents:
        print(f"      - {agent.name}")
    print()

    # 按能力查询
    print("   🛠️  按能力查询 [write]:")
    write_agents = registry.find_by_capability("write")
    for agent in write_agents:
        print(f"      - {agent.name}")
    print()

    # 智能匹配
    print("   🎯 智能匹配任务：\"我需要构思一个科幻小说的创意\"")
    best_match = registry.find_best_for_task("我需要构思一个科幻小说的创意")
    if best_match:
        print(f"      ✅ 最佳匹配：{best_match.name}")
        print(f"         描述：{best_match.description}")
    print()

    # 总结
    print("=" * 70)
    print("✅ 工作流演示完成")
    print("=" * 70)
    print()
    print("📝 关键要点：")
    print("   1. 使用 AgentLoader 从 YAML/JSON/Python 加载 Agent")
    print("   2. 依赖解析确保正确的加载顺序")
    print("   3. AgentFactory 创建 Agent 实例")
    print("   4. 多 Agent 协作完成复杂任务")
    print("   5. Registry 提供智能发现和匹配")
    print()
    print("💡 下一步：")
    print("   - 配置真实的 AI Provider")
    print("   - 运行实际的小说创作任务")
    print("   - 观察三个 Agent 的协作效果")
    print()


if __name__ == "__main__":
    demo_workflow()
