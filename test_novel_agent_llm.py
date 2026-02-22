"""
真实 LLM 调用测试 - 小说大纲 Agent

测试流程:
1. 通过 mate-agent 创建小说大纲 Agent
2. 使用 GLM-4.7 模型调用小说大纲 Agent 生成大纲
3. 输出测试报告

运行方式:
  cd "E:/localproject/Agent Learn"
  py test_novel_agent_llm.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LLMTestReport:
    """LLM 测试报告"""

    def __init__(self):
        self.tests: list[dict[str, Any]] = []
        self.start_time = datetime.now()

    def add_test(self, name: str, success: bool, duration_ms: int,
                 details: dict[str, Any] | None = None,
                 error: str | None = None,
                 output: str | None = None):
        self.tests.append({
            "name": name,
            "success": success,
            "duration_ms": duration_ms,
            "details": details or {},
            "error": error,
            "output": output,
            "timestamp": datetime.now().isoformat(),
        })

    def generate_report(self) -> str:
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds() * 1000

        passed = sum(1 for t in self.tests if t["success"])
        failed = sum(1 for t in self.tests if not t["success"])

        report = f"""
================================================================================
                    小说大纲 Agent LLM 调用测试报告
================================================================================

测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%H:%M:%S')}
总耗时: {total_duration:.0f}ms

测试统计:
  - 总数: {len(self.tests)}
  - 通过: {passed}
  - 失败: {failed}
  - 成功率: {passed / len(self.tests) * 100 if self.tests else 0:.1f}%

--------------------------------------------------------------------------------
                              测试详情
--------------------------------------------------------------------------------
"""
        for i, test in enumerate(self.tests, 1):
            status = "PASS" if test["success"] else "FAIL"
            report += f"""
{i}. [{status}] {test['name']}
   耗时: {test['duration_ms']}ms
"""
            if test["error"]:
                report += f"   错误: {test['error']}\n"

            if test["details"]:
                for key, value in test["details"].items():
                    report += f"   {key}: {value}\n"

            if test["output"]:
                # 限制输出长度
                output = test["output"]
                if len(output) > 500:
                    output = output[:500] + "...\n[输出已截断，完整内容见下方]"
                report += f"\n   --- 输出 ---\n{output}\n"

        report += """
================================================================================
                              测试结论
================================================================================
"""
        if failed == 0:
            report += "所有测试通过! 小说大纲 Agent LLM 调用正常。\n"
        else:
            report += f"有 {failed} 个测试失败，请检查上述错误信息。\n"

        return report


async def create_novel_agent(report: LLMTestReport) -> bool:
    """创建小说大纲 Agent"""
    test_name = "创建小说大纲 Agent"
    start_time = datetime.now()

    try:
        from main.Agent import get_tool_registry

        logger.info("=" * 60)
        logger.info("步骤1: 创建小说大纲 Agent")
        logger.info("=" * 60)

        registry = get_tool_registry()
        create_tool = registry.get("create_agent")

        novel_agent_spec = {
            "description": "AI小说大纲生成专家 - 专门用于创作和优化小说大纲",
            "model": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "temperature": 0.7,
                "max_tokens": 4096
            },
            "tools": ["read", "write"],
            "limits": {
                "max_iterations": 5,
                "timeout": 120
            },
            "tags": ["creative", "writing", "novel"]
        }

        result = await create_tool.execute(
            agent_id="novel-outline-agent",
            spec=novel_agent_spec,
            template="reasoning",
            system_prompt="""# AI小说大纲生成专家

你是一位专业的小说大纲创作顾问，擅长帮助作者构建完整、引人入胜的故事框架。

## 核心能力

1. **世界观构建** - 设定故事背景、历史、魔法/科技体系
2. **角色设计** - 主角配角性格塑造、人物关系、成长弧线
3. **情节规划** - 三幕结构、冲突高潮、伏笔转折
4. **大纲输出** - 章节规划、字数预估、关键场景

## 输出格式

生成大纲时，请按以下格式输出：

```
# 小说标题

## 一、世界观设定
[描述故事背景]

## 二、主要角色
- 主角: [姓名] - [性格特点]
- 配角: ...

## 三、故事大纲

### 第一幕 (起)
[开篇内容]

### 第二幕 (承转)
[发展内容]

### 第三幕 (合)
[结局内容]

## 四、章节规划
第1章: [标题] - [简介]
...
```

