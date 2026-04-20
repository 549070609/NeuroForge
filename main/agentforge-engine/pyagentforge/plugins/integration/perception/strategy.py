"""
感知策略控制器

支持同时应用多种感知策略（规则 / Agent / 脚本），并将各策略结果按指定合并模式汇总输出。

策略类型：
  - rule   : 封装现有 perceive()，零侵入原逻辑
  - script : 调用 Python callable 或外部脚本文件
  - agent  : 委托 AI AgentEngine 对数据进行感知分析

合并模式：
  - highest_priority : 取 priority 最高且已触发的策略结果（默认）
  - highest_severity : 取 decision 权重最高的结果
  - all              : 聚合全部触发策略的事件与决策
"""

import asyncio
import importlib.util
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .perception import DecisionType, PerceptionResult, perceive


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------


class StrategyType(str, Enum):
    RULE   = "rule"    # 规则策略
    AGENT  = "agent"   # Agent 策略
    SCRIPT = "script"  # 脚本策略


class MergeMode(str, Enum):
    HIGHEST_PRIORITY = "highest_priority"  # priority 最高且触发的策略获胜
    HIGHEST_SEVERITY = "highest_severity"  # decision 权重最高的结果获胜
    ALL              = "all"               # 聚合全部触发策略


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class StrategyConfig:
    """感知策略配置"""

    name:     str
    type:     StrategyType
    enabled:  bool            = True
    priority: int             = 0       # 越大越优先（HIGHEST_PRIORITY 模式生效）
    config:   dict[str, Any]  = field(default_factory=dict)


@dataclass
class StrategyResult:
    """单条策略的执行结果"""

    strategy_name: str
    strategy_type: StrategyType
    result:        PerceptionResult
    error:         str | None = None


# ---------------------------------------------------------------------------
# 策略基类
# ---------------------------------------------------------------------------


class BaseStrategy(ABC):
    """感知策略抽象基类"""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @abstractmethod
    async def apply(self, data: dict | list) -> PerceptionResult:
        """执行感知，返回决策结果"""


# ---------------------------------------------------------------------------
# 规则策略
# ---------------------------------------------------------------------------


class RuleStrategy(BaseStrategy):
    """规则策略：封装现有 perceive() 函数，完全向后兼容"""

    async def apply(self, data: dict | list) -> PerceptionResult:
        rules     = self.config.config.get("rules", {})
        aggregate = bool(self.config.config.get("aggregate", False))
        return perceive(data, rules, aggregate=aggregate)


# ---------------------------------------------------------------------------
# 脚本策略
# ---------------------------------------------------------------------------


