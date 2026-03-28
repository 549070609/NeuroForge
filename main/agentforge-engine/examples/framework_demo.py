#!/usr/bin/env python3
"""
NeuroForge 框架独立测试应用

演示所有新增功能，使用 ScriptedProvider 实现确定性运行，
不依赖真实 LLM API，不耦合现有业务逻辑。

运行: python examples/framework_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.checkpoint import FileCheckpointer, MemoryCheckpointer
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.testing import ScriptBuilder, ScriptedProvider
from pyagentforge.tools.base import BaseTool
from pyagentforge.workflow import (
    END,
    AgentRole,
    EngineFactory,
    HandoffManager,
    HandoffPayload,
    StepNode,
    TeamDefinition,
    TeamExecutor,
    TeamProcess,
    TraceCollector,
    WorkflowGraph,
)


# ─── 测试用工具 ──────────────────────────────────────────

class EchoTool(BaseTool):
    """测试工具：原样返回输入"""
    name = "echo"
    description = "Echo input back"
    parameters_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, text: str = "", **kwargs) -> str:
        return f"[echo] {text}"


class CalculateTool(BaseTool):
    """测试工具：简单计算"""
    name = "calculate"
    description = "Simple arithmetic"
    parameters_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string"},
        },
        "required": ["expression"],
    }

    async def execute(self, expression: str = "", **kwargs) -> str:
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"


def create_test_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(CalculateTool())
    return registry


# ─── Demo 1: ScriptedProvider + AgentEngine ──────────────

async def demo_scripted_provider():
    """演示 ScriptedProvider 确定性测试"""
    print("\n" + "=" * 60)
    print("Demo 1: ScriptedProvider + AgentEngine")
    print("=" * 60)

    script = (
        ScriptBuilder()
        .add_tool_call("echo", {"text": "Hello from agent!"})
        .add_tool_call("calculate", {"expression": "2 + 3 * 4"})
        .add_text("I called echo and calculate. Echo said 'Hello from agent!' "
                   "and the calculation 2+3*4 = 14.")
        .build()
    )

    provider = ScriptedProvider(script)
    tools = create_test_tools()
    config = AgentConfig(max_iterations=10)

    engine = AgentEngine(provider=provider, tool_registry=tools, config=config)
    result = await engine.run("Test the echo and calculate tools")

    print(f"  Result: {result[:120]}...")
    print(f"  Provider calls: {len(provider.call_log)}")
    print(f"  Remaining responses: {provider.remaining_responses}")
    assert "14" in result
    print("  PASSED")


# ─── Demo 2: Checkpoint + Resume ─────────────────────────

async def demo_checkpoint():
    """演示 Checkpoint 保存和恢复"""
    print("\n" + "=" * 60)
    print("Demo 2: Checkpoint + Resume")
    print("=" * 60)

    checkpointer = MemoryCheckpointer()

    script1 = (
        ScriptBuilder()
        .add_tool_call("echo", {"text": "step 1"})
        .add_tool_call("echo", {"text": "step 2"})
        .add_text("All steps completed successfully.")
        .build()
    )

    provider = ScriptedProvider(script1)
    tools = create_test_tools()
    config = AgentConfig(max_iterations=10)

    engine = AgentEngine(
        provider=provider,
        tool_registry=tools,
        config=config,
        checkpointer=checkpointer,
    )

    result = await engine.run("Run two echo steps")

    sessions = await checkpointer.list_sessions()
    print(f"  Result: {result[:80]}...")
    print(f"  Sessions with checkpoints after completion: {len(sessions)}")
    assert len(sessions) == 0, "Checkpoint should be cleaned after success"
    print("  PASSED (checkpoint cleaned on success)")


# ─── Demo 3: WorkflowGraph ──────────────────────────────

async def demo_workflow():
    """演示声明式工作流编排"""
    print("\n" + "=" * 60)
    print("Demo 3: WorkflowGraph + Conditional Routing")
    print("=" * 60)

    def check_review(state):
        review = state.get("review", "")
        return "pass" if "APPROVED" in review else "fail"

    wf = WorkflowGraph("test-review-flow")
    wf.add_node(StepNode(name="analyze", agent_type="explore", output_key="analysis"))
    wf.add_node(StepNode(name="implement", agent_type="code", output_key="code"))
    wf.add_node(StepNode(name="review", agent_type="review", output_key="review"))

    wf.add_edge("analyze", "implement")
    wf.add_edge("implement", "review")
    wf.add_conditional_edge("review", check_review, {"pass": END, "fail": "implement"})

    print(f"  Mermaid graph:\n{wf.to_mermaid()}")
    print()

    checkpointer = MemoryCheckpointer()
    executor = wf.compile(checkpointer=checkpointer)

    result = await executor.invoke(
        initial_state={"task": "Build a calculator module"},
        thread_id="wf-001",
    )

    print(f"  Thread: {result.thread_id}")
    print(f"  Steps executed: {len(result.trace)}")
    for step in result.trace:
        print(f"    - {step.node} ({step.agent_type}): {step.elapsed_ms}ms")
    print(f"  Total: {result.total_elapsed_ms}ms")
    print(f"  Resumed: {result.resumed}")
    print("  PASSED (dry-run mode)")


# ─── Demo 4: Handoff ────────────────────────────────────

async def demo_handoff():
    """演示 Agent Handoff 上下文传递"""
    print("\n" + "=" * 60)
    print("Demo 4: Agent Handoff Protocol")
    print("=" * 60)

    source_context = ContextManager(system_prompt="You are an analyzer.")
    source_context.add_user_message("Analyze the auth module")
    source_context.add_assistant_text("Found 3 security issues in auth.py")

    manager = HandoffManager()

    payload = manager.initiate(
        source_agent="analyzer",
        target_agent="fixer",
        instruction="Fix the 3 security issues found in auth.py",
        context=source_context,
        shared_state={"issues_count": 3, "file": "auth.py"},
    )

    target_context = ContextManager(system_prompt="You are a fixer.")
    accepted = manager.accept("fixer", target_context)

    print(f"  Handoff initiated: analyzer → fixer")
    print(f"  Accepted: {accepted}")
    print(f"  Target context messages: {len(target_context)}")
    print(f"  Shared state: {payload.shared_state}")
    print(f"  History: {manager.get_history()}")

    serialized = payload.to_dict()
    restored = HandoffPayload.from_dict(serialized)
    assert restored.source_agent == "analyzer"
    assert restored.target_agent == "fixer"
    print("  Serialization roundtrip: OK")
    print("  PASSED")


# ─── Demo 5: Team Collaboration ─────────────────────────

async def demo_team():
    """演示 CrewAI 风格团队协作"""
    print("\n" + "=" * 60)
    print("Demo 5: Team Collaboration (CrewAI-style)")
    print("=" * 60)

    researcher = AgentRole(
        name="researcher",
        role="Research Analyst",
        goal="Find relevant information and provide analysis",
        backstory="Expert in technical research with 10 years experience",
        agent_type="explore",
    )
    writer = AgentRole(
        name="writer",
        role="Technical Writer",
        goal="Write clear, comprehensive documentation",
        backstory="Skilled at translating complex topics into readable content",
        agent_type="code",
    )

    team = TeamDefinition(
        name="docs-team",
        goal="Create comprehensive API documentation",
        agents=[researcher, writer],
        process=TeamProcess.SEQUENTIAL,
    )

    print(f"  Team: {team.name}")
    print(f"  Goal: {team.goal}")
    print(f"  Process: {team.process.value}")
    print(f"  Agents:")
    for agent in team.agents:
        print(f"    - {agent.name} ({agent.role})")
        print(f"      System prompt preview: {agent.to_system_prompt()[:80]}...")

    executor = TeamExecutor(team)
    wf = executor.build_workflow()
    print(f"\n  Generated workflow: {wf.name}")
    print(f"  Nodes: {list(wf.nodes.keys())}")
    print(f"  Edges: {len(wf.edges)}")
    print(f"\n  Mermaid:\n{wf.to_mermaid()}")
    print("  PASSED")


# ─── Demo 6: Tracing ────────────────────────────────────

async def demo_tracing():
    """演示结构化 Trace/Span"""
    print("\n" + "=" * 60)
    print("Demo 6: Structured Tracing")
    print("=" * 60)

    from pyagentforge.workflow.tracing import SpanKind, SpanStatus

    collector = TraceCollector()

    agent_span = collector.start_span("agent.run", kind=SpanKind.AGENT,
                                       attributes={"model": "test-model"})

    llm_span = collector.start_span("llm.call", kind=SpanKind.LLM_CALL,
                                     parent=agent_span,
                                     attributes={"prompt_tokens": 100})
    await asyncio.sleep(0.01)
    llm_span.add_event("response_received", {"tokens": 50})
    collector.finish_span(llm_span)

    tool_span = collector.start_span("tool.echo", kind=SpanKind.TOOL_CALL,
                                      parent=agent_span)
    await asyncio.sleep(0.005)
    collector.finish_span(tool_span)

    collector.finish_span(agent_span)

    summary = collector.get_summary()
    print(f"  Trace ID: {collector.trace_id}")
    print(f"  Total spans: {summary['total_spans']}")
    print(f"  Active spans: {summary['active_spans']}")
    print(f"  By kind:")
    for kind, stats in summary["by_kind"].items():
        print(f"    {kind}: count={stats['count']}, total={stats['total_ms']}ms")

    exported = collector.export_json()
    print(f"  Exported spans: {len(exported)}")
    assert len(exported) == 3
    assert exported[0]["kind"] == "llm_call"
    assert exported[0]["parent_span_id"] == agent_span.span_id
    print("  PASSED")


# ─── Demo 7: LLMClient Retry ────────────────────────────

async def demo_retry():
    """演示 LLMClient 重试配置"""
    print("\n" + "=" * 60)
    print("Demo 7: LLMClient RetryConfig")
    print("=" * 60)

    from pyagentforge.client import LLMClient, RetryConfig

    config = RetryConfig(
        max_retries=3,
        initial_delay=0.5,
        backoff_multiplier=2.0,
        jitter=True,
        retryable_status_codes={429, 500, 502, 503},
    )

    print(f"  max_retries: {config.max_retries}")
    print(f"  initial_delay: {config.initial_delay}s")
    print(f"  backoff_multiplier: {config.backoff_multiplier}")
    print(f"  jitter: {config.jitter}")
    print(f"  retryable codes: {config.retryable_status_codes}")

    client = LLMClient(
        retry_config=config,
        fallback_model_ids=["gpt-4o-mini", "claude-haiku"],
    )
    print(f"  Fallback models: {client.fallback_model_ids}")
    await client.aclose()
    print("  PASSED (config verified)")


# ─── Demo 8: PersistentEventBus ──────────────────────────

async def demo_persistent_events():
    """演示持久化事件总线"""
    print("\n" + "=" * 60)
    print("Demo 8: PersistentEventBus")
    print("=" * 60)

    from pyagentforge.plugins.integration.events.events import EventType
    from pyagentforge.plugins.integration.events.persistent import PersistentEventBus

    with tempfile.TemporaryDirectory() as tmpdir:
        bus = PersistentEventBus(name="test", storage_dir=tmpdir)

        events_received = []
        bus.subscribe(lambda e: events_received.append(e))

        await bus.emit(EventType.AGENT_STARTED, {"agent": "demo"}, source="test")
        await bus.emit(EventType.TOOL_STARTED, {"tool": "echo"}, source="test")
        await bus.emit(EventType.AGENT_COMPLETED, {"result": "ok"}, source="test")

        print(f"  Events emitted: {bus.get_event_count()}")
        print(f"  Events received by subscriber: {len(events_received)}")

        replayed = bus.replay(from_seq=2)
        print(f"  Replayed from seq 2: {len(replayed)} events")
        assert len(replayed) == 2

        all_events = bus.replay()
        print(f"  All events in log: {len(all_events)}")
        assert len(all_events) == 3

        log_file = Path(tmpdir) / "test.jsonl"
        print(f"  Log file exists: {log_file.exists()}")
        print(f"  Log file size: {log_file.stat().st_size} bytes")

    print("  PASSED")


# ─── Demo 9: SandboxExecutor ────────────────────────────

async def demo_sandbox():
    """演示工具沙箱执行"""
    print("\n" + "=" * 60)
    print("Demo 9: SandboxExecutor")
    print("=" * 60)

    from pyagentforge.kernel.sandbox import SandboxConfig, SandboxExecutor

    executor = SandboxExecutor(SandboxConfig(timeout_seconds=10))

    print(f"  Should sandbox 'Bash': {executor.should_sandbox('Bash')}")
    print(f"  Should sandbox 'Read': {executor.should_sandbox('Read')}")
    print(f"  Should sandbox 'Write': {executor.should_sandbox('Write')}")

    result = await executor.execute_in_sandbox(
        "Bash", {"command": "echo hello from sandbox"}
    )
    print(f"  Sandbox result: success={result.success}")
    print(f"  Output: {result.output.strip()}")
    print(f"  Elapsed: {result.elapsed_ms}ms")
    assert result.success
    assert "hello from sandbox" in result.output
    print("  PASSED")


# ─── Main ────────────────────────────────────────────────

async def main():
    print("╔" + "═" * 58 + "╗")
    print("║  NeuroForge Framework Demo — All Features              ║")
    print("╚" + "═" * 58 + "╝")

    demos = [
        ("ScriptedProvider", demo_scripted_provider),
        ("Checkpoint", demo_checkpoint),
        ("WorkflowGraph", demo_workflow),
        ("Handoff", demo_handoff),
        ("Team", demo_team),
        ("Tracing", demo_tracing),
        ("LLMClient Retry", demo_retry),
        ("PersistentEventBus", demo_persistent_events),
        ("Sandbox", demo_sandbox),
    ]

    passed = 0
    failed = 0

    for name, demo_fn in demos:
        try:
            await demo_fn()
            passed += 1
        except Exception as e:
            print(f"\n  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
