"""
团队协作系统

CrewAI 风格的角色驱动多 Agent 协作。
每个 Agent 有 role/goal/backstory，
TeamExecutor 按 process 模式编排执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyagentforge.utils.logging import get_logger
from pyagentforge.workflow.graph import END, StepNode, WorkflowGraph

logger = get_logger(__name__)


class TeamProcess(str, Enum):
    """团队执行流程"""
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


@dataclass
class AgentRole:
    """Agent 角色定义"""

    name: str
    role: str
    goal: str
    backstory: str = ""
    agent_type: str = "code"
    tools: list[str] | str = "*"
    max_iterations: int = 20

    def to_system_prompt(self) -> str:
        """将角色信息转化为 system prompt"""
        parts = [
            f"# Role: {self.role}",
            f"\n## Goal\n{self.goal}",
        ]
        if self.backstory:
            parts.append(f"\n## Background\n{self.backstory}")
        parts.append(
            "\n## Instructions\n"
            "Complete your assigned task thoroughly. "
            "When done, provide a clear summary of your output."
        )
        return "\n".join(parts)


@dataclass
class TeamDefinition:
    """团队定义"""

    name: str
    goal: str
    agents: list[AgentRole]
    process: TeamProcess = TeamProcess.SEQUENTIAL
    manager: AgentRole | None = None

    def validate(self) -> None:
        if not self.agents:
            raise ValueError("Team must have at least one agent")
        if self.process == TeamProcess.HIERARCHICAL and not self.manager:
            raise ValueError("Hierarchical process requires a manager agent")
        names = [a.name for a in self.agents]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate agent names in team")


class TeamExecutor:
    """团队执行器

    根据 TeamDefinition 自动构建 WorkflowGraph 并执行。
    """

    def __init__(
        self,
        team: TeamDefinition,
        checkpointer: Any | None = None,
    ) -> None:
        team.validate()
        self.team = team
        self.checkpointer = checkpointer

    def build_workflow(self) -> WorkflowGraph:
        """将 TeamDefinition 转换为 WorkflowGraph"""
        if self.team.process == TeamProcess.SEQUENTIAL:
            return self._build_sequential()
        elif self.team.process == TeamProcess.HIERARCHICAL:
            return self._build_hierarchical()
        else:
            raise ValueError(f"Unknown process: {self.team.process}")

    def _build_sequential(self) -> WorkflowGraph:
        """顺序执行：agent_1 → agent_2 → ... → END"""
        wf = WorkflowGraph(
            f"team-{self.team.name}",
            reducers={
                "messages": lambda old, new: (old or []) + (new if isinstance(new, list) else [new]),
                "agent_outputs": lambda old, new: {**(old or {}), **(new if isinstance(new, dict) else {})},
            },
        )

        for agent in self.team.agents:
            prompt_tpl = (
                f"Team goal: {self.team.goal}\n\n"
                f"Your task: {{task}}\n\n"
                "Previous agent outputs:\n{agent_outputs}"
            )
            wf.add_node(StepNode(
                name=agent.name,
                agent_type=agent.agent_type,
                system_prompt=agent.to_system_prompt(),
                tools=agent.tools,
                max_iterations=agent.max_iterations,
                output_key=agent.name,
                prompt_template=prompt_tpl,
            ))

        for i in range(len(self.team.agents) - 1):
            wf.add_edge(self.team.agents[i].name, self.team.agents[i + 1].name)

        wf.add_edge(self.team.agents[-1].name, END)
        return wf

    def _build_hierarchical(self) -> WorkflowGraph:
        """层级执行：manager 分配 → 各 agent 执行 → manager 审查"""
        assert self.team.manager is not None
        mgr = self.team.manager

        wf = WorkflowGraph(
            f"team-{self.team.name}-hierarchical",
            reducers={
                "messages": lambda old, new: (old or []) + (new if isinstance(new, list) else [new]),
                "agent_outputs": lambda old, new: {**(old or {}), **(new if isinstance(new, dict) else {})},
            },
        )

        delegate_prompt = (
            f"Team goal: {self.team.goal}\n\n"
            f"Task: {{task}}\n\n"
            f"You are the team manager. Available team members:\n"
        )
        for agent in self.team.agents:
            delegate_prompt += f"- {agent.name} ({agent.role}): {agent.goal}\n"
        delegate_prompt += (
            "\nPlan the task execution and assign work. "
            "Output a delegation plan."
        )

        wf.add_node(StepNode(
            name=f"{mgr.name}_plan",
            agent_type=mgr.agent_type,
            system_prompt=mgr.to_system_prompt(),
            tools=mgr.tools,
            max_iterations=mgr.max_iterations,
            output_key="delegation_plan",
            prompt_template=delegate_prompt,
        ))

        for agent in self.team.agents:
            exec_prompt = (
                f"Team goal: {self.team.goal}\n\n"
                f"Delegation plan: {{delegation_plan}}\n\n"
                f"Your assigned task: {{task}}"
            )
            wf.add_node(StepNode(
                name=agent.name,
                agent_type=agent.agent_type,
                system_prompt=agent.to_system_prompt(),
                tools=agent.tools,
                max_iterations=agent.max_iterations,
                output_key=agent.name,
                prompt_template=exec_prompt,
            ))

        review_prompt = (
            f"Team goal: {self.team.goal}\n\n"
            f"All agent outputs: {{agent_outputs}}\n\n"
            "Review all outputs and provide a final consolidated result."
        )
        wf.add_node(StepNode(
            name=f"{mgr.name}_review",
            agent_type=mgr.agent_type,
            system_prompt=mgr.to_system_prompt(),
            tools=["Read", "Grep"],
            max_iterations=10,
            output_key="final_review",
            prompt_template=review_prompt,
        ))

        prev = f"{mgr.name}_plan"
        for agent in self.team.agents:
            wf.add_edge(prev, agent.name)
            prev = agent.name
        wf.add_edge(prev, f"{mgr.name}_review")
        wf.add_edge(f"{mgr.name}_review", END)

        return wf

    async def run(
        self,
        task: str,
        engine_factory: Any,
        thread_id: str | None = None,
    ) -> Any:
        """执行团队任务"""
        from pyagentforge.workflow.executor import WorkflowResult  # noqa: F811

        wf = self.build_workflow()
        executor = wf.compile(checkpointer=self.checkpointer)

        initial_state: dict[str, Any] = {
            "task": task,
            "team_name": self.team.name,
            "team_goal": self.team.goal,
            "agent_outputs": {},
        }

        result = await executor.invoke(
            initial_state=initial_state,
            engine_factory=engine_factory,
            thread_id=thread_id,
        )

        logger.info(
            f"Team '{self.team.name}' completed",
            extra_data={
                "process": self.team.process.value,
                "agents": len(self.team.agents),
                "elapsed_ms": result.total_elapsed_ms,
            },
        )
        return result
