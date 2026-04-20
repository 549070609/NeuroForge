"""
思维链系统使用示例

演示如何使用思维链系统增强 Agent 解决问题的能力。
"""

import asyncio

# 模拟环境设置
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
from pyagentforge.plugins.integration.chain_of_thought.models import (
    ChainOfThought,
    Constraint,
    ConstraintType,
    CoTPhase,
)


async def example_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("示例 1: 基础思维链使用")
    print("=" * 60)

    # 创建管理器
    manager = ChainOfThoughtManager()

    # 加载调试思维链
    cot = manager.load_cot("debugging")

    if cot:
        print(f"\n加载思维链: {cot.name}")
        print(f"描述: {cot.description}")
        print(f"阶段数: {len(cot.phases)}")

        # 显示阶段
        print("\n阶段列表:")
        for i, phase in enumerate(cot.get_ordered_phases(), 1):
            print(f"  {i}. {phase.name}")
            print(f"     约束数: {len(phase.constraints)}")
    else:
        print("未找到 debugging 思维链模板")


async def example_create_custom_cot():
    """创建自定义思维链示例"""
    print("\n" + "=" * 60)
    print("示例 2: 创建自定义思维链")
    print("=" * 60)

    manager = ChainOfThoughtManager()

    # 定义自定义思维链
    custom_cot = manager.create_cot_from_template(
        name="api_integration",
        description="API 集成开发流程",
        phases=[
            {
                "name": "research",
                "prompt": "1. 研究 API 文档\n2. 理解认证方式\n3. 列出需要的端点",
                "order": 0,
                "constraints": [
                    {"description": "必须列出至少3个端点", "type": "soft"},
                ],
            },
            {
                "name": "design",
                "prompt": "1. 设计数据模型\n2. 设计错误处理\n3. 设计缓存策略",
                "order": 1,
                "constraints": [
                    {"description": "必须包含错误处理设计", "type": "hard"},
                ],
            },
            {
                "name": "implement",
                "prompt": "1. 实现认证\n2. 实现各端点调用\n3. 添加重试逻辑",
                "order": 2,
                "constraints": [
                    {"description": "每个端点必须有单元测试", "type": "hard"},
                ],
            },
            {
                "name": "verify",
                "prompt": "1. 运行集成测试\n2. 验证错误处理\n3. 性能测试",
                "order": 3,
                "constraints": [],
            },
        ],
        source="agent",
    )

    print(f"\n创建自定义思维链: {custom_cot.name}")
    print(f"阶段: {[p.name for p in custom_cot.phases]}")

    # 保存
    manager.save_agent_cot(custom_cot)
    print("已保存为 Agent 自生成思维链")


async def example_plan_validation():
    """计划验证示例"""
    print("\n" + "=" * 60)
    print("示例 3: 计划约束验证")
    print("=" * 60)

    manager = ChainOfThoughtManager()

    # 创建带约束的思维链
    cot = ChainOfThought(
        name="secure_coding",
        description="安全编码流程",
        phases=[
            CoTPhase(
                name="plan",
                prompt="规划实现",
                constraints=[
                    Constraint("必须考虑输入验证", ConstraintType.HARD),
                    Constraint("必须包含安全测试", ConstraintType.HARD),
                    Constraint("建议使用参数化查询", ConstraintType.SOFT),
                ],
                order=0,
            ),
        ],
    )

    manager.set_current_cot(cot)
    manager.start_execution("example_session")

    # 测试计划 1: 缺少安全测试
    bad_plan = [
        {"description": "实现功能"},
        {"description": "添加输入验证"},
        {"description": "编写单元测试"},
    ]

    is_valid, violations = manager.validate_plan_against_cot(bad_plan)

    print("\n测试计划 1 (缺少安全测试):")
    print(f"  验证结果: {'通过' if is_valid else '失败'}")
    print(f"  违反数: {len(violations)}")

    for v in violations:
        icon = "❗" if v.constraint_type == ConstraintType.HARD else "⚠️"
        print(f"  {icon} {v.constraint_description}")

    # 测试计划 2: 符合约束
    good_plan = [
        {"description": "实现功能"},
        {"description": "添加输入验证"},
        {"description": "编写安全测试"},
        {"description": "使用参数化查询"},
    ]

    is_valid, violations = manager.validate_plan_against_cot(good_plan)

    print("\n测试计划 2 (符合约束):")
    print(f"  验证结果: {'通过' if is_valid else '失败'}")
    print(f"  违反数: {len(violations)}")


async def example_system_prompt_generation():
    """系统提示生成示例"""
    print("\n" + "=" * 60)
    print("示例 4: 生成系统提示扩展")
    print("=" * 60)

    manager = ChainOfThoughtManager()

    cot = manager.load_cot("problem_solving")

    if cot:
        manager.set_current_cot(cot)

        guidance = manager.generate_system_prompt_extension()

        print("\n生成的系统提示扩展:")
        print("-" * 40)
        print(guidance[:500] + "..." if len(guidance) > 500 else guidance)


async def example_execution_tracking():
    """执行跟踪示例"""
    print("\n" + "=" * 60)
    print("示例 5: 执行跟踪")
    print("=" * 60)

    manager = ChainOfThoughtManager()

    cot = ChainOfThought(
        name="example",
        description="示例思维链",
        phases=[
            CoTPhase("understand", "理解问题", order=0),
            CoTPhase("solve", "解决问题", order=1),
            CoTPhase("verify", "验证结果", order=2),
        ],
    )

    manager.set_current_cot(cot)

    # 开始执行
    trace = manager.start_execution("demo_session")

    print(f"\n开始执行跟踪: {trace.cot_name}")
    print(f"会话 ID: {trace.session_id}")

    # 记录阶段结果
    manager.record_phase_result("understand", "问题是计算斐波那契数列")
    manager.record_phase_result("solve", "使用动态规划实现")
    manager.record_phase_result("verify", "测试通过，结果正确")

    # 记录计划
    manager.record_plan([
        {"description": "分析需求"},
        {"description": "编写代码"},
        {"description": "测试验证"},
    ])

    # 完成执行
    manager.complete_execution(
        success=True,
        reflection="使用动态规划比递归更高效"
    )

    # 查看轨迹
    trace = manager.get_execution_trace()
    print(f"\n执行完成: {'成功' if trace.success else '失败'}")
    print(f"阶段结果数: {len(trace.phase_results)}")
    print(f"计划步骤数: {len(trace.plan_steps)}")
    print(f"反思: {trace.reflection}")


async def main():
    """运行所有示例"""
    await example_basic_usage()
    await example_create_custom_cot()
    await example_plan_validation()
    await example_system_prompt_generation()
    await example_execution_tracking()

    print("\n" + "=" * 60)
    print("所有示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
