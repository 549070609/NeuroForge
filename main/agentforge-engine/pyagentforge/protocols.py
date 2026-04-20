"""协议格式适配的抽象与注册中心。

设计原则
--------
- **Kernel 零厂商**：本文件只保留协议抽象（``BaseProtocolAdapter`` /
  ``StreamEvent`` / ``ProtocolAdapterRegistry``）和启动时的自动装配逻辑。
- **vendor adapter 插件化**：OpenAI、Anthropic 等具体厂商协议放在
  ``pyagentforge.plugins.protocol.<vendor>`` 子包中，由本模块在 import 时
  通过两种渠道装配：
    1) ``importlib.metadata.entry_points`` 组 ``pyagentforge.protocol_adapters``
       —— 第三方包零代码接入；
    2) 未安装 entry_points（例如未 pip 安装、直接源码运行）时，回退到
       ``_load_bundled_adapters`` 显式 import 仓库内置 vendor 子包。
- **运行时注册表校验**：``ModelConfig.api_type`` 不再做静态 Literal 限制，
  而是由 ``LLMClient`` 在调用时查 ``PROTOCOL_ADAPTERS`` 得到 adapter，
  未注册则抛 ``Unsupported api_type`` —— 这使得"插件式供应商"真正成立。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urljoin

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.kernel.model_registry import ModelConfig
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


StreamEventType = Literal[
    "text_delta",
    "tool_call_delta",
    "usage",
    "done",
    "raw",
]


@dataclass
class StreamEvent:
    """通用流式事件（协议层抽象，零厂商字段）。

    各协议适配器负责把 SSE 行解码为本结构。调用方（LLMClient / 插件）
    基于 ``type`` 做路由；厂商专属字段请放进 ``raw``。
    """

    type: StreamEventType
    text: str | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments_delta: str | None = None
    tool_call_index: int | None = None
    usage: dict[str, int] | None = None
    stop_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProtocolAdapter(ABC):
    api_type: str
    endpoint: str
    stream_endpoint: str | None = None  # 为 None 则复用 endpoint + stream=True

    def build_url(self, config: ModelConfig) -> str:
        if not config.base_url:
            raise ValueError(f"Base URL is required for model: {config.id}")
        return urljoin(config.base_url.rstrip("/") + "/", self.endpoint.lstrip("/"))

    def build_stream_url(self, config: ModelConfig) -> str:
        if self.stream_endpoint is None:
            return self.build_url(config)
        if not config.base_url:
            raise ValueError(f"Base URL is required for model: {config.id}")
        return urljoin(
            config.base_url.rstrip("/") + "/",
            self.stream_endpoint.lstrip("/"),
        )

    def build_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(config.headers)
        return headers

    def build_stream_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = self.build_headers(config)
        headers["Accept"] = "text/event-stream"
        return headers

    @abstractmethod
    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        pass

    @abstractmethod
    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        pass

    def build_stream_request(
        self, request_params: dict[str, Any], config: ModelConfig
    ) -> dict[str, Any]:
        """默认实现：复用 build_request 并强制 ``stream=True``。

        若厂商协议需要不同的请求体（例如 payload 字段名不同），请覆写。
        """
        params = dict(request_params)
        params["stream"] = True
        return self.build_request(params, config)

    def parse_stream_line(self, line: str) -> StreamEvent | None:
        """解析 SSE 数据行 -> StreamEvent。

        返回 ``None`` 表示该行应被忽略（心跳 / 空行 / 注释 / 未知事件）。
        协议层实现的默认行为：仅识别 ``data: `` 前缀 + ``[DONE]`` 终止符；
        具体语义由子类通过 :meth:`parse_stream_chunk_payload` 决定。
        """
        stripped = line.strip()
        if not stripped:
            return None
        if stripped.startswith(":"):  # SSE 注释 / 心跳
            return None
        if not stripped.startswith("data:"):
            # 协议层不认识的行（可能是 event: name），交给子类 parse_event_line 处理
            return self.parse_event_line(stripped)
        payload = stripped[len("data:"):].strip()
        if payload == "[DONE]":
            return StreamEvent(type="done")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return self.parse_stream_chunk_payload(decoded)

    def parse_event_line(self, line: str) -> StreamEvent | None:
        """供子类覆写：处理非 ``data:`` 开头的 SSE 元数据行（如 ``event: name``）。"""
        return None

    def parse_stream_chunk_payload(self, payload: dict[str, Any]) -> StreamEvent | None:
        """供子类覆写：把一帧已解析的 JSON 负载映射为 :class:`StreamEvent`。"""
        return StreamEvent(type="raw", raw=payload)

    def aggregate_stream(
        self, events: list[StreamEvent], config: ModelConfig
    ) -> ProviderResponse:
        """把一次流的所有事件合成终态 :class:`ProviderResponse`。

        默认实现覆盖 OpenAI 风格（text_delta + tool_call_delta），子类可按需覆写。
        """
        texts: list[str] = []
        tool_calls_buf: dict[int, dict[str, Any]] = {}
        usage: dict[str, int] = {}
        stop_reason = "end_turn"

        for event in events:
            if event.type == "text_delta" and event.text:
                texts.append(event.text)
            elif event.type == "tool_call_delta":
                idx = event.tool_call_index if event.tool_call_index is not None else 0
                entry = tool_calls_buf.setdefault(
                    idx,
                    {"id": "", "name": "", "arguments": ""},
                )
                if event.tool_call_id:
                    entry["id"] = event.tool_call_id
                if event.tool_call_name:
                    entry["name"] = event.tool_call_name
                if event.tool_call_arguments_delta:
                    entry["arguments"] += event.tool_call_arguments_delta
            elif event.type == "usage" and event.usage:
                usage.update(event.usage)
            elif event.type == "done":
                if event.stop_reason:
                    stop_reason = event.stop_reason
                if event.usage:
                    usage.update(event.usage)

        content: list[TextBlock | ToolUseBlock] = []
        joined_text = "".join(texts)
        if joined_text:
            content.append(TextBlock(text=joined_text))

        if tool_calls_buf:
            stop_reason = "tool_use"
            for _, entry in sorted(tool_calls_buf.items()):
                try:
                    parsed_input = (
                        json.loads(entry["arguments"]) if entry["arguments"] else {}
                    )
                    if not isinstance(parsed_input, dict):
                        parsed_input = {}
                except json.JSONDecodeError:
                    parsed_input = {}
                content.append(
                    ToolUseBlock(
                        id=str(entry["id"]),
                        name=str(entry["name"]),
                        input=parsed_input,
                    )
                )

        return ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
        )

    def supports_streaming(self) -> bool:
        return True


class ProtocolAdapterRegistry:
    """协议适配器注册表。

    上游/第三方插件可通过 :func:`register_protocol_adapter` 注册自定义协议
    （如某厂商的私有格式），无需修改 kernel 源码。

    本类实现了最小的 Mapping 子集（``__getitem__`` / ``get`` / ``__contains__``
    / ``__iter__`` / ``keys``），保证任何遗留代码仍可把它当作原先的 ``dict`` 使用。
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseProtocolAdapter] = {}

    # --- 注册 API ---------------------------------------------------------

    def register(self, adapter: BaseProtocolAdapter, *, override: bool = False) -> None:
        api_type = getattr(adapter, "api_type", None)
        if not api_type:
            raise ValueError("ProtocolAdapter must declare non-empty `api_type`")
        if not override and api_type in self._adapters:
            raise ValueError(
                f"Protocol adapter for api_type={api_type!r} already registered; "
                f"pass override=True to replace"
            )
        self._adapters[api_type] = adapter

    def unregister(self, api_type: str) -> bool:
        return self._adapters.pop(api_type, None) is not None

    # --- dict-like 兼容 ---------------------------------------------------

    def __getitem__(self, api_type: str) -> BaseProtocolAdapter:
        return self._adapters[api_type]

    def get(self, api_type: str, default: Any = None) -> BaseProtocolAdapter | Any:
        return self._adapters.get(api_type, default)

    def __contains__(self, api_type: object) -> bool:
        return api_type in self._adapters

    def __iter__(self):
        return iter(self._adapters)

    def keys(self):
        return self._adapters.keys()

    def values(self):
        return self._adapters.values()

    def items(self):
        return self._adapters.items()

    def __len__(self) -> int:
        return len(self._adapters)