请根据用户的需求，创作专业、详细的小说大纲。"""
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        result_data = json.loads(result)

        if result_data.get("success"):
            logger.info(f"成功创建: {result_data.get('message')}")
            report.add_test(
                name=test_name,
                success=True,
                duration_ms=duration_ms,
                details={
                    "agent_id": "novel-outline-agent",
                    "config_file": result_data.get('data', {}).get('config_file'),
                }
            )
            return True
        else:
            # 可能已存在
            error = result_data.get("error", "")
            if "已存在" in error:
                logger.info(f"Agent 已存在，继续测试")
                report.add_test(
                    name=test_name,
                    success=True,
                    duration_ms=duration_ms,
                    details={"message": "Agent 已存在"}
                )
                return True
            logger.error(f"创建失败: {error}")
            report.add_test(name=test_name, success=False, duration_ms=duration_ms, error=error)
            return False

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.exception(f"测试失败: {e}")
        report.add_test(name=test_name, success=False, duration_ms=duration_ms, error=str(e))
        return False


async def test_llm_call(report: LLMTestReport) -> bool:
    """使用真实 LLM 调用小说大纲 Agent"""
    test_name = "LLM 调用小说大纲 Agent"
    start_time = datetime.now()

    try:
        logger.info("=" * 60)
        logger.info("步骤2: 使用 GLM-4-Plus 调用小说大纲 Agent")
        logger.info("=" * 60)

        # 添加 agentforge-engine 到路径
        sys.path.insert(0, str(Path("main/agentforge-engine")))

        # 导入 GLM Provider
        from pyagentforge.providers.llm.glm.provider import GLMProvider, GLMEndpoint
        from main.Agent import AgentDirectory

        # 获取 Agent 信息
        directory = AgentDirectory()
        directory.scan()

        novel_agent = directory.get_agent("novel-outline-agent")
        if not novel_agent:
            raise RuntimeError("novel-outline-agent 不存在")

        # 读取系统提示词
        system_prompt = ""
        if novel_agent.system_prompt_path:
            system_prompt = novel_agent.system_prompt_path.read_text(encoding="utf-8")

        logger.info(f"系统提示词长度: {len(system_prompt)} 字符")

        # 创建 GLM Provider (使用 OpenAI 兼容端点)
        provider = GLMProvider(
            model="glm-4-plus",
            endpoint=GLMEndpoint.OPENAI,
            temperature=0.7,
            max_tokens=4096,
        )

        # 构建请求
        user_prompt = """请帮我创作一个科幻悬疑小说的大纲，主题是关于一个程序员发现自己写的代码开始有了自我意识。

要求:
1. 字数控制在 2000 字左右的大纲
2. 包含完整的三幕结构
3. 至少规划 10 个章节
4. 角色要有人性化的冲突和成长"""

        messages = [
            {"role": "user", "content": user_prompt}
        ]

        logger.info("正在调用 GLM-4-Plus 生成小说大纲...")
        logger.info(f"用户提示: {user_prompt[:100]}...")

        # 调用 LLM
        response = await provider.create_message(
            system=system_prompt,
            messages=messages,
            tools=[],  # 无工具调用
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # 提取输出
        output_text = ""
        if hasattr(response, 'content') and response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    output_text += block.text
        elif hasattr(response, 'text'):
            output_text = response.text

        if output_text:
            logger.info("=" * 60)
            logger.info("生成的小说大纲:")
            logger.info("=" * 60)
            print(output_text)
            logger.info("=" * 60)

            report.add_test(
                name=test_name,
                success=True,
                duration_ms=duration_ms,
                details={
                    "model": "glm-4-plus",
                    "endpoint": "openai",
                    "system_prompt_length": len(system_prompt),
                    "output_length": len(output_text),
                },
                output=output_text
            )
            return True
        else:
            report.add_test(
                name=test_name,
                success=False,
                duration_ms=duration_ms,
                error="LLM 返回空内容"
            )
            return False

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.exception(f"LLM 调用失败: {e}")
        report.add_test(
            name=test_name,
            success=False,
            duration_ms=duration_ms,
            error=str(e)
        )
        return False


async def cleanup(report: LLMTestReport) -> bool:
    """清理测试 Agent"""
    test_name = "清理测试 Agent"
    start_time = datetime.now()

    try:
        from main.Agent import get_tool_registry

        logger.info("=" * 60)
        logger.info("步骤3: 清理测试 Agent")
        logger.info("=" * 60)

        registry = get_tool_registry()
        delete_tool = registry.get("delete_agent")

        result = await delete_tool.execute(
            agent_id="novel-outline-agent",
            backup=False,
            force=True,
        )

        result_data = json.loads(result)
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        if result_data.get("success"):
            logger.info(f"清理成功: {result_data.get('message')}")
            report.add_test(
                name=test_name,
                success=True,
                duration_ms=duration_ms,
                details={"deleted_agent": "novel-outline-agent"}
            )
        else:
            logger.info(f"清理结果: {result_data.get('error', 'unknown')}")
            report.add_test(
                name=test_name,
                success=True,
                duration_ms=duration_ms,
                details={"message": result_data.get('error', 'already deleted')}
            )
        return True

    except Exception as e:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.exception(f"清理失败: {e}")
        report.add_test(name=test_name, success=False, duration_ms=duration_ms, error=str(e))
        return False


async def main():
    """主测试函数"""
    logger.info("=" * 80)
    logger.info("           小说大纲 Agent LLM 调用测试")
    logger.info("=" * 80)

    report = LLMTestReport()

    # 执行测试
    success = await create_novel_agent(report)
    if success:
        await test_llm_call(report)
    await cleanup(report)

    # 生成报告
    report_text = report.generate_report()
    print(report_text)

    # 保存报告
    report_path = Path(__file__).parent / "llm_test_report.md"
    report_path.write_text(f"```\n{report_text}\n```\n", encoding="utf-8")
    logger.info(f"测试报告已保存到: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