class ScriptStrategy(BaseStrategy):
    """
    脚本策略：调用 Python callable 或加载外部脚本文件。

    handler 签名（同步或异步）：
        def apply(data: dict | list, config: dict) -> PerceptionResult
        async def apply(data: dict | list, config: dict) -> PerceptionResult

    外部脚本须在模块级导出名为 ``apply`` 或 ``perceive`` 的函数。
    """

    def __init__(
        self,
        config:  StrategyConfig,
        handler: Callable | None = None,
    ) -> None:
        super().__init__(config)
        self._handler = handler

    async def apply(self, data: dict | list) -> PerceptionResult:
        handler = self._handler or self._load_from_path()
        if handler is None:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason="ScriptStrategy: no handler configured",
                data={},
            )
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(data, self.config.config)
            return handler(data, self.config.config)
        except Exception as exc:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason=f"ScriptStrategy error: {exc}",
                data={"error": str(exc)},
            )

    def _load_from_path(self) -> Callable | None:
        """从 config['script_path'] 动态加载模块并提取入口函数"""
        script_path = self.config.config.get("script_path")
        if not script_path:
            return None
        spec = importlib.util.spec_from_file_location("_perception_script", script_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return getattr(mod, "apply", None) or getattr(mod, "perceive", None)


# ---------------------------------------------------------------------------
# Agent 策略
# ---------------------------------------------------------------------------

_AGENT_DEFAULT_PROMPT = (
    "You are a log analysis agent. Analyze the following log data and decide what action to take.\n"
    "Log data:\n{data}\n\n"
    "Reply ONLY with a JSON object:\n"
    '{{"decision": "<find_user|execute|call_agent|none>", "reason": "<brief reason>"}}'
)


class AgentStrategy(BaseStrategy):
    """
    Agent 策略：委托 AI AgentEngine 对数据进行感知分析。

    engine 需支持异步调用接口之一：
        await engine.run(prompt)
        await engine.chat(prompt)
        await engine.arun(prompt)
    """

    def __init__(self, config: StrategyConfig, engine: Any = None) -> None:
        super().__init__(config)
        self._engine = engine

    def set_engine(self, engine: Any) -> None:
        """注入引擎（由插件在 on_engine_start 时调用）"""
        self._engine = engine

    async def apply(self, data: dict | list) -> PerceptionResult:
        if self._engine is None:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason="AgentStrategy: engine not configured",
                data={},
            )
        cfg             = self.config.config
        prompt_template = cfg.get("prompt", _AGENT_DEFAULT_PROMPT)
        data_str        = json.dumps(data, ensure_ascii=False, indent=2)
        prompt          = prompt_template.format(data=data_str)
        try:
            call = (
                getattr(self._engine, "run",   None)
                or getattr(self._engine, "chat", None)
                or getattr(self._engine, "arun", None)
            )
            if call is None:
                raise AttributeError("Engine has no run/chat/arun method")
            response = await call(prompt)
            return _parse_agent_response(str(response))
        except Exception as exc:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason=f"AgentStrategy error: {exc}",
                data={"error": str(exc)},
            )


def _parse_agent_response(response: str) -> PerceptionResult:
    """将 Agent 的文本响应解析为 PerceptionResult"""
    _decision_map: dict[str, DecisionType] = {
        "find_user":  DecisionType.FIND_USER,
        "execute":    DecisionType.EXECUTE,
        "call_agent": DecisionType.CALL_AGENT,
        "none":       DecisionType.NONE,
    }
    try:
        start = response.find("{")
        end   = response.rfind("}") + 1
        if start != -1 and end > start:
            obj      = json.loads(response[start:end])
            raw_dec  = str(obj.get("decision", "none")).lower()
            reason   = str(obj.get("reason", "Agent decision"))
            decision = _decision_map.get(raw_dec, DecisionType.FIND_USER)
            return PerceptionResult(
                decision=decision,
                reason=reason,
                data={"agent_raw": response},
                metadata={"strategy_type": "agent"},
            )
    except Exception:
        pass
    return PerceptionResult(
        decision=DecisionType.FIND_USER,
        reason=f"Agent response (unparsed): {response[:200]}",
        data={"agent_raw": response},
        metadata={"strategy_type": "agent", "parse_error": True},
    )


# ---------------------------------------------------------------------------
# 策略控制器
# ---------------------------------------------------------------------------

_DECISION_WEIGHT: dict[DecisionType, int] = {
    DecisionType.FIND_USER:  3,
    DecisionType.CALL_AGENT: 2,
    DecisionType.EXECUTE:    1,
    DecisionType.NONE:       0,
}


