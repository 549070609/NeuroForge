"""
AgentBuilder 使用示例

展示如何使用流畅 API 快速创建小说创作 Agent
"""

import sys
from pathlib import Path

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.building import AgentBuilder, AgentTemplate


def create_ideation_agent_with_builder():
    """使用 Builder 创建构思专家"""
    print("📝 使用 AgentBuilder 创建构思专家...")

    schema = (
        AgentBuilder()
        # 身份配置
        .with_name("quick-ideation")
        .with_description("快速构思专家 - 使用 Builder 创建")
        .with_version("1.0.0")
        .with_tags(["novel", "creative", "ideation"])
        # 模型配置
        .with_model("claude-sonnet-4-20250514")
        .with_provider("anthropic")
        .with_temperature(0.9)
        .with_max_tokens(4096)
        # 能力配置
        .add_tools(["read", "write", "bash"])
        # 行为配置
        .with_prompt(
            "你是一位富有创意的小说构思专家。\n"
            "专注于：世界观构建、人物设定、主题确定。\n"
            "输出保存在：novels/{project}/ideation/ 目录"
        )
        .use_when(["构思", "创意", "设定"])
        .avoid_when(["撰写正文", "规划情节"])
        .with_key_trigger(r"\b(构思|创意|ideation)\b")
        # 限制配置
        .readonly(False)
        .background(True)
        .max_concurrent(2)
        # 分类配置
        .with_category(AgentCategory.PLANNING)
        .with_cost(AgentCost.MODERATE)
        # 记忆配置
        .with_memory(max_messages=100)
        # 构建并注册
        .build_and_register()
    )

    print(f"✅ 创建成功：{schema.identity.name}")
    print(f"   - 版本：{schema.identity.version}")
    print(f"   - 类别：{schema.category.value}")
    print(f"   - 成本：{schema.cost.value}")
    print(f"   - 标签：{', '.join(schema.identity.tags)}")
    print()

    return schema


def create_outline_agent_with_builder():
    """使用 Builder 创建大纲专家"""
    print("📋 使用 AgentBuilder 创建大纲专家...")

    schema = (
        AgentBuilder()
        .with_name("quick-outline")
        .with_description("快速大纲专家 - 使用 Builder 创建")
        .with_tags(["novel", "planning", "outline"])
        .with_model("claude-sonnet-4-20250514")
        .with_temperature(0.7)  # 中等温度，结构化思维
        .add_tools(["read", "write", "bash"])
        .with_prompt(
            "你是一位专业的小说大纲规划师。\n"
            "专注于：章节规划、情节设计、节奏控制。\n"
            "依赖：需要构思专家的输出。\n"
            "输出保存在：novels/{project}/outline/ 目录"
        )
        .use_when(["大纲", "章节", "情节"])
        .requires(["novel-ideation"])  # 依赖构思专家
        .with_category(AgentCategory.PLANNING)
        .with_cost(AgentCost.MODERATE)
        .build_and_register()
    )

    print(f"✅ 创建成功：{schema.identity.name}")
    print(f"   - 依赖：{schema.dependencies.requires}")
    print()

    return schema


def create_writer_agent_with_builder():
    """使用 Builder 创建写手"""
    print("✍️ 使用 AgentBuilder 创建写手...")

    schema = (
        AgentBuilder()
        .with_name("quick-writer")
        .with_description("快速写手 - 使用 Builder 创建")
        .with_tags(["novel", "writing", "creative"])
        .with_model("claude-sonnet-4-20250514")
        .with_temperature(0.85)  # 中高温度，创意写作
        .with_max_tokens(8192)  # 更大的 token 限制
        .add_tools(["read", "write", "bash"])
        .with_prompt(
            "你是一位才华横溢的小说写手。\n"
            "专注于：章节撰写、场景描写、对话创作。\n"
            "依赖：需要大纲专家的输出。\n"
            "输出保存在：novels/{project}/chapters/ 目录"
        )
        .use_when(["撰写", "章节", "场景"])
        .requires(["novel-outline"])  # 依赖大纲专家
        .with_category(AgentCategory.CODING)
        .with_cost(AgentCost.EXPENSIVE)  # 高成本
        .with_memory(max_messages=150)  # 更大记忆
        .persistent_session(True)  # 持久化会话
        .build_and_register()
    )

    print(f"✅ 创建成功：{schema.identity.name}")
    print(f"   - 最大 Token：{schema.model.max_tokens}")
    print(f"   - 持久化会话：{schema.memory.persistent_session}")
    print()

    return schema


def demo_builder_features():
    """展示 Builder 的各种功能"""
    print("=" * 60)
    print("AgentBuilder 功能演示")
    print("=" * 60)
    print()

    # 1. 基础创建
    print("1️⃣  基础创建演示")
    create_ideation_agent_with_builder()

    # 2. 依赖配置
    print("2️⃣  依赖配置演示")
    create_outline_agent_with_builder()

    # 3. 高级配置
    print("3️⃣  高级配置演示")
    create_writer_agent_with_builder()

    # 4. 继承功能
    print("4️⃣  继承功能演示")
    base_schema = (
        AgentBuilder()
        .with_name("base-novel-agent")
        .with_model("claude-sonnet-4-20250514")
        .add_tools(["read", "write"])
        .with_category(AgentCategory.PLANNING)
        .build()
    )

    derived_schema = (
        AgentBuilder()
        .with_name("derived-agent")
        .inherit_from(base_schema)
        .with_description("继承自基础 Agent")
        .build()
    )

    print(f"✅ 继承成功：{derived_schema.identity.name}")
    print(f"   - 继承的模型：{derived_schema.model.model}")
    print(f"   - 继承的工具：{derived_schema.capabilities.tools}")
    print()

    # 5. 模板使用
    print("5️⃣  模板使用演示")
    custom_planner = (
        AgentTemplate.planner()
        .with_name("novel-planner")
        .with_description("小说规划专用")
        .with_temperature(0.8)
        .build()
    )

    print(f"✅ 模板创建成功：{custom_planner.identity.name}")
    print(f"   - 类别：{custom_planner.category.value}")
    print(f"   - 温度：{custom_planner.model.temperature}")
    print()

    print("=" * 60)
    print("✅ AgentBuilder 功能演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo_builder_features()
