"""
单元测试 — perception.strategy
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from perception import perceive, DecisionType, PerceptionResult
from strategy import (
    AgentStrategy,
    BaseStrategy,
    MergeMode,
    MergeMode,
    RuleStrategy,
    ScriptStrategy,
    StrategyConfig,
    StrategyController,
    StrategyResult,
    StrategyType,
    build_controller_from_config,
    build_strategy,
    _parse_agent_response,
)


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------

def _rule_cfg(name: str = "rule1", priority: int = 0, rules: dict | None = None) -> StrategyConfig:
    return StrategyConfig(
        name=name,
        type=StrategyType.RULE,
        priority=priority,
        config={"rules": rules or {}},
    )


def _error_data() -> dict:
    return {"events": [{"level": "error", "message": "DB timeout"}]}


def _warn_data() -> dict:
    return {"events": [{"level": "warn", "message": "High CPU"}]}


def _none_data() -> dict:
    return {"events": [{"level": "info", "message": "normal"}]}


# ---------------------------------------------------------------------------
# RuleStrategy
# ---------------------------------------------------------------------------

class TestRuleStrategy:
    @pytest.mark.asyncio
    async def test_detects_error(self):
        s = RuleStrategy(_rule_cfg())
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.FIND_USER

    @pytest.mark.asyncio
    async def test_detects_warn(self):
        s = RuleStrategy(_rule_cfg())
        r = await s.apply(_warn_data())
        assert r.decision == DecisionType.FIND_USER

    @pytest.mark.asyncio
    async def test_none_for_info(self):
        s = RuleStrategy(_rule_cfg())
        r = await s.apply(_none_data())
        assert r.decision == DecisionType.NONE

    @pytest.mark.asyncio
    async def test_custom_rules_respected(self):
        cfg = _rule_cfg(rules={"levels": ["error"], "error_triggers": "execute"})
        s = RuleStrategy(cfg)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.EXECUTE

    @pytest.mark.asyncio
    async def test_aggregate_mode(self):
        cfg = StrategyConfig(
            name="agg",
            type=StrategyType.RULE,
            config={
                "rules": {},
                "aggregate": True,
            },
        )
        data = {"events": [
            {"level": "error", "message": "e1"},
            {"level": "error", "message": "e2"},
            {"level": "warn",  "message": "w1"},
        ]}
        s = RuleStrategy(cfg)
        r = await s.apply(data)
        assert r.decision == DecisionType.FIND_USER
        assert r.triggered_events is not None
        assert len(r.triggered_events) == 3


# ---------------------------------------------------------------------------
# ScriptStrategy
# ---------------------------------------------------------------------------

class TestScriptStrategy:
    @pytest.mark.asyncio
    async def test_callable_handler_sync(self):
        def my_handler(data, config):
            return PerceptionResult(
                decision=DecisionType.EXECUTE,
                reason="script says execute",
                data={},
            )
        cfg = StrategyConfig(name="script1", type=StrategyType.SCRIPT)
        s = ScriptStrategy(cfg, handler=my_handler)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.EXECUTE
        assert "script says execute" in r.reason

    @pytest.mark.asyncio
    async def test_callable_handler_async(self):
        async def my_handler(data, config):
            return PerceptionResult(
                decision=DecisionType.CALL_AGENT,
                reason="async script",
                data={},
            )
        cfg = StrategyConfig(name="script2", type=StrategyType.SCRIPT)
        s = ScriptStrategy(cfg, handler=my_handler)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.CALL_AGENT

    @pytest.mark.asyncio
    async def test_no_handler_returns_none(self):
        cfg = StrategyConfig(name="empty_script", type=StrategyType.SCRIPT)
        s = ScriptStrategy(cfg)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.NONE

    @pytest.mark.asyncio
    async def test_handler_exception_returns_none(self):
        def bad_handler(data, config):
            raise RuntimeError("boom")
        cfg = StrategyConfig(name="bad_script", type=StrategyType.SCRIPT)
        s = ScriptStrategy(cfg, handler=bad_handler)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.NONE
        assert "boom" in r.reason

    @pytest.mark.asyncio
    async def test_config_passed_to_handler(self):
        received = {}

        def my_handler(data, config):
            received.update(config)
            return PerceptionResult(decision=DecisionType.NONE, reason="ok", data={})

        cfg = StrategyConfig(
            name="cfg_script",
            type=StrategyType.SCRIPT,
            config={"threshold": 42},
        )
        s = ScriptStrategy(cfg, handler=my_handler)
        await s.apply(_error_data())
        assert received.get("threshold") == 42


# ---------------------------------------------------------------------------
# AgentStrategy
# ---------------------------------------------------------------------------

class TestAgentStrategy:
    @pytest.mark.asyncio
    async def test_no_engine_returns_none(self):
        cfg = StrategyConfig(name="agent1", type=StrategyType.AGENT)
        s = AgentStrategy(cfg)
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.NONE
        assert "engine not configured" in r.reason

    @pytest.mark.asyncio
    async def test_engine_run_called(self):
        class FakeEngine:
            async def run(self, prompt: str) -> str:
                return '{"decision": "execute", "reason": "agent decided execute"}'

        cfg = StrategyConfig(name="agent2", type=StrategyType.AGENT)
        s = AgentStrategy(cfg, engine=FakeEngine())
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.EXECUTE
        assert "agent decided execute" in r.reason

    @pytest.mark.asyncio
    async def test_engine_chat_fallback(self):
        class FakeEngine:
            async def chat(self, prompt: str) -> str:
                return '{"decision": "find_user", "reason": "chat response"}'

        cfg = StrategyConfig(name="agent3", type=StrategyType.AGENT)
        s = AgentStrategy(cfg, engine=FakeEngine())
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.FIND_USER

    @pytest.mark.asyncio
    async def test_engine_error_returns_none(self):
        class BrokenEngine:
            async def run(self, prompt: str) -> str:
                raise ConnectionError("LLM unreachable")

        cfg = StrategyConfig(name="agent_err", type=StrategyType.AGENT)
        s = AgentStrategy(cfg, engine=BrokenEngine())
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.NONE
        assert "LLM unreachable" in r.reason

    @pytest.mark.asyncio
    async def test_unparseable_response_falls_back_to_find_user(self):
        class FakeEngine:
            async def run(self, prompt: str) -> str:
                return "I cannot determine the action."

        cfg = StrategyConfig(name="agent_unparsed", type=StrategyType.AGENT)
        s = AgentStrategy(cfg, engine=FakeEngine())
        r = await s.apply(_error_data())
        assert r.decision == DecisionType.FIND_USER
        assert r.metadata is not None and r.metadata.get("parse_error") is True

    def test_set_engine(self):
        class Eng:
            pass
        cfg = StrategyConfig(name="agent_set", type=StrategyType.AGENT)
        s = AgentStrategy(cfg)
        assert s._engine is None
        eng = Eng()
        s.set_engine(eng)
        assert s._engine is eng


# ---------------------------------------------------------------------------
# _parse_agent_response
# ---------------------------------------------------------------------------

class TestParseAgentResponse:
    def test_valid_json_find_user(self):
        r = _parse_agent_response('{"decision": "find_user", "reason": "urgent"}')
        assert r.decision == DecisionType.FIND_USER
        assert r.reason == "urgent"

    def test_valid_json_execute(self):
        r = _parse_agent_response('{"decision": "execute", "reason": "run it"}')
        assert r.decision == DecisionType.EXECUTE

    def test_valid_json_call_agent(self):
        r = _parse_agent_response('{"decision": "call_agent", "reason": "delegate"}')
        assert r.decision == DecisionType.CALL_AGENT

    def test_valid_json_none(self):
        r = _parse_agent_response('{"decision": "none", "reason": "nothing"}')
        assert r.decision == DecisionType.NONE

    def test_json_embedded_in_text(self):
        r = _parse_agent_response('Sure! {"decision": "execute", "reason": "ok"} Done.')
        assert r.decision == DecisionType.EXECUTE

    def test_unknown_decision_defaults_to_find_user(self):
        r = _parse_agent_response('{"decision": "unknown_action", "reason": "?"}')
        assert r.decision == DecisionType.FIND_USER

    def test_no_json_returns_find_user_with_parse_error(self):
        r = _parse_agent_response("No JSON here at all.")
        assert r.decision == DecisionType.FIND_USER
        assert r.metadata is not None and r.metadata.get("parse_error") is True


# ---------------------------------------------------------------------------
# StrategyController — 并发模式
# ---------------------------------------------------------------------------

class TestStrategyControllerParallel:
    @pytest.mark.asyncio
    async def test_single_rule_strategy(self):
        ctrl = StrategyController(
            strategies=[RuleStrategy(_rule_cfg("r1", priority=1))],
        )
        merged, details = await ctrl.apply_all(_error_data())
        assert merged.decision == DecisionType.FIND_USER
        assert len(details) == 1

    @pytest.mark.asyncio
    async def test_no_enabled_strategies_returns_none(self):
        cfg = _rule_cfg("disabled")
        cfg.enabled = False
        ctrl = StrategyController(strategies=[RuleStrategy(cfg)])
        merged, details = await ctrl.apply_all(_error_data())
        assert merged.decision == DecisionType.NONE
        assert details == []

    @pytest.mark.asyncio
    async def test_all_strategies_none_returns_none(self):
        ctrl = StrategyController(
            strategies=[RuleStrategy(_rule_cfg("r1"))],
        )
        merged, details = await ctrl.apply_all(_none_data())
        assert merged.decision == DecisionType.NONE
        assert len(details) == 1

    @pytest.mark.asyncio
    async def test_two_rule_strategies_highest_priority_wins(self):
        low_cfg  = _rule_cfg("low",  priority=1, rules={"error_triggers": "execute"})
        high_cfg = _rule_cfg("high", priority=10, rules={"error_triggers": "find_user"})
        ctrl = StrategyController(
            strategies=[RuleStrategy(low_cfg), RuleStrategy(high_cfg)],
            merge_mode=MergeMode.HIGHEST_PRIORITY,
        )
        merged, details = await ctrl.apply_all(_error_data())
        assert merged.decision == DecisionType.FIND_USER
        assert "[high]" in merged.reason

    @pytest.mark.asyncio
    async def test_highest_severity_mode(self):
        def _make_script(decision: DecisionType) -> ScriptStrategy:
            def handler(data, config):
                return PerceptionResult(decision=decision, reason="test", data={})
            cfg = StrategyConfig(name=f"s_{decision.value}", type=StrategyType.SCRIPT)
            return ScriptStrategy(cfg, handler=handler)

        ctrl = StrategyController(
            strategies=[
                _make_script(DecisionType.EXECUTE),
                _make_script(DecisionType.FIND_USER),
                _make_script(DecisionType.CALL_AGENT),
            ],
            merge_mode=MergeMode.HIGHEST_SEVERITY,
        )
        merged, _ = await ctrl.apply_all(_error_data())
        # FIND_USER has weight 3 (highest)
        assert merged.decision == DecisionType.FIND_USER

    @pytest.mark.asyncio
    async def test_all_mode_aggregates_events(self):
        def _make_rule(name, rules):
            cfg = StrategyConfig(
                name=name,
                type=StrategyType.RULE,
                config={"rules": rules, "aggregate": True},
            )
            return RuleStrategy(cfg)

        data = {"events": [
            {"level": "error", "message": "e1"},
            {"level": "warn",  "message": "w1"},
        ]}
        ctrl = StrategyController(
            strategies=[
                _make_rule("r1", {"levels": ["error"]}),
                _make_rule("r2", {"levels": ["warn"]}),
            ],
            merge_mode=MergeMode.ALL,
        )
        merged, details = await ctrl.apply_all(data)
        assert merged.decision != DecisionType.NONE
        assert merged.triggered_events is not None
        assert len(merged.triggered_events) == 2  # 1 from r1 + 1 from r2

    @pytest.mark.asyncio
    async def test_strategy_exception_does_not_crash_controller(self):
        class BrokenStrategy(BaseStrategy):
            async def apply(self, data):
                raise RuntimeError("I am broken")

        broken_cfg = StrategyConfig(name="broken", type=StrategyType.RULE)
        ctrl = StrategyController(
            strategies=[
                BrokenStrategy(broken_cfg),
                RuleStrategy(_rule_cfg("ok", priority=1)),
            ],
        )
        merged, details = await ctrl.apply_all(_error_data())
        assert merged.decision == DecisionType.FIND_USER
        broken_sr = next(sr for sr in details if sr.strategy_name == "broken")
        assert broken_sr.error is not None

    @pytest.mark.asyncio
    async def test_add_strategy_at_runtime(self):
        ctrl = StrategyController()
        assert len(ctrl.strategies) == 0
        ctrl.add_strategy(RuleStrategy(_rule_cfg("r1")))
        assert len(ctrl.strategies) == 1
        merged, _ = await ctrl.apply_all(_error_data())
        assert merged.decision == DecisionType.FIND_USER


# ---------------------------------------------------------------------------
# StrategyController — 顺序模式（parallel=False）
# ---------------------------------------------------------------------------

class TestStrategyControllerSequential:
    @pytest.mark.asyncio
    async def test_stops_at_first_triggered_in_highest_priority_mode(self):
        calls: list[str] = []

        def make_script(name: str, decision: DecisionType) -> ScriptStrategy:
            def handler(data, config):
                calls.append(name)
                return PerceptionResult(decision=decision, reason=name, data={})
            cfg = StrategyConfig(name=name, type=StrategyType.SCRIPT, priority=0)
            return ScriptStrategy(cfg, handler=handler)

        ctrl = StrategyController(
            strategies=[
                make_script("first", DecisionType.FIND_USER),
                make_script("second", DecisionType.EXECUTE),
            ],
            merge_mode=MergeMode.HIGHEST_PRIORITY,
            parallel=False,
        )
        merged, details = await ctrl.apply_all(_error_data())
        assert "first" in calls
        assert "second" not in calls
        assert "[first]" in merged.reason

    @pytest.mark.asyncio
    async def test_continues_if_first_is_none(self):
        calls: list[str] = []

        def make_script(name: str, decision: DecisionType) -> ScriptStrategy:
            def handler(data, config):
                calls.append(name)
                return PerceptionResult(decision=decision, reason=name, data={})
            cfg = StrategyConfig(name=name, type=StrategyType.SCRIPT, priority=0)
            return ScriptStrategy(cfg, handler=handler)

        ctrl = StrategyController(
            strategies=[
                make_script("none_first", DecisionType.NONE),
                make_script("triggered_second", DecisionType.FIND_USER),
            ],
            merge_mode=MergeMode.HIGHEST_PRIORITY,
            parallel=False,
        )
        merged, _ = await ctrl.apply_all(_error_data())
        assert "none_first" in calls
        assert "triggered_second" in calls
        assert merged.decision == DecisionType.FIND_USER


# ---------------------------------------------------------------------------
# build_controller_from_config
# ---------------------------------------------------------------------------

class TestBuildControllerFromConfig:
    @pytest.mark.asyncio
    async def test_rule_type(self):
        ctrl = build_controller_from_config(
            [{"name": "r1", "type": "rule", "rules": {}}],
        )
        assert len(ctrl.strategies) == 1
        assert isinstance(ctrl.strategies[0], RuleStrategy)

    @pytest.mark.asyncio
    async def test_script_type_with_handler(self):
        def my_handler(data, config):
            return PerceptionResult(decision=DecisionType.EXECUTE, reason="ok", data={})

        ctrl = build_controller_from_config(
            [{"name": "s1", "type": "script"}],
            handlers={"s1": my_handler},
        )
        assert isinstance(ctrl.strategies[0], ScriptStrategy)
        r = await ctrl.strategies[0].apply(_error_data())
        assert r.decision == DecisionType.EXECUTE

    @pytest.mark.asyncio
    async def test_agent_type_receives_engine(self):
        class FakeEngine:
            async def run(self, p):
                return '{"decision": "call_agent", "reason": "delegate"}'

        ctrl = build_controller_from_config(
            [{"name": "a1", "type": "agent"}],
            engine=FakeEngine(),
        )
        assert isinstance(ctrl.strategies[0], AgentStrategy)
        r = await ctrl.strategies[0].apply(_error_data())
        assert r.decision == DecisionType.CALL_AGENT

    def test_disabled_strategy_excluded_from_execution(self):
        ctrl = build_controller_from_config(
            [{"name": "disabled", "type": "rule", "enabled": False}],
        )
        assert ctrl.strategies[0].config.enabled is False

    def test_merge_mode_all(self):
        ctrl = build_controller_from_config([], merge_mode="all")
        assert ctrl._merge_mode == MergeMode.ALL

    def test_merge_mode_highest_severity(self):
        ctrl = build_controller_from_config([], merge_mode="highest_severity")
        assert ctrl._merge_mode == MergeMode.HIGHEST_SEVERITY

    def test_unknown_merge_mode_defaults_to_highest_priority(self):
        ctrl = build_controller_from_config([], merge_mode="garbage")
        assert ctrl._merge_mode == MergeMode.HIGHEST_PRIORITY

    def test_priority_preserved(self):
        ctrl = build_controller_from_config(
            [{"name": "r1", "type": "rule", "priority": 99}],
        )
        assert ctrl.strategies[0].config.priority == 99

    def test_multiple_strategies(self):
        ctrl = build_controller_from_config(
            [
                {"name": "r1", "type": "rule"},
                {"name": "r2", "type": "rule"},
                {"name": "s1", "type": "script"},
            ]
        )
        assert len(ctrl.strategies) == 3


# ---------------------------------------------------------------------------
# build_strategy 工厂函数
# ---------------------------------------------------------------------------

class TestBuildStrategy:
    def test_builds_rule(self):
        cfg = _rule_cfg()
        s = build_strategy(cfg)
        assert isinstance(s, RuleStrategy)

    def test_builds_script(self):
        cfg = StrategyConfig(name="s", type=StrategyType.SCRIPT)
        s = build_strategy(cfg)
        assert isinstance(s, ScriptStrategy)

    def test_builds_agent(self):
        cfg = StrategyConfig(name="a", type=StrategyType.AGENT)
        s = build_strategy(cfg)
        assert isinstance(s, AgentStrategy)

    def test_unknown_type_raises(self):
        cfg = StrategyConfig(name="x", type="unknown")  # type: ignore[arg-type]
        with pytest.raises((ValueError, Exception)):
            build_strategy(cfg)
