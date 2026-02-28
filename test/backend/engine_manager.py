"""
Engine Manager

基于 main/Agent/ 范式加载 Agent 定义。
从 main/Agent/{agent-name}/agent.yaml 读取模型配置，
从 main/Agent/{agent-name}/system_prompt.md 读取系统提示词，
通过 pyagentforge.building.loader.AgentLoader 解析成 AgentSchema，
再构建 AgentEngine 供各 session 使用。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ENGINE_PATH = str(Path(__file__).resolve().parents[2] / "main" / "agentforge-engine")
AGENT_DIR = Path(__file__).resolve().parents[2] / "main" / "Agent"
WORKSPACE_DIR = str(Path(__file__).resolve().parents[1] / "workspace")

Path(WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)


def _ensure_engine_path() -> None:
    if ENGINE_PATH not in sys.path:
        sys.path.insert(0, ENGINE_PATH)


# ---------------------------------------------------------------------------
# Agent 定义加载 (from main/Agent/)
# ---------------------------------------------------------------------------


def _load_raw_definition(agent_name: str) -> dict[str, Any]:
    """
    从 main/Agent/{agent_name}/ 加载 agent.yaml，
    并将 system_prompt.md 的内容注入到 data["behavior"]["system_prompt"]。
    """
    agent_dir = AGENT_DIR / agent_name
    yaml_path = agent_dir / "agent.yaml"
    prompt_path = agent_dir / "system_prompt.md"

    if not yaml_path.exists():
        raise FileNotFoundError(f"Agent YAML not found: {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    if prompt_path.exists():
        system_prompt = prompt_path.read_text(encoding="utf-8").strip()
        data.setdefault("behavior", {})["system_prompt"] = system_prompt
        logger.info("Loaded system_prompt.md for agent: %s", agent_name)
    else:
        logger.warning("system_prompt.md not found for agent: %s", agent_name)

    return data


def _parse_schema(data: dict[str, Any]) -> Any:
    """
    使用 pyagentforge AgentLoader 的 _parse_schema 逻辑将原始 dict 解析为 AgentSchema。
    避免走完整 AgentFactory 流水线（工具注册仍由各 _create_*_engine 手动完成）。
    """
    _ensure_engine_path()
    from pyagentforge.building.loader import AgentDependencyResolver, AgentLoader
    from pyagentforge.agents.registry import AgentRegistry

    # 最小化初始化 loader（只借用 _parse_schema，不走 _register_loaded）
    loader = AgentLoader.__new__(AgentLoader)
    loader._loaded = {}
    loader._registry = AgentRegistry()
    loader._watcher = None
    loader._dependency_resolver = AgentDependencyResolver(loader)
    return loader._parse_schema(data)


def _apply_schema_overrides(schema: Any, overrides: dict[str, Any]) -> None:
    """
    将运行时配置覆盖就地应用到 AgentSchema 实例。

    支持覆盖字段:
      model.temperature, model.max_tokens
      limits.max_iterations
      (system_prompt 由调用方通过 system_prompt_override 参数处理)
    """
    model_map = {"temperature": "temperature", "max_tokens": "max_tokens"}
    limit_map = {"max_iterations": "max_iterations"}

    for key, value in overrides.items():
        if value is None:
            continue
        if key in model_map and hasattr(schema, "model"):
            try:
                setattr(schema.model, model_map[key], value)
            except Exception as e:
                logger.warning("Could not override schema.model.%s: %s", key, e)
        elif key in limit_map and hasattr(schema, "limits"):
            try:
                setattr(schema.limits, limit_map[key], value)
            except Exception as e:
                logger.warning("Could not override schema.limits.%s: %s", key, e)


def _make_kernel_config(schema: Any, system_prompt_override: str | None = None) -> Any:
    """
    将 AgentSchema 转换为 kernel-level AgentConfig（dataclass 版，带 max_iterations）。
    system_prompt_override 可覆盖 schema 中的系统提示词（用于运行时追加 workspace 等信息）。
    """
    _ensure_engine_path()
    from pyagentforge.kernel.engine import AgentConfig

    prompt = system_prompt_override if system_prompt_override is not None else schema.behavior.system_prompt

    return AgentConfig(
        system_prompt=prompt,
        max_tokens=schema.model.max_tokens,
        temperature=schema.model.temperature,
        max_iterations=schema.limits.max_iterations,
    )


# ---------------------------------------------------------------------------
# 模块级：加载系统提示词（供 app.py import ACTIVE_SYSTEM_PROMPT 使用）
# ---------------------------------------------------------------------------

def _read_system_prompt(agent_name: str) -> str:
    path = AGENT_DIR / agent_name / "system_prompt.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


PASSIVE_SYSTEM_PROMPT: str = _read_system_prompt("passive-agent")
ACTIVE_SYSTEM_PROMPT: str = _read_system_prompt("active-agent")


# ---------------------------------------------------------------------------
# EngineManager
# ---------------------------------------------------------------------------


class EngineManager:
    """
    Session-level AgentEngine lifecycle manager.

    Engines are keyed by (session_id, provider_fingerprint).
    If the provider config changes (model/api_key), the engine is recreated
    so it uses the updated provider — the old conversation history is cleared.
    """

    # {session_id: {"engine": AgentEngine, "fingerprint": str}}
    _passive_engines: dict[str, dict[str, Any]] = {}
    _active_engines: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _make_fingerprint(provider: Any) -> str:
        """Stable identity string for a provider instance."""
        return f"{provider.__class__.__name__}:{provider.model}"

    # ------------------------------------------------------------------
    # Engine factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def _create_passive_engine(cls, provider: Any) -> Any:
        _ensure_engine_path()
        from pyagentforge.kernel.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry

        # 1. 从 main/Agent/ 加载 passive-agent 定义
        schema = _parse_schema(_load_raw_definition("passive-agent"))

        # 2. 追加 workspace_dir 到系统提示词（运行时信息）
        enriched_prompt = schema.behavior.system_prompt + (
            f"\n\n工作目录：{WORKSPACE_DIR}\n"
            "请用中文回复。生成代码时，在工作目录中创建文件并用 bash 验证运行。"
        )

        # 3. 构建 kernel AgentConfig
        config = _make_kernel_config(schema, system_prompt_override=enriched_prompt)

        # 4. 注册工具（主动注册，schema 中的工具名仅作声明用途）
        registry = ToolRegistry()

        registry.register_builtin_tools()  # bash, read, write, edit, glob, grep

        try:
            registry.register_extended_tools()  # webfetch, websearch, multiedit, todo
        except Exception as e:
            logger.warning("Extended tools unavailable: %s", e)

        try:
            from pyagentforge.tools.builtin.ls import LsTool
            registry.register(LsTool())
        except Exception as e:
            logger.warning("ls tool unavailable: %s", e)

        try:
            from pyagentforge.tools.builtin.plan import PlanTool
            registry.register(PlanTool())
        except Exception as e:
            logger.warning("plan tool unavailable: %s", e)

        try:
            from pyagentforge.tools.builtin.apply_patch import ApplyPatchTool, DiffTool
            registry.register(ApplyPatchTool())
            registry.register(DiffTool())
        except Exception as e:
            logger.warning("apply_patch/diff tools unavailable: %s", e)

        try:
            registry.register_p1_tools(working_dir=WORKSPACE_DIR)
        except Exception as e:
            logger.warning("P1 tools unavailable: %s", e)

        return AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

    @classmethod
    def _create_active_engine(
        cls, provider: Any, config_overrides: dict[str, Any] | None = None
    ) -> Any:
        _ensure_engine_path()
        from pyagentforge.kernel.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry

        from active_tools_impl import (
            GenerateMockDataTool,
            PerceiveTool,
            SituationCompareTool,
            SituationReportTool,
            ThreatAnalysisTool,
        )

        # 1. 从 main/Agent/ 加载 active-agent 定义
        schema = _parse_schema(_load_raw_definition("active-agent"))

        # 2. 应用运行时配置覆盖（优先级高于 agent.yaml）
        if config_overrides:
            _apply_schema_overrides(schema, config_overrides)
            logger.info("Active engine config overrides applied: %s", list(config_overrides.keys()))

        # 3. 构建 kernel AgentConfig（直接使用 schema 中的系统提示词）
        system_prompt_override = (config_overrides or {}).get("system_prompt")
        config = _make_kernel_config(schema, system_prompt_override=system_prompt_override)

        # 3. 注册工具
        registry = ToolRegistry()

        try:
            from pyagentforge.tools.builtin.webfetch import WebFetchTool
            from pyagentforge.tools.builtin.websearch import WebSearchTool
            registry.register(WebFetchTool())
            registry.register(WebSearchTool())
        except Exception as e:
            logger.warning("Web tools unavailable: %s", e)

        # 自定义战场工具（来自 test/backend/active_tools_impl.py）
        registry.register(PerceiveTool())
        registry.register(ThreatAnalysisTool())
        registry.register(SituationReportTool())
        registry.register(SituationCompareTool())
        registry.register(GenerateMockDataTool())

        return AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def get_or_create_passive(cls, session_id: str, provider: Any) -> Any:
        """Return the cached passive engine for this session, recreating if provider changed."""
        fp = cls._make_fingerprint(provider)
        entry = cls._passive_engines.get(session_id)
        if entry is None or entry["fingerprint"] != fp:
            engine = cls._create_passive_engine(provider)
            cls._passive_engines[session_id] = {"engine": engine, "fingerprint": fp}
            logger.info("Created passive engine session=%s model=%s", session_id, provider.model)
        return cls._passive_engines[session_id]["engine"]

    @classmethod
    def get_or_create_active(
        cls,
        session_id: str,
        provider: Any,
        config_overrides: dict[str, Any] | None = None,
    ) -> Any:
        """Return the cached active engine for this session, recreating if provider or config changed."""
        fp = cls._make_fingerprint(provider)
        if config_overrides:
            import json as _json
            fp += ":" + _json.dumps(config_overrides, sort_keys=True, default=str)
        entry = cls._active_engines.get(session_id)
        if entry is None or entry["fingerprint"] != fp:
            engine = cls._create_active_engine(provider, config_overrides=config_overrides)
            cls._active_engines[session_id] = {"engine": engine, "fingerprint": fp}
            logger.info("Created active engine session=%s model=%s", session_id, provider.model)
        return cls._active_engines[session_id]["engine"]

    @classmethod
    def destroy_passive(cls, session_id: str) -> None:
        cls._passive_engines.pop(session_id, None)
        logger.debug("Destroyed passive engine session=%s", session_id)

    @classmethod
    def destroy_active(cls, session_id: str) -> None:
        cls._active_engines.pop(session_id, None)
        logger.debug("Destroyed active engine session=%s", session_id)

    @classmethod
    def reset_all(cls) -> None:
        """Clear all cached engines (call after config change)."""
        count = len(cls._passive_engines) + len(cls._active_engines)
        cls._passive_engines.clear()
        cls._active_engines.clear()
        logger.info("All engines reset (%d cleared)", count)
