"""
主动感知器插件

基于 ATON/TOON 日志的主动感知与决策
"""

import hashlib
import importlib.util
import sys
import time
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import List

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


# ---------------------------------------------------------------------------
# 告警去重器
# ---------------------------------------------------------------------------

@dataclass
class _AlertRecord:
    """单条告警指纹的冷却记录"""
    first_seen: float = dataclass_field(default_factory=time.time)
    last_seen:  float = dataclass_field(default_factory=time.time)
    count:      int   = 1


class AlertDeduplicator:
    """
    基于事件指纹的告警去重器（内存缓存，进程级生命周期）。

    去重逻辑：
      - 首次出现  → 放行，记录 first_seen
      - 冷却期内  → 抑制（suppressed），更新 last_seen 与 count
      - 冷却期过后 → 重置并放行（持续故障仍能被捕获）

    Args:
        cooldown_seconds: 冷却窗口时长（秒），默认 300
        max_cache_size:   指纹缓存上限，超出时 LRU 淘汰，默认 1000
    """

    def __init__(self, cooldown_seconds: int = 300, max_cache_size: int = 1000) -> None:
        self._cooldown = cooldown_seconds
        self._max_size = max_cache_size
        self._cache: dict[str, _AlertRecord] = {}

    def should_alert(self, level: str, message: str) -> bool:
        """
        判断指定事件是否应触发告警。

        Returns:
            True  = 放行（首次出现 or 冷却期已过）
            False = 抑制（冷却期内重复出现）
        """
        fp  = self._fingerprint(level, message)
        now = time.time()
        rec = self._cache.get(fp)

        if rec is None:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            self._cache[fp] = _AlertRecord(first_seen=now, last_seen=now, count=1)
            return True

        rec.count    += 1
        rec.last_seen = now

        if now - rec.first_seen >= self._cooldown:
            self._cache[fp] = _AlertRecord(first_seen=now, last_seen=now, count=1)
            return True

        return False

    def filter_events(self, events: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        过滤事件列表，区分"应告警"与"冷却中被抑制"。

        Args:
            events: perceive() 返回的 triggered_events 列表

        Returns:
            (to_alert, suppressed)
              to_alert   — 需要执行告警的事件子集
              suppressed — 冷却期内被抑制的事件子集
        """
        to_alert:   list[dict] = []
        suppressed: list[dict] = []
        for evt in events:
            level   = str(
                evt.get("level") or evt.get("severity")
                or evt.get("_level_normalized") or "unknown"
            )
            message = str(evt.get("message") or "")
            if self.should_alert(level, message):
                to_alert.append(evt)
            else:
                suppressed.append(evt)
        return to_alert, suppressed

    def stats(self) -> dict:
        """返回当前缓存统计（用于调试 / 监控）"""
        now    = time.time()
        active = sum(1 for r in self._cache.values() if now - r.first_seen < self._cooldown)
        return {
            "cache_size":    len(self._cache),
            "active_alerts": active,
            "cooldown_s":    self._cooldown,
        }

    @staticmethod
    def _fingerprint(level: str, message: str) -> str:
        key = f"{level.lower().strip()}:{message[:100]}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def _evict_oldest(self) -> None:
        """移除 last_seen 最早的条目（LRU 淘汰）"""
        if not self._cache:
            return
        oldest = min(self._cache, key=lambda k: self._cache[k].last_seen)
        del self._cache[oldest]


def _load_tools_module():
    """加载同目录下的 tools 模块（兼容插件加载器独立加载 PLUGIN.py）"""
    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    try:
        from tools import (  # type: ignore[import]
            ParseLogTool, PerceiveTool, ReadLogsTool,
            ExecuteDecisionTool, StrategyPerceiveTool,
        )
        return ParseLogTool, PerceiveTool, ReadLogsTool, ExecuteDecisionTool, StrategyPerceiveTool
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "perception_tools",
            plugin_dir / "tools.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return (
                mod.ParseLogTool, mod.PerceiveTool, mod.ReadLogsTool,
                mod.ExecuteDecisionTool, mod.StrategyPerceiveTool,
            )
    raise RuntimeError("Failed to load perception tools")


def _load_strategy_module():
    """加载同目录下的 strategy 模块"""
    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    try:
        from strategy import build_controller_from_config  # type: ignore[import]
        return build_controller_from_config
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "perception_strategy",
            plugin_dir / "strategy.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.build_controller_from_config
    raise RuntimeError("Failed to load perception strategy")


class PerceptionPlugin(Plugin):
    """主动感知器插件"""

    metadata = PluginMetadata(
        id="integration.perception",
        name="主动感知器",
        version="2.0.0",
        type=PluginType.INTEGRATION,
        description=(
            "基于 ATON/TOON 日志的主动感知与决策，"
            "支持 parse_log、perceive、read_logs、execute_decision、strategy_perceive"
        ),
        author="OntoMind",
        provides=["perception", "log_parser", "strategy_perception"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._tools: List[BaseTool] | None = None
        self._strategy_controller = None
        self._strategy_tool = None

    async def on_plugin_load(self, context) -> None:
        await super().on_plugin_load(context)
        config = context.config or {}
        self._log_path = config.get("log_path", "./logs")
        filter_rules = config.get("filter_rules", {})
        self._default_rules = {
            "levels":         filter_rules.get("level", ["error", "warn"]),
            "error_triggers": filter_rules.get("error_triggers", "find_user"),
            "warn_triggers":  filter_rules.get("warn_triggers", "find_user"),
        }
        cooldown = int(config.get("cooldown_seconds", 300))
        self._deduplicator = AlertDeduplicator(cooldown_seconds=cooldown)

        # 策略控制器配置
        self._strategies_cfg   = config.get("strategies", [])
        self._merge_mode       = config.get("merge_mode", "highest_priority")
        self._parallel         = bool(config.get("parallel", True))

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()
        (
            ParseLogTool, PerceiveTool, ReadLogsTool,
            ExecuteDecisionTool, StrategyPerceiveTool,
        ) = _load_tools_module()

        self._execute_tool = ExecuteDecisionTool(default_rules=self._default_rules)

        # 如果配置了 strategies，则构建策略控制器并注入到 StrategyPerceiveTool
        self._strategy_tool = StrategyPerceiveTool(
            default_strategies=self._strategies_cfg,
            default_merge_mode=self._merge_mode,
        )
        if self._strategies_cfg:
            try:
                build_controller_from_config = _load_strategy_module()
                self._strategy_controller = build_controller_from_config(
                    self._strategies_cfg,
                    merge_mode=self._merge_mode,
                    parallel=self._parallel,
                )
                self._strategy_tool.set_controller(self._strategy_controller)
            except Exception as exc:
                self.context.logger.warning(
                    f"Perception: strategy controller init failed: {exc}"
                )

        self._tools = [
            ParseLogTool(),
            PerceiveTool(default_rules=self._default_rules),
            ReadLogsTool(default_path=self._log_path),
            self._execute_tool,
            self._strategy_tool,
        ]
        self.context.logger.info(
            f"Perception plugin activated with tools: {[t.name for t in self._tools]}"
        )

    async def on_engine_start(self, engine) -> None:
        """引擎启动时：注入执行器、注入 Agent 策略引擎、注册 Cron/Event/Webhook 触发器"""
        config = self.context.config or {}
        log = self.context.logger

        event_bus = getattr(engine, "event_bus", None) or getattr(engine, "eventBus", None)

        # --- Epic 4: 决策执行器（初始化失败时降级，不阻断 engine 启动）---
        try:
            try:
                from executor import DecisionExecutor
            except ImportError:
                from .executor import DecisionExecutor
            self._executor = DecisionExecutor(
                engine=engine,
                event_bus=event_bus,
                engine_factory=getattr(engine, "create_engine", None),
                execute_actions=config.get("execute_actions") or {},
                call_agent_config=config.get("call_agent") or {},
                logger=log,
            )
            self._execute_tool.set_executor(self._executor)
        except Exception as e:
            log.warning(
                f"Perception: executor initialization failed, execute_decision tool disabled: {e}"
            )
            self._executor = None

        # --- 策略控制器：给 agent 类型策略注入引擎 ---
        if self._strategy_controller is not None:
            try:
                try:
                    from strategy import AgentStrategy
                except ImportError:
                    from .strategy import AgentStrategy  # type: ignore[no-redef]
                for s in self._strategy_controller.strategies:
                    if isinstance(s, AgentStrategy):
                        s.set_engine(engine)
                log.info("Perception: agent strategies wired with engine")
            except Exception as exc:
                log.warning(f"Perception: failed to wire agent strategies: {exc}")

        # --- Epic 6: 触发与调度 ---
        automation = self._ensure_automation(engine, event_bus)
        if automation:
            await automation.start()
            self._register_cron(config, automation, log)
            self._register_event_triggers(config, automation, event_bus, log)
            self._register_webhooks(config, automation, log)

    # ---- 触发器注册 ----

    @staticmethod
    def _ensure_automation(engine, event_bus):
        """获取或创建 AutomationManager"""
        try:
            from pyagentforge.automation.scheduler import AutomationManager
            automation = getattr(engine, "automation_manager", None)
            if automation is None:
                automation = AutomationManager(engine, event_bus=event_bus)
                engine.automation_manager = automation
            return automation
        except ImportError:
            return None

    def _register_cron(self, config, automation, log):
        """Story 6.1: Cron 定时触发（含聚合感知 + 去重，支持策略控制器）"""
        cron_expr = config.get("cron_expr")
        if not cron_expr:
            return

        async def _cron_callback() -> None:
            """Cron 定时感知回调：聚合多文件事件后去重执行"""
            import glob as glob_mod
            import os

            try:
                from parser import parse_log
                from perception import perceive, PerceptionResult, DecisionType
                from executor import execute_decision
            except ImportError:
                from .parser import parse_log
                from .perception import perceive, PerceptionResult, DecisionType
                from .executor import execute_decision

            files = sorted(glob_mod.glob(os.path.join(self._log_path, "*")))[:10]
            if not files:
                return

            all_events: list[dict] = []
            merged_result = None

            for fp in files:
                try:
                    with open(fp, encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
                    parsed = parse_log(raw)

                    # 优先使用策略控制器，降级为单规则感知
                    if self._strategy_controller is not None:
                        r, _ = await self._strategy_controller.apply_all(parsed)
                    else:
                        r = perceive(parsed, self._default_rules, aggregate=True)

                    all_events.extend(r.triggered_events or [])
                    if r.decision.value != "none" and merged_result is None:
                        merged_result = r
                except Exception as exc:
                    log.debug(f"Cron perception skip {fp}: {exc}")

            if not all_events:
                return

            to_alert, suppressed = self._deduplicator.filter_events(all_events)
            if suppressed:
                log.debug(f"Cron dedup: {len(suppressed)} event(s) suppressed")
            if not to_alert or self._executor is None:
                return

            mock_result = PerceptionResult(
                decision=(merged_result.decision if merged_result else DecisionType.FIND_USER),
                reason=f"Cron poll: {len(to_alert)} new event(s) detected",
                data={"triggered_count": len(to_alert)},
                triggered_events=to_alert,
            )
            await execute_decision(mock_result, executor=self._executor)

        try:
            automation.add_cron_task(
                "perception_poll",
                cron_expr,
                _cron_callback,
                name="Perception Poll",
            )
            log.info(f"Perception cron registered: {cron_expr}")
        except Exception as e:
            log.warning(f"Failed to register cron: {e}")

    def _register_event_triggers(self, config, automation, event_bus, log):
        """Story 6.2: EventBus 事件触发"""
        triggers = config.get("event_triggers") or []
        if not triggers or not event_bus:
            return
        for i, trigger in enumerate(triggers):
            event_type = trigger.get("event_type")
            if not event_type:
                continue
            condition_field = trigger.get("condition_field")
            condition_value = trigger.get("condition_value")
            condition = None
            if condition_field:
                condition = lambda data, _f=condition_field, _v=condition_value: (
                    data.get(_f) == _v if _v is not None else bool(data.get(_f))
                )
            task_id = f"perception_event_{i}_{event_type}"
            action = trigger.get(
                "action",
                f"Read logs from {self._log_path}, parse and perceive. Event: {event_type}.",
            )
            try:
                automation.add_event_task(
                    task_id,
                    event_type,
                    action,
                    name=f"Perception on {event_type}",
                    condition=condition,
                )
                log.info(f"Perception event trigger registered: {event_type}")
            except Exception as e:
                log.warning(f"Failed to register event trigger {event_type}: {e}")

    def _register_webhooks(self, config, automation, log):
        """Story 6.3: Webhook 触发"""
        webhook_cfg = config.get("webhook")
        if not webhook_cfg:
            return
        path = webhook_cfg.get("path")
        if not path:
            return
        secret = webhook_cfg.get("secret")

        async def _webhook_handler(payload: dict, headers: dict) -> dict:
            """Webhook 接收处理：payload → parse → perceive/strategy(聚合) → 去重 → execute"""
            try:
                from parser import parse_log
                from perception import perceive
                from executor import execute_decision
            except ImportError:
                from .parser import parse_log
                from .perception import perceive
                from .executor import execute_decision

            raw = payload.get("log") or payload.get("data") or payload.get("raw") or ""
            if isinstance(raw, dict):
                parsed = raw
            elif isinstance(raw, str) and raw.strip():
                parsed = parse_log(raw)
            else:
                return {"status": "skipped", "reason": "no log data in payload"}

            # 优先使用策略控制器，降级为单规则感知
            if self._strategy_controller is not None:
                result, _details = await self._strategy_controller.apply_all(parsed)
            else:
                result = perceive(parsed, self._default_rules, aggregate=True)

            if result.decision.value == "none":
                return {"status": "skipped", "reason": "no actionable events"}

            triggered = result.triggered_events or []
            to_alert, suppressed = self._deduplicator.filter_events(triggered)

            if not to_alert:
                return {
                    "status":      "suppressed",
                    "reason":      f"All {len(triggered)} event(s) are within cooldown window",
                    "suppressed":  len(suppressed),
                    "decision":    result.decision.value,
                    "dedup_stats": self._deduplicator.stats(),
                }

            if self._executor is None:
                return {
                    "status":    "warning",
                    "decision":  result.decision.value,
                    "reason":    result.reason,
                    "alerted":   len(to_alert),
                    "suppressed": len(suppressed),
                    "execution": {
                        "success": False,
                        "message": "Executor not configured: on_engine_start was not called or failed",
                    },
                }

            exec_result = await execute_decision(result, executor=self._executor)
            return {
                "status":    "ok",
                "decision":  result.decision.value,
                "reason":    result.reason,
                "alerted":   len(to_alert),
                "suppressed": len(suppressed),
                "execution": {"success": exec_result.success, "message": exec_result.message},
            }

        try:
            automation.add_webhook_handler(path, _webhook_handler, secret=secret)
            log.info(f"Perception webhook registered: {path}")
        except Exception as e:
            log.warning(f"Failed to register webhook {path}: {e}")

    def get_tools(self) -> List[BaseTool]:
        return self._tools or []
