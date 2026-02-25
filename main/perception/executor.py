"""
决策执行器

根据 PerceptionResult.decision 分发到三种执行路径：
- find_user: 通知用户（事件、回调、API）
- execute: 执行预定义动作（shell、HTTP）
- call_agent: 委派其它 Agent
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

try:
    from .perception import DecisionType, PerceptionResult
except ImportError:
    from perception import DecisionType, PerceptionResult


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    message: str
    details: dict[str, Any] | None = None


# --- Story 4.1: find_user 通知路径 ---

async def _default_find_user(
    result: PerceptionResult,
    event_bus: Any | None,
    notify_callback: Callable[..., Awaitable[None] | None] | None,
    logger: Any | None,
) -> ExecutionResult:
    """
    默认 find_user 实现：优先 EventBus，其次 callback，最后 log。
    """
    payload = {
        "reason": result.reason,
        "data": result.data,
        "metadata": result.metadata or {},
        "source": "perception",
    }
    content = f"[Perception Alert] {result.reason}\nData: {json.dumps(result.data, ensure_ascii=False)}"

    # 1. EventBus 事件
    if event_bus:
        try:
            pub = getattr(event_bus, "publish", None) or getattr(event_bus, "emit", None)
            if pub and callable(pub):
                if asyncio.iscoroutinefunction(pub):
                    await pub("perception.alert", payload)
                else:
                    pub("perception.alert", payload)
                return ExecutionResult(True, "Notification sent via EventBus", {"channel": "event_bus"})
        except Exception as e:
            if logger:
                logger.warning(f"EventBus publish failed: {e}")

    # 2. 回调
    if notify_callback:
        try:
            if asyncio.iscoroutinefunction(notify_callback):
                await notify_callback(result, content)
            else:
                notify_callback(result, content)
            return ExecutionResult(True, "Notification sent via callback", {"channel": "callback"})
        except Exception as e:
            if logger:
                logger.warning(f"Notify callback failed: {e}")
            return ExecutionResult(False, f"Callback failed: {e}")

    # 3. 仅日志
    if logger:
        logger.warning(f"Perception find_user (no channel): {content}")
    return ExecutionResult(True, "Logged (no notification channel configured)", {"channel": "log"})


# --- Story 4.2: execute 动作路径 ---

async def _run_shell(cmd: str | list, logger: Any | None) -> ExecutionResult:
    """执行 shell 命令"""
    try:
        if isinstance(cmd, list):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout, stderr = await proc.communicate()
        out = stdout.decode(errors="ignore").strip()
        err = stderr.decode(errors="ignore").strip()
        if logger and (out or err):
            logger.info(f"Shell output: {out or err}")
        return ExecutionResult(
            proc.returncode == 0,
            out or err or f"exit {proc.returncode}",
            {"returncode": proc.returncode, "stderr": err},
        )
    except Exception as e:
        if logger:
            logger.error(f"Shell execution failed: {e}")
        return ExecutionResult(False, str(e), {"error": str(e)})


async def _run_http(config: dict, logger: Any | None) -> ExecutionResult:
    """执行 HTTP 请求（使用 asyncio.to_thread + urllib）"""
    import urllib.request

    def _sync_request() -> tuple[int, str]:
        url = config.get("url") or config.get("endpoint")
        if not url:
            raise ValueError("Missing url/endpoint in HTTP config")
        method = (config.get("method") or "POST").upper()
        headers = dict(config.get("headers") or {})
        body = config.get("body")
        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                headers.setdefault("Content-Type", "application/json; charset=utf-8")
            elif isinstance(body, str):
                data = body.encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in headers.items():
            req.add_header(k, str(v))
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode(errors="ignore")
            return (resp.status, text)

    try:
        status, text = await asyncio.to_thread(_sync_request)
        ok = 200 <= status < 300
        return ExecutionResult(
            ok,
            f"HTTP {status}: {text[:200]}",
            {"status": status, "body_preview": text[:500]},
        )
    except Exception as e:
        if logger:
            logger.error(f"HTTP execution failed: {e}")
        return ExecutionResult(False, str(e), {"error": str(e)})


async def _default_execute(
    result: PerceptionResult,
    execute_actions: dict[str, Any],
    logger: Any | None,
) -> ExecutionResult:
    """
    默认 execute 实现：根据配置执行 shell 或 HTTP。
    配置格式:
      execute_actions:
        default: { type: shell, cmd: "echo Alert" }
        或: { type: http, url: "...", method: "POST" }
    """
    actions = execute_actions or {}
    # 从 result.data 中取 action_key，或使用 default
    action_key = (result.data or {}).get("action_key") or (result.metadata or {}).get("action_key") or "default"
    action_cfg = actions.get(action_key) or actions.get("default")
    if not action_cfg:
        return ExecutionResult(False, "No execute action configured", {"action_key": action_key})

    action_type = (action_cfg.get("type") or "shell").lower()
    if action_type == "shell":
        cmd = action_cfg.get("cmd") or action_cfg.get("command")
        if not cmd:
            return ExecutionResult(False, "Shell action missing cmd/command")
        return await _run_shell(cmd, logger)
    if action_type == "http":
        return await _run_http(action_cfg, logger)
    return ExecutionResult(False, f"Unknown action type: {action_type}", {})


# --- Story 4.3: call_agent 委派路径 ---

async def _default_call_agent(
    result: PerceptionResult,
    engine: Any | None,
    prompt_template: str | None,
    target_agent: str | None,
    engine_factory: Callable[..., Any] | None,
    logger: Any | None,
) -> ExecutionResult:
    """
    默认 call_agent 实现：通过 engine.run(prompt) 委派。
    若配置了 engine_factory(agent_type)，则创建子引擎执行。
    """
    if not engine and not engine_factory:
        return ExecutionResult(False, "No engine or engine_factory for call_agent", {})

    template = prompt_template or "Handle this perception alert.\n\nReason: {reason}\n\nData: {data}"
    try:
        prompt = template.format(
            reason=result.reason,
            data=json.dumps(result.data, ensure_ascii=False),
            metadata=json.dumps(result.metadata or {}, ensure_ascii=False),
        )
    except KeyError:
        prompt = f"Handle: {result.reason}\nData: {result.data}"

    target = target_agent or "main"
    run_engine = engine

    if engine_factory and target != "main":
        run_engine = engine_factory(target)

    if not run_engine:
        return ExecutionResult(False, f"Could not create engine for {target}", {})

    try:
        if hasattr(run_engine, "run"):
            resp = await run_engine.run(prompt)
            return ExecutionResult(True, str(resp)[:500], {"response_preview": str(resp)[:200]})
        return ExecutionResult(False, "Engine has no run method", {})
    except Exception as e:
        if logger:
            logger.error(f"Call agent failed: {e}")
        return ExecutionResult(False, str(e), {"error": str(e)})


# --- 主执行器 ---


class DecisionExecutor:
    """
    决策执行器：根据 PerceptionResult 分发到 find_user / execute / call_agent。
    """

    def __init__(
        self,
        *,
        engine: Any = None,
        event_bus: Any = None,
        engine_factory: Callable[..., Any] | None = None,
        notify_callback: Callable[..., Awaitable[None] | None] | None = None,
        execute_actions: dict[str, Any] | None = None,
        call_agent_config: dict[str, Any] | None = None,
        logger: Any = None,
    ):
        self.engine = engine
        self.event_bus = event_bus
        self.engine_factory = engine_factory
        self.notify_callback = notify_callback
        self.execute_actions = execute_actions or {}
        self.call_agent_config = call_agent_config or {}
        self.logger = logger

    async def execute(self, result: PerceptionResult) -> ExecutionResult:
        """执行决策"""
        if result.decision == DecisionType.NONE:
            return ExecutionResult(True, "No action required", {"decision": "none"})

        if result.decision == DecisionType.FIND_USER:
            return await _default_find_user(
                result,
                self.event_bus,
                self.notify_callback,
                self.logger,
            )
        if result.decision == DecisionType.EXECUTE:
            return await _default_execute(
                result,
                self.execute_actions,
                self.logger,
            )
        if result.decision == DecisionType.CALL_AGENT:
            cfg = self.call_agent_config
            return await _default_call_agent(
                result,
                self.engine,
                cfg.get("prompt_template"),
                cfg.get("target_agent"),
                self.engine_factory,
                self.logger,
            )
        return ExecutionResult(False, f"Unknown decision: {result.decision}", {})


async def execute_decision(
    result: PerceptionResult,
    executor: DecisionExecutor | None = None,
    **executor_kw: Any,
) -> ExecutionResult:
    """
    便捷函数：执行决策。
    若未提供 executor，则用 executor_kw 创建临时执行器。
    """
    ex = executor or DecisionExecutor(**executor_kw)
    return await ex.execute(result)