class StrategyController:
    """
    感知策略控制器：协调多个感知策略并合并结果。

    Args:
        strategies : 策略列表（按注册顺序）
        merge_mode : 结果合并模式，默认 HIGHEST_PRIORITY
        parallel   : True=并发执行（asyncio.gather），False=顺序执行
    """

    def __init__(
        self,
        strategies: list[BaseStrategy] | None = None,
        merge_mode: MergeMode = MergeMode.HIGHEST_PRIORITY,
        parallel:   bool      = True,
    ) -> None:
        self._strategies: list[BaseStrategy] = strategies or []
        self._merge_mode  = merge_mode
        self._parallel    = parallel

    # ---- 公开接口 ----

    @property
    def strategies(self) -> list[BaseStrategy]:
        return list(self._strategies)

    def add_strategy(self, strategy: BaseStrategy) -> None:
        self._strategies.append(strategy)

    async def apply_all(
        self,
        data: dict | list,
    ) -> tuple[PerceptionResult, list[StrategyResult]]:
        """
        应用所有启用的策略，返回合并结果和各策略详情。

        Returns:
            (merged_result, strategy_results)
              merged_result    — 根据 merge_mode 合并后的最终决策
              strategy_results — 每个策略的原始结果（含错误信息）
        """
        enabled = [s for s in self._strategies if s.config.enabled]
        if not enabled:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason="StrategyController: no enabled strategies",
                data={},
            ), []

        if self._parallel:
            results = await self._run_parallel(enabled, data)
        else:
            results = await self._run_sequential(enabled, data)

        merged = self._merge(results)
        return merged, results

    # ---- 内部执行 ----

    @staticmethod
    async def _run_parallel(
        strategies: list[BaseStrategy],
        data: dict | list,
    ) -> list[StrategyResult]:
        async def _one(s: BaseStrategy) -> StrategyResult:
            try:
                return StrategyResult(
                    strategy_name=s.config.name,
                    strategy_type=s.config.type,
                    result=await s.apply(data),
                )
            except Exception as exc:
                return StrategyResult(
                    strategy_name=s.config.name,
                    strategy_type=s.config.type,
                    result=PerceptionResult(
                        decision=DecisionType.NONE,
                        reason=f"Strategy '{s.config.name}' raised: {exc}",
                        data={"error": str(exc)},
                    ),
                    error=str(exc),
                )

        return list(await asyncio.gather(*[_one(s) for s in strategies]))

    async def _run_sequential(
        self,
        strategies: list[BaseStrategy],
        data: dict | list,
    ) -> list[StrategyResult]:
        results: list[StrategyResult] = []
        for s in strategies:
            try:
                r = StrategyResult(
                    strategy_name=s.config.name,
                    strategy_type=s.config.type,
                    result=await s.apply(data),
                )
            except Exception as exc:
                r = StrategyResult(
                    strategy_name=s.config.name,
                    strategy_type=s.config.type,
                    result=PerceptionResult(
                        decision=DecisionType.NONE,
                        reason=f"Strategy '{s.config.name}' raised: {exc}",
                        data={"error": str(exc)},
                    ),
                    error=str(exc),
                )
            results.append(r)
            # 顺序 + HIGHEST_PRIORITY 模式：首次触发即停
            if (
                self._merge_mode == MergeMode.HIGHEST_PRIORITY
                and r.result.decision != DecisionType.NONE
            ):
                break
        return results

    # ---- 结果合并 ----

    def _merge(self, results: list[StrategyResult]) -> PerceptionResult:
        triggered = [r for r in results if r.result.decision != DecisionType.NONE]
        if not triggered:
            return PerceptionResult(
                decision=DecisionType.NONE,
                reason="No strategies triggered an action",
                data={"strategy_count": len(results)},
                metadata={"strategies": [r.strategy_name for r in results]},
            )

        if self._merge_mode == MergeMode.HIGHEST_PRIORITY:
            priority_map = {s.config.name: s.config.priority for s in self._strategies}
            winner = max(triggered, key=lambda r: priority_map.get(r.strategy_name, 0))
            return _wrap_winner(winner, triggered)

        if self._merge_mode == MergeMode.HIGHEST_SEVERITY:
            winner = max(triggered, key=lambda r: _DECISION_WEIGHT.get(r.result.decision, 0))
            return _wrap_winner(winner, triggered)

        # MergeMode.ALL
        return _merge_all(triggered, results)


# ---------------------------------------------------------------------------
# 辅助：合并逻辑
# ---------------------------------------------------------------------------