# 全局 registry。保留原名 ``PROTOCOL_ADAPTERS`` 以维持向后兼容：
# 旧代码 ``PROTOCOL_ADAPTERS.get(api_type)`` 继续可用。
PROTOCOL_ADAPTERS = ProtocolAdapterRegistry()

ENTRY_POINT_GROUP = "pyagentforge.protocol_adapters"


def register_protocol_adapter(adapter: BaseProtocolAdapter, *, override: bool = False) -> None:
    """上游插件注册自定义协议适配器。"""
    PROTOCOL_ADAPTERS.register(adapter, override=override)


def get_protocol_adapter(api_type: str) -> BaseProtocolAdapter | None:
    return PROTOCOL_ADAPTERS.get(api_type)


# ---------------------------------------------------------------------------
# Bootstrap：entry_points 优先 + bundled fallback
# ---------------------------------------------------------------------------


def _instantiate(target: Any) -> BaseProtocolAdapter | None:
    """把 entry_point.load() 得到的对象归一化为 BaseProtocolAdapter 实例。

    支持三种写法：
    - 指向 Adapter *类*：自动 ``target()``
    - 指向 Adapter *实例*：直接返回
    - 指向 *工厂函数*：调用并返回（需返回实例）
    """
    try:
        if isinstance(target, BaseProtocolAdapter):
            return target
        if isinstance(target, type) and issubclass(target, BaseProtocolAdapter):
            return target()
        if callable(target):
            obj = target()
            if isinstance(obj, BaseProtocolAdapter):
                return obj
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to instantiate protocol adapter: {exc}")
    return None


