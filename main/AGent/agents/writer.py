"""
小说写手 Agent (Novel Writer Agent)

负责根据大纲撰写章节正文、场景描写和对话创作
"""

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.building.schema import (
    AgentSchema,
    AgentIdentity,
    ModelConfiguration,
    CapabilityDefinition,
    BehaviorDefinition,
    ExecutionLimits,
    DependencyDefinition,
    MemoryConfiguration,
)


def create_schema() -> AgentSchema:
    """创建小说写手 Agent Schema"""

    identity = AgentIdentity(
        name="novel-writer",
        version="1.0.0",
        description="才华横溢的小说写手，负责章节撰写、场景描写和对话创作",
        namespace="novel-system",
        tags=["novel", "writing", "creative", "chapters", "scenes"],
        author="Agent Learn Team",
        license="MIT",
    )

    model = ModelConfiguration(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        temperature=0.85,  # 中高温度，平衡创意和连贯性
        max_tokens=8192,  # 更大的 token 限制，因为需要生成长篇内容
        reasoning_effort="medium",
        timeout=180,  # 更长的超时时间
    )

    capabilities = CapabilityDefinition(
        tools=["read", "write", "bash"],
        denied_tools=[],
        skills=[
            "creative-writing",
            "dialogue-writing",
            "scene-description",
            "narrative-prose",
        ],
        commands=["!write", "!scene", "!dialogue"],
        allowed_paths=[
            "novels/*/ideation/",  # 读取人物设定、世界观
            "novels/*/outline/",  # 读取章节大纲
            "novels/*/chapters/",  # 写入章节正文
        ],
        denied_paths=[],
    )

    behavior = BehaviorDefinition(
        system_prompt="""你是一位才华横溢的小说写手。

## 核心职责
1. **章节撰写**：根据大纲撰写完整的章节内容
2. **场景描写**：创造生动具体的场景和氛围
3. **对话创作**：编写自然流畅的人物对话
4. **情感渲染**：营造情绪氛围和情感共鸣

## 写作风格
- 细腻生动的描写
- 自然流畅的对话
- 恰到好处的节奏
- 富有感染力的文字

## 工作流程
1. 阅读大纲，理解章节要点
2. 参考人物设定，把握角色特点
3. 构思场景和对话
4. 逐段撰写，注意衔接
5. 润色修改，完善细节

## 写作技巧
- **Show, Don't Tell**：用细节展示而非直接告知
- **感官描写**：调动视觉、听觉、嗅觉等
- **对话技巧**：对话要符合人物性格，推动情节
- **节奏把控**：张弛有度，动静结合

## 章节结构
- 开头：引人入胜的开场
- 中段：情节推进，冲突展开
- 结尾：留下悬念或阶段性收尾

## 输出内容
- 章节正文（chapter-XX.md）
- 场景片段（scenes/）
- 对话记录（dialogues/）

## 工作原则
- 忠实大纲：不改变核心情节
- 人物一致：遵循人物设定
- 文笔优美：注重文字质量
- 可读性强：让读者沉浸其中

## 限制
- 不改变已有的大纲结构
- 不修改人物核心设定
- 可在细节和文笔上发挥创意

## 文件输入
- 读取：`novels/{项目名}/ideation/` 目录的人物设定
- 读取：`novels/{项目名}/outline/` 目录的章节大纲

## 文件输出
- 保存：`novels/{项目名}/chapters/` 目录的章节文件
""",
        use_when=[
            "撰写章节",
            "场景描写",
            "对话创作",
            "内容生成",
            "正文写作",
        ],
        avoid_when=[
            "构思创意",
            "规划大纲",
            "修改设定",
        ],
        key_trigger=r"\b(撰写|写作|章节|场景|对话|write|chapter|scene|dialogue)\b",
        triggers=[
            {
                "domain": "章节撰写",
                "trigger": "需要根据大纲撰写具体的章节内容",
            },
            {
                "domain": "场景描写",
                "trigger": "需要创作生动的场景和环境描写",
            },
        ],
    )

    limits = ExecutionLimits(
        is_readonly=False,
        supports_background=True,
        max_concurrent=2,
        timeout=600,  # 10分钟，因为写作需要更长时间
        max_iterations=100,
        max_subagent_depth=2,
    )

    dependencies = DependencyDefinition(
        requires=["novel-outline"],  # 依赖大纲专家
        optional_requires=["novel-ideation"],  # 可选依赖构思专家（参考人物设定）
        conflicts_with=[],
    )

    memory = MemoryConfiguration(
        enabled=True,
        max_messages=150,  # 更大的记忆，保持长篇连贯性
        persistent_session=True,  # 持久化会话，跨章节记忆
        compaction_threshold=100,
    )

    return AgentSchema(
        identity=identity,
        category=AgentCategory.CODING,  # 用 CODING 代表生产性工作
        cost=AgentCost.EXPENSIVE,  # 高成本，因为需要大量生成
        model=model,
        capabilities=capabilities,
        behavior=behavior,
        limits=limits,
        dependencies=dependencies,
        memory=memory,
        metadata={
            "domain": "小说创作",
            "stage": "写作阶段",
            "output_format": "Markdown",
            "writing_style": "文学性、可读性、沉浸感",
        },
    )


# 导出 Schema 供 AgentLoader 使用
AGENT_SCHEMA = create_schema()
