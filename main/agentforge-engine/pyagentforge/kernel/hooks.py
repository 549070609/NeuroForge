"""
LLM 请求/响应扩展点（Kernel 层，零厂商耦合）

本模块定义两类可由上游插件注册的钩子：

- ``RequestInterceptor``：在 ``build_request`` 之后、HTTP 发送之前，
  可修改 ``payload`` / ``headers`` / ``url``。
- ``ResponseTransformer``：在 ``parse_response`` 之后、返回给调用方之前，
  可修改 ``ProviderResponse``（如剥离厂商专属的 ``<think>`` 标签、
  把 reasoning 文本搬入 ``ProviderResponse.reasoning`` 等）。

Kernel 自身从不注册任何钩子。所有厂商差异都通过插件在应用启动时
调用 :func:`register_request_interceptor` / :func:`register_response_transformer`
完成注入。

设计原则
--------
1. **零厂商知识**：本文件不出现任何厂商名称。
2. **匹配器驱动**：每个钩子附带 ``matcher`` 决定对哪些请求生效，
   kernel 只负责按优先级顺序筛选、派发。
3. **同步/异步均可**：钩子可返回同步值或 awaitable。
4. **链式不可变语义**：钩子必须返回新值（或原值），kernel 不假设原地修改。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar, runtime_checkable

from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.kernel.model_registry import ModelConfig

if False:  # TYPE_CHECKING 占位，避免 protocols 引入对 hooks 的循环导入
    from pyagentforge.protocols import StreamEvent as _StreamEvent  # noqa: F401


@dataclass
class HookContext:
    """钩子执行上下文（所有钩子类型共用）。

    Kernel 构造一次，在一次 LLM 调用内按序传递给所有匹配的钩子。
    """

    model_id: str
    model_config: ModelConfig
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        return self.model_config.provider

    @property
    def api_type(self) -> str:
        return self.model_config.api_type

    @property
    def resolved_model_name(self) -> str:
        return self.model_config.resolved_model_name


# ---------------------------------------------------------------------------
# 请求侧：RequestInterceptor
# ---------------------------------------------------------------------------

@dataclass
class RequestPayload:
    """可变请求负载容器，传入 RequestInterceptor 以便原地或复制修改。"""

    url: str
    headers: dict[str, str]
    payload: dict[str, Any]


@runtime_checkable
class RequestInterceptor(Protocol):
    """在 HTTP 发送之前修改请求。

    实现者须返回 :class:`RequestPayload`（可以是同一个对象，也可以新建）。
    可以是同步函数或 async 协程。
    """

    def __call__(
        self,
        ctx: HookContext,
        request: RequestPayload,
    ) -> RequestPayload | Awaitable[RequestPayload]:
        ...


# ---------------------------------------------------------------------------
# 响应侧：ResponseTransformer
# ---------------------------------------------------------------------------


@runtime_checkable
class ResponseTransformer(Protocol):
    """在 ``parse_response`` 之后修改 ``ProviderResponse``。"""

    def __call__(
        self,
        ctx: HookContext,
        response: ProviderResponse,
    ) -> ProviderResponse | Awaitable[ProviderResponse]:
        ...


# ---------------------------------------------------------------------------
# 流式侧：StreamTransformer
# ---------------------------------------------------------------------------


@runtime_checkable
class StreamTransformer(Protocol):
    """流式场景下，对每个 :class:`StreamEvent` 进行改写或过滤。

    - 返回新事件：替换原事件继续下游。
    - 返回 ``None``：丢弃该事件（例如插件判断为"内部推理块"不希望透传给调用方）。
    - 可返回 awaitable。
    """

    def __call__(
        self,
        ctx: HookContext,
        event: "Any",  # StreamEvent（protocols.py 定义，避免循环导入在此用 Any）
    ) -> "Any | None | Awaitable[Any | None]":
        ...


# ---------------------------------------------------------------------------
# 匹配器（Matcher）
# ---------------------------------------------------------------------------

Matcher = Callable[[HookContext], bool]


def match_any() -> Matcher:
    """匹配所有请求。"""
    return lambda _ctx: True


def match_provider(*providers: str) -> Matcher:
    """按 ``ModelConfig.provider`` 精确匹配。"""
    allowed = {p.lower() for p in providers}
    return lambda ctx: ctx.provider.lower() in allowed


def match_api_type(*api_types: str) -> Matcher:
    """按 ``ModelConfig.api_type`` 精确匹配。"""
    allowed = set(api_types)
    return lambda ctx: ctx.api_type in allowed


def match_model_prefix(*prefixes: str) -> Matcher:
    """按模型 ID 或 resolved_model_name 的前缀匹配。"""
    prefixes_lower = tuple(p.lower() for p in prefixes)
    return lambda ctx: (
        ctx.model_id.lower().startswith(prefixes_lower)
        or ctx.resolved_model_name.lower().startswith(prefixes_lower)
    )


# ---------------------------------------------------------------------------
# Registry（注册表）
# ---------------------------------------------------------------------------

H = TypeVar("H")


@dataclass(order=True)
class _HookEntry(Generic[H]):
    priority: int
    # 稳定排序 tiebreaker
    sequence: int
    hook: H = field(compare=False)
    matcher: Matcher = field(compare=False)
    name: str = field(compare=False, default="")


class _HookRegistry(Generic[H]):
    """通用 hook 注册表。按优先级（数值越小越先执行）排序。"""

    def __init__(self) -> None:
        self._entries: list[_HookEntry[H]] = []
        self._counter = 0

    def register(
        self,
        hook: H,
        matcher: Matcher | None = None,
        *,
        priority: int = 100,
        name: str = "",
    ) -> Callable[[], None]:
        """注册一个钩子。返回可用于取消注册的 ``unregister`` 函数。"""
        self._counter += 1
        entry = _HookEntry[H](
            priority=priority,
            sequence=self._counter,
            hook=hook,
            matcher=matcher or match_any(),
            name=name or getattr(hook, "__name__", repr(hook)),
        )
        self._entries.append(entry)
        self._entries.sort()

        def _unregister() -> None:
            try:
                self._entries.remove(entry)
            except ValueError:
                pass

        return _unregister

    def iter_matching(self, ctx: HookContext) -> list[_HookEntry[H]]:
        return [e for e in self._entries if e.matcher(ctx)]

    def list_all(self) -> list[_HookEntry[H]]:
        return list(self._entries)

    def clear(self) -> None:
        """清空所有注册。通常只在测试中使用。"""
        self._entries.clear()


# ---------------------------------------------------------------------------
# 模块级单例 + 公共 API
# ---------------------------------------------------------------------------

_request_interceptors: _HookRegistry[RequestInterceptor] = _HookRegistry()
_response_transformers: _HookRegistry[ResponseTransformer] = _HookRegistry()
_stream_transformers: _HookRegistry[StreamTransformer] = _HookRegistry()


def register_request_interceptor(
    hook: RequestInterceptor,
    matcher: Matcher | None = None,
    *,
    priority: int = 100,
    name: str = "",
) -> Callable[[], None]:
    """注册 RequestInterceptor。返回取消注册的函数。"""
    return _request_interceptors.register(hook, matcher, priority=priority, name=name)


def register_response_transformer(
    hook: ResponseTransformer,
    matcher: Matcher | None = None,
    *,
    priority: int = 100,
    name: str = "",
) -> Callable[[], None]:
    """注册 ResponseTransformer。返回取消注册的函数。"""
    return _response_transformers.register(hook, matcher, priority=priority, name=name)


def get_request_interceptors() -> _HookRegistry[RequestInterceptor]:
    return _request_interceptors


def get_response_transformers() -> _HookRegistry[ResponseTransformer]:
    return _response_transformers


def register_stream_transformer(
    hook: StreamTransformer,
    matcher: Matcher | None = None,
    *,
    priority: int = 100,
    name: str = "",
) -> Callable[[], None]:
    """注册 StreamTransformer。返回取消注册的函数。"""
    return _stream_transformers.register(hook, matcher, priority=priority, name=name)


def get_stream_transformers() -> _HookRegistry[StreamTransformer]:
    return _stream_transformers


def clear_all_hooks() -> None:
    """清空所有已注册钩子（测试辅助）。"""
    _request_interceptors.clear()
    _response_transformers.clear()
    _stream_transformers.clear()


# ---------------------------------------------------------------------------
# Pipeline 执行器
# ---------------------------------------------------------------------------

async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


async def run_request_interceptors(
    ctx: HookContext,
    request: RequestPayload,
) -> RequestPayload:
    """按优先级执行所有匹配的 RequestInterceptor。"""
    for entry in _request_interceptors.iter_matching(ctx):
        request = await _maybe_await(entry.hook(ctx, request))
        if request is None:
            raise RuntimeError(
                f"RequestInterceptor {entry.name!r} returned None; must return RequestPayload"
            )
    return request


async def run_response_transformers(
    ctx: HookContext,
    response: ProviderResponse,
) -> ProviderResponse:
    """按优先级执行所有匹配的 ResponseTransformer。"""
    for entry in _response_transformers.iter_matching(ctx):
        response = await _maybe_await(entry.hook(ctx, response))
        if response is None:
            raise RuntimeError(
                f"ResponseTransformer {entry.name!r} returned None; must return ProviderResponse"
            )
    return response


async def run_stream_transformers(ctx: HookContext, event: Any) -> Any | None:
    """按优先级执行所有匹配的 StreamTransformer。

    任一钩子返回 ``None`` 即中断 pipeline，向调用方表示"该事件应被丢弃"。
    与请求/响应钩子不同，流式钩子允许返回 ``None``（这是语义上的合法值）。
    """
    for entry in _stream_transformers.iter_matching(ctx):
        event = await _maybe_await(entry.hook(ctx, event))
        if event is None:
            return None
    return event