def _load_from_entry_points(registry: ProtocolAdapterRegistry) -> int:
    """从 ``pyagentforge.protocol_adapters`` entry_points 组加载 adapter。

    返回成功注册的数量。静默忽略加载失败的单个条目（记录 warning）。
    """
    loaded = 0
    try:
        from importlib.metadata import entry_points
    except Exception as exc:  # pragma: no cover
        logger.debug(f"importlib.metadata unavailable: {exc}")
        return 0

    try:
        # Python 3.10+ 推荐签名
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - 老版本兼容
        eps = entry_points().get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]

    for ep in eps:
        try:
            target = ep.load()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to load protocol adapter entry_point {ep.name!r}: {exc}"
            )
            continue

        adapter = _instantiate(target)
        if adapter is None:
            logger.warning(
                f"entry_point {ep.name!r} did not yield a BaseProtocolAdapter; skipping"
            )
            continue

        try:
            registry.register(adapter, override=True)
            loaded += 1
            logger.debug(
                f"Registered protocol adapter via entry_point: "
                f"{ep.name} -> {adapter.api_type}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to register adapter from entry_point {ep.name!r}: {exc}"
            )
    return loaded


def _load_bundled_adapters(registry: ProtocolAdapterRegistry) -> int:
    """兜底：当 entry_points 未发现任何 adapter 时（例如未 pip 安装），
    显式加载仓库自带的 vendor 子包，保证 kernel 开箱即用。
    """
    loaded = 0
    bundled = [
        ("pyagentforge.plugins.protocol.openai.chat", "OpenAIChatProtocol"),
        ("pyagentforge.plugins.protocol.openai.responses", "OpenAIResponsesProtocol"),
        ("pyagentforge.plugins.protocol.anthropic.messages", "AnthropicMessagesProtocol"),
    ]
    import importlib

    for module_path, class_name in bundled:
        try:
            module = importlib.import_module(module_path)
            adapter_cls = getattr(module, class_name)
            registry.register(adapter_cls(), override=True)
            loaded += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"Failed to load bundled adapter {module_path}:{class_name}: {exc}"
            )
    return loaded


def bootstrap_adapters(registry: ProtocolAdapterRegistry | None = None) -> int:
    """装配协议适配器。幂等：可重复调用。

    1. 先走 entry_points（第三方零代码接入）；
    2. 如果 entry_points 没装配到任何 adapter（例如本地源码开发未 pip 安装），
       回退到 bundled import，保证 openai/anthropic 等内置协议可用。
    """
    reg = registry or PROTOCOL_ADAPTERS
    n = _load_from_entry_points(reg)
    if n == 0:
        n = _load_bundled_adapters(reg)
    logger.debug(f"Protocol adapters bootstrapped: {n} (known: {sorted(reg.keys())})")
    return n


# 模块 import 时自动装配一次
bootstrap_adapters(PROTOCOL_ADAPTERS)


# ---------------------------------------------------------------------------
# 向后兼容 re-export：旧代码 ``from pyagentforge.protocols import OpenAIChatProtocol`` 仍可用
# ---------------------------------------------------------------------------

def __getattr__(name: str) -> Any:
    # 延迟到访问时再 import，避免循环依赖（concrete adapter 反向依赖本模块的 BaseProtocolAdapter）
    _compat_map = {
        "OpenAIChatProtocol": ("pyagentforge.plugins.protocol.openai.chat", "OpenAIChatProtocol"),
        "OpenAIResponsesProtocol": (
            "pyagentforge.plugins.protocol.openai.responses",
            "OpenAIResponsesProtocol",
        ),
        "AnthropicMessagesProtocol": (
            "pyagentforge.plugins.protocol.anthropic.messages",
            "AnthropicMessagesProtocol",
        ),
    }
    if name in _compat_map:
        import importlib

        module_path, class_name = _compat_map[name]
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    raise AttributeError(f"module 'pyagentforge.protocols' has no attribute {name!r}")
