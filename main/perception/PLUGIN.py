"""
主动感知器插件

基于 ATON/TOON 日志的主动感知与决策
"""

import importlib.util
import sys
from pathlib import Path
from typing import List

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


def _load_tools_module():
    """加载同目录下的 tools 模块（兼容插件加载器独立加载 PLUGIN.py）"""
    plugin_dir = Path(__file__).resolve().parent
    if str(plugin_dir) not in sys.path:
        sys.path.insert(0, str(plugin_dir))
    try:
        from tools import ParseLogTool, PerceiveTool, ReadLogsTool, ExecuteDecisionTool
        return ParseLogTool, PerceiveTool, ReadLogsTool, ExecuteDecisionTool
    except ImportError:
        spec = importlib.util.spec_from_file_location(
            "perception_tools",
            plugin_dir / "tools.py",
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.ParseLogTool, mod.PerceiveTool, mod.ReadLogsTool, mod.ExecuteDecisionTool
    raise RuntimeError("Failed to load perception tools")


class PerceptionPlugin(Plugin):
    """主动感知器插件"""

    metadata = PluginMetadata(
        id="integration.perception",
        name="主动感知器",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="基于 ATON/TOON 日志的主动感知与决策，支持 parse_log、perceive、read_logs、execute_decision",
        author="OntoMind",
        provides=["perception", "log_parser"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._tools: List[BaseTool] | None = None

    async def on_plugin_load(self, context) -> None:
        await super().on_plugin_load(context)
        config = context.config or {}
        self._log_path = config.get("log_path", "./logs")
        self._rules = config.get("filter_rules", {})
        self._default_rules = {
            "levels": self._rules.get("level", ["error", "warn"]),
            "error_triggers": self._rules.get("error_triggers", "find_user"),
            "warn_triggers": self._rules.get("warn_triggers", "find_user"),
        }

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()
        ParseLogTool, PerceiveTool, ReadLogsTool, ExecuteDecisionTool = _load_tools_module()
        self._execute_tool = ExecuteDecisionTool(default_rules=self._default_rules)
        self._tools = [
            ParseLogTool(),
            PerceiveTool(default_rules=self._default_rules),
            ReadLogsTool(default_path=self._log_path),
            self._execute_tool,
        ]
        self.context.logger.info(
            f"Perception plugin activated with tools: {[t.name for t in self._tools]}"
        )

    async def on_engine_start(self, engine) -> None:
        """引擎启动时：注入执行器、注册 Cron/Event/Webhook 触发器"""
        config = self.context.config or {}
        log = self.context.logger

        # --- Epic 4: 决策执行器 ---
        try:
            from executor import DecisionExecutor
        except ImportError:
            from .executor import DecisionExecutor
        event_bus = getattr(engine, "event_bus", None) or getattr(engine, "eventBus", None)
        self._executor = DecisionExecutor(
            engine=engine,
            event_bus=event_bus,
            engine_factory=getattr(engine, "create_engine", None),
            execute_actions=config.get("execute_actions") or {},
            call_agent_config=config.get("call_agent") or {},
            logger=log,
        )
        self._execute_tool.set_executor(self._executor)

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
        """Story 6.1: Cron 定时触发"""
        cron_expr = config.get("cron_expr")
        if not cron_expr:
            return
        try:
            automation.add_cron_task(
                "perception_poll",
                cron_expr,
                f"Read logs from {self._log_path}, parse and perceive, execute decision if needed.",
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
            """Webhook 接收处理：payload → parse → perceive → execute"""
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

            result = perceive(parsed, self._default_rules)
            exec_result = await execute_decision(result, executor=self._executor)
            return {
                "status": "ok",
                "decision": result.decision.value,
                "reason": result.reason,
                "execution": {"success": exec_result.success, "message": exec_result.message},
            }

        try:
            automation.add_webhook_handler(path, _webhook_handler, secret=secret)
            log.info(f"Perception webhook registered: {path}")
        except Exception as e:
            log.warning(f"Failed to register webhook {path}: {e}")

    def get_tools(self) -> List[BaseTool]:
        return self._tools or []