def _wrap_winner(
    winner:    StrategyResult,
    triggered: list[StrategyResult],
) -> PerceptionResult:
    r    = winner.result
    meta = dict(r.metadata or {})
    meta.update(
        {
            "strategy":         winner.strategy_name,
            "strategy_type":    winner.strategy_type.value,
            "triggered_by":     [t.strategy_name for t in triggered],
            "total_triggered":  len(triggered),
        }
    )
    return PerceptionResult(
        decision=r.decision,
        reason=f"[{winner.strategy_name}] {r.reason}",
        data=r.data,
        metadata=meta,
        triggered_events=r.triggered_events,
    )


def _merge_all(
    triggered:   list[StrategyResult],
    all_results: list[StrategyResult],
) -> PerceptionResult:
    best       = max(triggered, key=lambda r: _DECISION_WEIGHT.get(r.result.decision, 0))
    all_events = [evt for r in triggered for evt in (r.result.triggered_events or [])]
    return PerceptionResult(
        decision=best.result.decision,
        reason=(
            f"Combined {len(triggered)} strategy result(s): "
            + "; ".join(f"[{r.strategy_name}] {r.result.reason[:60]}" for r in triggered)
        ),
        data={
            "triggered_strategies": [r.strategy_name for r in triggered],
            "total_strategies":     len(all_results),
            "total_events":         len(all_events),
        },
        metadata={
            "merge_mode": "all",
            "strategies": [r.strategy_name for r in all_results],
        },
        triggered_events=all_events or None,
    )


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def build_strategy(
    config:  StrategyConfig,
    handler: Callable | None = None,
    engine:  Any             = None,
) -> BaseStrategy:
    """根据配置创建对应类型的策略实例"""
    if config.type == StrategyType.RULE:
        return RuleStrategy(config)
    if config.type == StrategyType.SCRIPT:
        return ScriptStrategy(config, handler=handler)
    if config.type == StrategyType.AGENT:
        return AgentStrategy(config, engine=engine)
    raise ValueError(f"Unknown strategy type: {config.type}")


def build_controller_from_config(
    strategies_cfg: list[dict[str, Any]],
    merge_mode:     str                       = "highest_priority",
    parallel:       bool                      = True,
    handlers:       dict[str, Callable] | None = None,
    engine:         Any                       = None,
) -> StrategyController:
    """
    从配置字典列表构建 StrategyController。

    Args:
        strategies_cfg : 策略配置列表，每项为 dict（见下方示例）
        merge_mode     : 合并模式字符串（highest_priority / highest_severity / all）
        parallel       : 是否并发执行各策略
        handlers       : {策略名: callable}，供 script 策略使用
        engine         : AgentEngine 实例，供 agent 策略使用

    配置示例::

        strategies_cfg = [
            {
                "name": "error_watcher",
                "type": "rule",
                "priority": 10,
                "rules": {"levels": ["error", "warn"], "error_triggers": "find_user"},
            },
            {
                "name": "security_check",
                "type": "script",
                "priority": 5,
                "script_path": "./scripts/security_check.py",
            },
            {
                "name": "ai_analyzer",
                "type": "agent",
                "enabled": False,
                "priority": 1,
                "prompt": "Analyze logs: {data}",
            },
        ]
    """
    _mode_map: dict[str, MergeMode] = {
        "highest_priority": MergeMode.HIGHEST_PRIORITY,
        "highest_severity": MergeMode.HIGHEST_SEVERITY,
        "all":              MergeMode.ALL,
    }
    mode = _mode_map.get(merge_mode, MergeMode.HIGHEST_PRIORITY)

    built: list[BaseStrategy] = []
    for raw in strategies_cfg:
        cfg = StrategyConfig(
            name     = raw.get("name", "unnamed"),
            type     = StrategyType(raw.get("type", "rule")),
            enabled  = bool(raw.get("enabled", True)),
            priority = int(raw.get("priority", 0)),
            config   = {k: v for k, v in raw.items()
                        if k not in ("name", "type", "enabled", "priority")},
        )
        handler  = (handlers or {}).get(cfg.name)
        strategy = build_strategy(cfg, handler=handler, engine=engine)
        built.append(strategy)

    return StrategyController(strategies=built, merge_mode=mode, parallel=parallel)
