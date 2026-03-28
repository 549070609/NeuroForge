"""
子Agent调度工具

调度和执行子Agent。

子Agent 位于 mate-agent/subagents/ 目录下。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class SubagentStatus(str, Enum):
    """子Agent执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SubagentResult:
    """子Agent执行结果"""
    agent_id: str
    status: SubagentStatus
    output: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def get_subagent_path(subagent_id: str) -> Path | None:
    """
    获取子Agent的路径

    子Agent位于 mate-agent/subagents/{subagent-id}/ 目录下

    Args:
        subagent_id: 子Agent ID (如: builder-agent, analyzer-agent)

    Returns:
        子Agent目录路径或None
    """
    from main.Agent.core import get_agent_base_config

    config = get_agent_base_config()
    mate_agent_path = config.get_mate_agent_path()
    subagent_dir = mate_agent_path / "subagents" / subagent_id

    if subagent_dir.exists() and (subagent_dir / "agent.yaml").exists():
        return subagent_dir

    return None


class SpawnSubagentTool(MateAgentTool):
    """
    子Agent调度工具

    调度并执行子Agent，支持:
    - 单个子Agent执行
    - 并行执行多个子Agent
    - 超时控制
    - 结果汇总

    参数:
        subagent_id: 子Agent ID
        task: 任务描述
        inputs: 输入参数 (可选)
        timeout: 超时时间 (秒，可选)
    """

    name = "spawn_subagent"
    description = "调度并执行子Agent"
    category = "system"
    requires_confirmation = False
    timeout = 300  # 默认 5 分钟

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "subagent_id": {
                "type": "string",
                "description": "要调度的子Agent ID"
            },
            "task": {
                "type": "string",
                "description": "任务描述"
            },
            "inputs": {
                "type": "object",
                "description": "输入参数 (可选)"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间 (秒)",
                "default": 300
            },
            "context": {
                "type": "object",
                "description": "传递给子Agent的上下文 (可选)"
            }
        },
        "required": ["subagent_id", "task"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行子Agent调度

        Args:
            subagent_id: 子Agent ID
            task: 任务描述
            inputs: 输入参数
            timeout: 超时时间
            context: 上下文

        Returns:
            执行结果
        """
        subagent_id = kwargs.get("subagent_id")
        task = kwargs.get("task", "")
        inputs = kwargs.get("inputs", {})
        timeout = kwargs.get("timeout", 300)
        context = kwargs.get("context", {})
        subagent_executor = kwargs.get("subagent_executor")
        engine_factory = kwargs.get("engine_factory")

        if not subagent_id:
            return self._format_error("subagent_id 是必需参数", "MISSING_SUBAGENT_ID")

        if not task:
            return self._format_error("task 是必需参数", "MISSING_TASK")

        try:
            # 首先检查是否是子Agent (在 mate-agent/subagents/ 目录下)
            subagent_path = get_subagent_path(subagent_id)
            if subagent_path:
                # 找到子Agent，加载其信息
                agent = self._load_subagent_info(subagent_path, subagent_id)
            else:
                # 尝试从常规Agent目录查找
                directory = self._ensure_directory()
                agent = directory.get_agent(subagent_id)

            if not agent:
                return self._format_error(
                    f"子Agent '{subagent_id}' 不存在",
                    "SUBAGENT_NOT_FOUND"
                )

            # 执行子Agent
            result = await self._execute_subagent(
                agent=agent,
                task=task,
                inputs=inputs,
                timeout=timeout,
                context=context,
                subagent_executor=subagent_executor,
                engine_factory=engine_factory,
            )

            self._log_operation("spawn_subagent", {
                "subagent_id": subagent_id,
                "task_length": len(task),
                "timeout": timeout,
                "status": result.status.value,
            })

            return self._format_subagent_result(result)

        except asyncio.TimeoutError:
            return self._format_error(
                f"子Agent '{subagent_id}' 执行超时 ({timeout}秒)",
                "TIMEOUT"
            )
        except Exception as e:
            logger.exception(f"Failed to spawn subagent: {subagent_id}")
            return self._format_error(f"子Agent调度失败: {str(e)}", "SPAWN_FAILED")

    def _load_subagent_info(self, subagent_path: Path, subagent_id: str) -> Any:
        """
        从子Agent目录加载Agent信息

        Args:
            subagent_path: 子Agent目录路径
            subagent_id: 子Agent ID

        Returns:
            AgentInfo 实例
        """
        import yaml
        from main.Agent.core import AgentOrigin, AgentInfo

        agent_file = subagent_path / "agent.yaml"
        if not agent_file.exists():
            return None

        with open(agent_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        identity = data.get("identity", {})
        name = identity.get("name", subagent_id)

        system_prompt_path = subagent_path / "system_prompt.md"
        if not system_prompt_path.exists():
            system_prompt_path = None

        return AgentInfo(
            name=name,
            origin=AgentOrigin.LOCAL,
            namespace="subagent",
            agent_id=subagent_id,
            file_path=agent_file,
            system_prompt_path=system_prompt_path,
            description=identity.get("description", ""),
            tags=identity.get("tags", []),
            category=data.get("category", "coding"),
            priority=20,
            metadata=data,
        )

    async def _execute_subagent(
        self,
        agent: Any,
        task: str,
        inputs: dict[str, Any],
        timeout: int,
        context: dict[str, Any],
        subagent_executor: Any = None,
        engine_factory: Any = None,
    ) -> SubagentResult:
        """
        执行子Agent

        Args:
            agent: AgentInfo 实例
            task: 任务描述
            inputs: 输入参数
            timeout: 超时时间
            context: 上下文

        Returns:
            执行结果
        """
        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        result = SubagentResult(
            agent_id=agent.agent_id,
            status=SubagentStatus.RUNNING,
            started_at=started_at,
        )

        try:
            output = await asyncio.wait_for(
                self._run_subagent(
                    agent=agent,
                    task=task,
                    inputs=inputs,
                    context=context,
                    subagent_executor=subagent_executor,
                    engine_factory=engine_factory,
                ),
                timeout=timeout,
            )

            result.status = SubagentStatus.COMPLETED
            result.output = output

        except asyncio.TimeoutError:
            result.status = SubagentStatus.TIMEOUT
            result.error = f"执行超时 ({timeout}秒)"

        except Exception as e:
            result.status = SubagentStatus.FAILED
            result.error = str(e)

        finally:
            completed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            result.completed_at = completed_at

            # 计算执行时间
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            result.duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

        return result

    async def _run_subagent(
        self,
        agent: Any,
        task: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
        subagent_executor: Any = None,
        engine_factory: Any = None,
    ) -> str:
        """
        执行真实子Agent运行时。

        Args:
            agent: AgentInfo 实例
            task: 任务描述
            inputs: 输入参数
            context: 上下文
            subagent_executor: 注入的子Agent执行器
            engine_factory: 注入的引擎工厂

        Returns:
            执行输出
        """
        execution_prompt = self._build_execution_prompt(task, inputs, context)

        if subagent_executor is not None:
            result = subagent_executor(
                agent=agent,
                task=task,
                inputs=inputs,
                context=context,
                prompt=execution_prompt,
            )
            if inspect.isawaitable(result):
                result = await result
            return str(result)

        if engine_factory is not None:
            engine = self._create_engine(engine_factory, agent)
            if engine is None or not hasattr(engine, "run"):
                raise RuntimeError(f"无法为子Agent '{agent.agent_id}' 创建运行时")

            result = engine.run(execution_prompt)
            if inspect.isawaitable(result):
                result = await result
            return str(result)

        raise RuntimeError(
            f"子Agent '{agent.agent_id}' 运行时不可用，请注入 subagent_executor 或 engine_factory"
        )

    def _create_engine(self, engine_factory: Any, agent: Any) -> Any:
        """通过注入的工厂创建子Agent运行时。"""
        try:
            return engine_factory(agent.agent_id, agent)
        except TypeError:
            return engine_factory(agent.agent_id)

    def _build_execution_prompt(
        self,
        task: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """构造传递给子Agent运行时的执行提示。"""
        sections = [f"Task:\n{task}"]

        if inputs:
            sections.append(
                "Inputs:\n" + json.dumps(inputs, ensure_ascii=False, indent=2)
            )

        if context:
            sections.append(
                "Context:\n" + json.dumps(context, ensure_ascii=False, indent=2)
            )

        return "\n\n".join(sections)

    def _format_subagent_result(self, result: SubagentResult) -> str:
        """格式化子Agent执行结果"""
        output = {
            "success": result.status == SubagentStatus.COMPLETED,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "duration_ms": result.duration_ms,
        }

        if result.output:
            output["output"] = result.output

        if result.error:
            output["error"] = result.error

        if result.metadata:
            output["metadata"] = result.metadata

        return json.dumps(output, ensure_ascii=False, indent=2)


class SpawnMultipleSubagentsTool(MateAgentTool):
    """
    并行调度多个子Agent工具

    并行执行多个子Agent，并汇总结果。

    参数:
        subagents: 子Agent列表 (每个包含 agent_id 和 task)
        parallel: 是否并行执行 (默认 True)
        fail_fast: 是否在任一失败时立即停止 (默认 False)
    """

    name = "spawn_multiple_subagents"
    description = "并行调度多个子Agent"
    category = "system"
    requires_confirmation = False
    timeout = 600  # 默认 10 分钟

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "subagents": {
                "type": "array",
                "description": "子Agent列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "task": {"type": "string"},
                        "inputs": {"type": "object"}
                    },
                    "required": ["agent_id", "task"]
                }
            },
            "parallel": {
                "type": "boolean",
                "description": "是否并行执行",
                "default": True
            },
            "fail_fast": {
                "type": "boolean",
                "description": "是否在任一失败时立即停止",
                "default": False
            }
        },
        "required": ["subagents"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行多子Agent调度

        Args:
            subagents: 子Agent列表
            parallel: 是否并行执行
            fail_fast: 是否快速失败

        Returns:
            执行结果汇总
        """
        subagents = kwargs.get("subagents", [])
        parallel = kwargs.get("parallel", True)
        fail_fast = kwargs.get("fail_fast", False)

        if not subagents:
            return self._format_error("subagents 不能为空", "EMPTY_SUBAGENTS")

        try:
            directory = self._ensure_directory()

            # 验证所有子Agent
            for sa in subagents:
                agent_id = sa.get("agent_id")
                if not directory.get_agent(agent_id):
                    return self._format_error(
                        f"子Agent '{agent_id}' 不存在",
                        "SUBAGENT_NOT_FOUND"
                    )

            if parallel:
                results = await self._execute_parallel(subagents, directory, fail_fast)
            else:
                results = await self._execute_sequential(subagents, directory, fail_fast)

            # 汇总结果
            summary = self._summarize_results(results)

            self._log_operation("spawn_multiple_subagents", {
                "count": len(subagents),
                "parallel": parallel,
                "summary": summary,
            })

            return self._format_multiple_results(results, summary)

        except Exception as e:
            logger.exception("Failed to spawn multiple subagents")
            return self._format_error(f"多子Agent调度失败: {str(e)}", "SPAWN_FAILED")

    async def _execute_parallel(
        self,
        subagents: list[dict[str, Any]],
        directory: Any,
        fail_fast: bool,
    ) -> list[SubagentResult]:
        """并行执行"""
        spawn_tool = SpawnSubagentTool(agent_directory=self._directory)

        tasks = [
            spawn_tool.execute(
                subagent_id=sa["agent_id"],
                task=sa["task"],
                inputs=sa.get("inputs", {}),
            )
            for sa in subagents
        ]

        if fail_fast:
            # 使用 asyncio.gather 并在第一个失败时取消其他
            results = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            # 等待所有完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # 解析结果
        parsed_results = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                parsed_results.append(SubagentResult(
                    agent_id=subagents[i]["agent_id"],
                    status=SubagentStatus.FAILED,
                    error=str(result),
                ))
            else:
                # 解析 JSON 结果
                result_text = str(result)
                try:
                    data = json.loads(result_text)
                    parsed_results.append(SubagentResult(
                        agent_id=data.get("agent_id", subagents[i]["agent_id"]),
                        status=SubagentStatus(data.get("status", "completed")),
                        output=data.get("output", ""),
                        error=data.get("error", ""),
                    ))
                except (json.JSONDecodeError, ValueError):
                    parsed_results.append(SubagentResult(
                        agent_id=subagents[i]["agent_id"],
                        status=SubagentStatus.COMPLETED,
                        output=result_text,
                    ))

        return parsed_results

    async def _execute_sequential(
        self,
        subagents: list[dict[str, Any]],
        directory: Any,
        fail_fast: bool,
    ) -> list[SubagentResult]:
        """顺序执行"""
        spawn_tool = SpawnSubagentTool(agent_directory=self._directory)
        results = []

        for sa in subagents:
            try:
                result = await spawn_tool.execute(
                    subagent_id=sa["agent_id"],
                    task=sa["task"],
                    inputs=sa.get("inputs", {}),
                )

                import json
                data = json.loads(result)
                results.append(SubagentResult(
                    agent_id=sa["agent_id"],
                    status=SubagentStatus(data.get("status", "completed")),
                    output=data.get("output", ""),
                    error=data.get("error", ""),
                ))

                # 如果 fail_fast 且执行失败，停止
                if fail_fast and data.get("status") != "completed":
                    break

            except Exception as e:
                results.append(SubagentResult(
                    agent_id=sa["agent_id"],
                    status=SubagentStatus.FAILED,
                    error=str(e),
                ))
                if fail_fast:
                    break

        return results

    def _summarize_results(self, results: list[SubagentResult]) -> dict[str, int]:
        """汇总结果"""
        summary = {
            "total": len(results),
            "completed": 0,
            "failed": 0,
            "timeout": 0,
        }

        for r in results:
            if r.status == SubagentStatus.COMPLETED:
                summary["completed"] += 1
            elif r.status == SubagentStatus.TIMEOUT:
                summary["timeout"] += 1
            else:
                summary["failed"] += 1

        return summary

    def _format_multiple_results(
        self,
        results: list[SubagentResult],
        summary: dict[str, int],
    ) -> str:
        """格式化多子Agent结果"""
        import json

        output = {
            "success": summary["failed"] == 0 and summary["timeout"] == 0,
            "summary": summary,
            "results": [
                {
                    "agent_id": r.agent_id,
                    "status": r.status.value,
                    "output": r.output,
                    "error": r.error,
                }
                for r in results
            ],
        }

        return json.dumps(output, ensure_ascii=False, indent=2)
