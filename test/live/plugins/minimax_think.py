"""
MiniMax ``<think>...</think>`` 剥离参考插件（同步 + 流式）。

背景：部分 OpenAI-兼容厂商（例如 MiniMax-M2）会在 assistant 消息的 ``content``
字段直接拼接推理段，用 ``<think>...</think>`` 包裹。对纯调用方来说这是噪声，
应当被剥离；但对调试/可观测性而言又不能完全丢弃——框架已在 ``ProviderResponse``
新增 ``reasoning`` 字段（P1a 之一），本插件会把剥离的文本回填到该字段。

Kernel 不感知任何厂商，此插件位于 ``test/live/plugins/``，仅用于活体测试与示例。
需要使用时显式调用 :func:`install`（返回卸载回调）。

实现要点：
- 匹配器：按 ``model_config.provider == "minimax"`` 精确过滤，避免误伤其它厂商。
- 同步：正则一次性剥离全部 ``<think>...</think>`` 段，塞进 ``reasoning``。
- 流式：小缓冲区 + 状态机逐字符消费，跨 chunk 拆分亦正确处理；状态按
  ``id(HookContext)`` 维护（kernel 对每次调用生成新 ``HookContext``），
  ``done`` 事件上清理以防内存泄漏。
"""

from __future__ import annotations

import re
from typing import Callable

from pyagentforge import (
    HookContext,
    StreamEvent,
    match_provider,
    register_response_transformer,
    register_stream_transformer,
)
from pyagentforge.kernel.message import ProviderResponse, TextBlock

_THINK_TAG_OPEN = "<think>"
_THINK_TAG_CLOSE = "</think>"
_THINK_BLOCK_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 同步响应：ResponseTransformer
# ---------------------------------------------------------------------------


def _strip_think_sync(_ctx: HookContext, response: ProviderResponse) -> ProviderResponse:
    """从 ProviderResponse 每个 TextBlock 剥离 ``<think>...</think>``，并回填 reasoning。"""
    reasoning_parts: list[str] = []
    new_content: list = []

    for block in response.content:
        if isinstance(block, TextBlock):
            text = block.text or ""
            found = _THINK_BLOCK_RE.findall(text)
            if found:
                reasoning_parts.extend(s.strip() for s in found if s.strip())
                stripped = _THINK_BLOCK_RE.sub("", text).strip()
                if stripped:
                    new_content.append(TextBlock(text=stripped))
            else:
                new_content.append(block)
        else:
            new_content.append(block)

    if not reasoning_parts:
        return response

    reasoning_text = "\n\n".join(reasoning_parts)
    existing = response.reasoning or ""
    merged_reasoning = f"{existing}\n\n{reasoning_text}".strip() if existing else reasoning_text

    return response.model_copy(update={"content": new_content, "reasoning": merged_reasoning})


# ---------------------------------------------------------------------------
# 流式：StreamTransformer（带 per-call 状态机）
# ---------------------------------------------------------------------------


class _StreamState:
    """单次 stream 调用内的 ``<think>`` 状态机。

    工作方式：
    - 每次收到 ``text_delta``，把增量 append 到 pending 缓冲。
    - 扫描缓冲：若未处于 think 段，尽量吐出"确定不在 tag 内的前缀"；剩余可能是
      ``<think`` 的前缀片段，留待下一 chunk。
    - 若处于 think 段，缓冲全部丢弃并塞入 reasoning，直到遇到 ``</think>``。
    """

    __slots__ = ("pending", "in_think", "reasoning")

    def __init__(self) -> None:
        self.pending: str = ""
        self.in_think: bool = False
        self.reasoning: list[str] = []

    def feed(self, chunk: str) -> str:
        """喂入一段增量文本，返回对外应当 yield 的可见文本（可能为空字符串）。"""
        self.pending += chunk
        out_parts: list[str] = []

        while self.pending:
            if self.in_think:
                idx = self.pending.find(_THINK_TAG_CLOSE)
                if idx == -1:
                    # 整块仍在 think 内；保留尾部 len(close_tag)-1 个字符以防 tag 跨 chunk
                    keep = len(_THINK_TAG_CLOSE) - 1
                    if len(self.pending) > keep:
                        self.reasoning.append(self.pending[:-keep])
                        self.pending = self.pending[-keep:]
                    return "".join(out_parts)
                # 找到闭合标签
                self.reasoning.append(self.pending[:idx])
                self.pending = self.pending[idx + len(_THINK_TAG_CLOSE) :]
                self.in_think = False
            else:
                idx = self.pending.find(_THINK_TAG_OPEN)
                if idx == -1:
                    # 整块都在可见区；但 pending 末尾可能是 "<", "<t", ... 的 tag 前缀
                    tail = _tag_prefix_len(self.pending, _THINK_TAG_OPEN)
                    if tail:
                        out_parts.append(self.pending[:-tail])
                        self.pending = self.pending[-tail:]
                    else:
                        out_parts.append(self.pending)
                        self.pending = ""
                    return "".join(out_parts)
                # 发现 <think>
                out_parts.append(self.pending[:idx])
                self.pending = self.pending[idx + len(_THINK_TAG_OPEN) :]
                self.in_think = True

        return "".join(out_parts)

    def collected_reasoning(self) -> str:
        return "".join(self.reasoning).strip()


def _tag_prefix_len(text: str, tag: str) -> int:
    """若 text 末尾是 tag 的前缀（例如 ``'<thi'`` 对 ``'<think>'``），返回该前缀长度，否则 0。"""
    max_check = min(len(text), len(tag) - 1)
    for length in range(max_check, 0, -1):
        if tag.startswith(text[-length:]):
            return length
    return 0


class _MinimaxThinkStripper:
    def __init__(self) -> None:
        self._states: dict[int, _StreamState] = {}

    def _get_state(self, ctx: HookContext) -> _StreamState:
        key = id(ctx)
        state = self._states.get(key)
        if state is None:
            state = _StreamState()
            self._states[key] = state
        return state

    def __call__(self, ctx: HookContext, event: StreamEvent) -> StreamEvent | None:
        state = self._get_state(ctx)

        if event.type == "text_delta":
            visible = state.feed(event.text or "")
            if not visible:
                return None
            return StreamEvent(type="text_delta", text=visible, raw=event.raw)

        if event.type == "done":
            # 清理状态，避免累积
            self._states.pop(id(ctx), None)
            return event

        return event


# ---------------------------------------------------------------------------
# 对外安装接口
# ---------------------------------------------------------------------------


def install(provider: str = "minimax") -> Callable[[], None]:
    """挂载插件。返回卸载回调，便于测试 teardown。"""
    matcher = match_provider(provider)

    unregister_resp = register_response_transformer(
        _strip_think_sync,
        matcher,
        priority=50,
        name=f"minimax_think.sync[{provider}]",
    )
    unregister_stream = register_stream_transformer(
        _MinimaxThinkStripper(),
        matcher,
        priority=50,
        name=f"minimax_think.stream[{provider}]",
    )

    def _uninstall() -> None:
        unregister_resp()
        unregister_stream()

    return _uninstall


__all__ = ["install"]
