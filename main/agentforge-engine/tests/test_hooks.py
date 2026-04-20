"""
Kernel 扩展点测试：RequestInterceptor / ResponseTransformer / 协议适配器 registry

验证框架的插件扩展能力，不涉及任何具体厂商实现。
"""

from __future__ import annotations

from typing import Any

import pytest

from pyagentforge import (
    BaseProtocolAdapter,
    HookContext,
    ModelConfig,
    ProtocolAdapterRegistry,
    RequestPayload,
    clear_all_hooks,
    get_protocol_adapter,
    match_any,
    match_api_type,
    match_model_prefix,
    match_provider,
    register_protocol_adapter,
    register_request_interceptor,
    register_response_transformer,
)
from pyagentforge.kernel.hooks import (
    get_request_interceptors,
    get_response_transformers,
    run_request_interceptors,
    run_response_transformers,
)
from pyagentforge.kernel.message import ProviderResponse, TextBlock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_hooks():
    """每个用例开始前后都确保 hook 注册表为空，避免串扰。"""
    clear_all_hooks()
    yield
    clear_all_hooks()


@pytest.fixture
def model_config() -> ModelConfig:
    return ModelConfig(
        id="dummy-model",
        name="Dummy Model",
        provider="dummy-vendor",
        api_type="openai-completions",
        model_name="dummy-model",
        base_url="https://example.invalid/v1",
    )


@pytest.fixture
def hook_ctx(model_config: ModelConfig) -> HookContext:
    return HookContext(model_id=model_config.id, model_config=model_config)


@pytest.fixture
def sample_response() -> ProviderResponse:
    return ProviderResponse(
        content=[TextBlock(text="hello")],
        stop_reason="end_turn",
        usage={"input_tokens": 10, "output_tokens": 5},
    )


# ---------------------------------------------------------------------------
# ProviderResponse 新字段
# ---------------------------------------------------------------------------


class TestProviderResponseExtensions:
    def test_reasoning_default_none(self, sample_response):
        assert sample_response.reasoning is None

    def test_extra_default_empty(self, sample_response):
        assert sample_response.extra == {}

    def test_fields_round_trip_via_model_copy(self, sample_response):
        updated = sample_response.model_copy(
            update={"reasoning": "chain of thought", "extra": {"vendor_tag": "x"}}
        )
        assert updated.reasoning == "chain of thought"
        assert updated.extra == {"vendor_tag": "x"}
        # 原对象未被污染
        assert sample_response.reasoning is None


# ---------------------------------------------------------------------------
# Matchers
# ---------------------------------------------------------------------------


class TestMatchers:
    def test_match_any(self, hook_ctx):
        assert match_any()(hook_ctx) is True

    def test_match_provider_hit(self, hook_ctx):
        assert match_provider("dummy-vendor")(hook_ctx) is True

    def test_match_provider_case_insensitive(self, hook_ctx):
        assert match_provider("DUMMY-VENDOR")(hook_ctx) is True

    def test_match_provider_miss(self, hook_ctx):
        assert match_provider("other")(hook_ctx) is False

    def test_match_api_type(self, hook_ctx):
        assert match_api_type("openai-completions")(hook_ctx) is True
        assert match_api_type("anthropic-messages")(hook_ctx) is False

    def test_match_model_prefix(self, hook_ctx):
        assert match_model_prefix("dummy")(hook_ctx) is True
        assert match_model_prefix("DUMMY")(hook_ctx) is True
        assert match_model_prefix("other-")(hook_ctx) is False


# ---------------------------------------------------------------------------
# ResponseTransformer
# ---------------------------------------------------------------------------


class TestResponseTransformer:
    @pytest.mark.asyncio
    async def test_sync_transformer_runs(self, hook_ctx, sample_response):
        def transformer(ctx: HookContext, resp: ProviderResponse) -> ProviderResponse:
            return resp.model_copy(update={"reasoning": "set-by-hook"})

        register_response_transformer(transformer)
        result = await run_response_transformers(hook_ctx, sample_response)

        assert result.reasoning == "set-by-hook"

    @pytest.mark.asyncio
    async def test_async_transformer_runs(self, hook_ctx, sample_response):
        async def transformer(ctx: HookContext, resp: ProviderResponse) -> ProviderResponse:
            return resp.model_copy(update={"extra": {"flag": True}})

        register_response_transformer(transformer)
        result = await run_response_transformers(hook_ctx, sample_response)

        assert result.extra == {"flag": True}

    @pytest.mark.asyncio
    async def test_matcher_filters_out_non_matching(self, hook_ctx, sample_response):
        def transformer(ctx: HookContext, resp: ProviderResponse) -> ProviderResponse:
            return resp.model_copy(update={"reasoning": "should-not-appear"})

        register_response_transformer(transformer, match_provider("other-vendor"))
        result = await run_response_transformers(hook_ctx, sample_response)

        assert result.reasoning is None

    @pytest.mark.asyncio
    async def test_priority_order(self, hook_ctx, sample_response):
        call_order: list[str] = []

        def first(ctx, resp):
            call_order.append("first")
            return resp.model_copy(update={"reasoning": "first"})

        def second(ctx, resp):
            call_order.append("second")
            # 覆盖第一个
            return resp.model_copy(update={"reasoning": "second"})

        # priority 数值小的先执行
        register_response_transformer(second, priority=50)
        register_response_transformer(first, priority=10)

        result = await run_response_transformers(hook_ctx, sample_response)

        assert call_order == ["first", "second"]
        assert result.reasoning == "second"

    @pytest.mark.asyncio
    async def test_unregister(self, hook_ctx, sample_response):
        def transformer(ctx, resp):
            return resp.model_copy(update={"reasoning": "ran"})

        unreg = register_response_transformer(transformer)
        unreg()

        result = await run_response_transformers(hook_ctx, sample_response)
        assert result.reasoning is None

    @pytest.mark.asyncio
    async def test_none_return_raises(self, hook_ctx, sample_response):
        def bad_transformer(ctx, resp):  # 返回 None
            return None

        register_response_transformer(bad_transformer)
        with pytest.raises(RuntimeError, match="must return ProviderResponse"):
            await run_response_transformers(hook_ctx, sample_response)

    @pytest.mark.asyncio
    async def test_no_hooks_returns_unchanged(self, hook_ctx, sample_response):
        result = await run_response_transformers(hook_ctx, sample_response)
        assert result is sample_response


# ---------------------------------------------------------------------------
# RequestInterceptor
# ---------------------------------------------------------------------------


class TestRequestInterceptor:
    @pytest.fixture
    def request_payload(self) -> RequestPayload:
        return RequestPayload(
            url="https://example.invalid/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            payload={"model": "dummy-model", "messages": []},
        )

    @pytest.mark.asyncio
    async def test_can_modify_headers(self, hook_ctx, request_payload):
        def interceptor(ctx, req):
            req.headers["X-Plugin"] = "ok"
            return req

        register_request_interceptor(interceptor)
        result = await run_request_interceptors(hook_ctx, request_payload)
        assert result.headers["X-Plugin"] == "ok"

    @pytest.mark.asyncio
    async def test_can_modify_payload(self, hook_ctx, request_payload):
        def interceptor(ctx, req):
            req.payload["metadata"] = {"tenant": "t1"}
            return req

        register_request_interceptor(interceptor)
        result = await run_request_interceptors(hook_ctx, request_payload)
        assert result.payload["metadata"] == {"tenant": "t1"}

    @pytest.mark.asyncio
    async def test_matcher_filters(self, hook_ctx, request_payload):
        def interceptor(ctx, req):
            req.headers["X-Should-Not"] = "1"
            return req

        register_request_interceptor(interceptor, match_provider("other"))
        result = await run_request_interceptors(hook_ctx, request_payload)
        assert "X-Should-Not" not in result.headers

    @pytest.mark.asyncio
    async def test_chain_order(self, hook_ctx, request_payload):
        def add_a(ctx, req):
            req.headers["X-Order"] = req.headers.get("X-Order", "") + "A"
            return req

        def add_b(ctx, req):
            req.headers["X-Order"] = req.headers.get("X-Order", "") + "B"
            return req

        register_request_interceptor(add_a, priority=10)
        register_request_interceptor(add_b, priority=20)

        result = await run_request_interceptors(hook_ctx, request_payload)
        assert result.headers["X-Order"] == "AB"


# ---------------------------------------------------------------------------
# Protocol adapter registry
# ---------------------------------------------------------------------------


class _DummyAdapter(BaseProtocolAdapter):
    api_type = "dummy-protocol"
    endpoint = "/dummy"

    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        return {"model": config.resolved_model_name}

    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        return ProviderResponse(
            content=[TextBlock(text=str(response.get("text", "")))],
            stop_reason="end_turn",
        )


class TestProtocolAdapterRegistry:
    def test_builtin_adapters_present(self):
        assert get_protocol_adapter("openai-completions") is not None
        assert get_protocol_adapter("anthropic-messages") is not None
        assert get_protocol_adapter("openai-responses") is not None

    def test_register_and_retrieve(self):
        adapter = _DummyAdapter()
        try:
            register_protocol_adapter(adapter)
            assert get_protocol_adapter("dummy-protocol") is adapter
        finally:
            from pyagentforge.protocols import PROTOCOL_ADAPTERS

            PROTOCOL_ADAPTERS.unregister("dummy-protocol")

    def test_duplicate_registration_rejected(self):
        adapter = _DummyAdapter()
        register_protocol_adapter(adapter)
        try:
            with pytest.raises(ValueError, match="already registered"):
                register_protocol_adapter(_DummyAdapter())
        finally:
            from pyagentforge.protocols import PROTOCOL_ADAPTERS

            PROTOCOL_ADAPTERS.unregister("dummy-protocol")

    def test_override_allowed(self):
        first = _DummyAdapter()
        register_protocol_adapter(first)
        try:
            replacement = _DummyAdapter()
            register_protocol_adapter(replacement, override=True)
            assert get_protocol_adapter("dummy-protocol") is replacement
        finally:
            from pyagentforge.protocols import PROTOCOL_ADAPTERS

            PROTOCOL_ADAPTERS.unregister("dummy-protocol")

    def test_dict_like_backward_compat(self):
        """现存代码中 ``PROTOCOL_ADAPTERS.get(api_type)`` / ``in`` 仍能工作。"""
        from pyagentforge.protocols import PROTOCOL_ADAPTERS

        assert "openai-completions" in PROTOCOL_ADAPTERS
        assert PROTOCOL_ADAPTERS.get("openai-completions") is not None
        assert PROTOCOL_ADAPTERS.get("does-not-exist") is None
        # 迭代与 len
        assert len(list(PROTOCOL_ADAPTERS)) >= 3
        assert len(PROTOCOL_ADAPTERS) >= 3

    def test_adapter_without_api_type_rejected(self):
        class _BadAdapter(BaseProtocolAdapter):
            api_type = ""  # type: ignore[assignment]
            endpoint = "/x"

            def build_request(self, request_params, config):
                return {}

            def parse_response(self, response):
                return ProviderResponse(content=[], stop_reason="end_turn")

        with pytest.raises(ValueError, match="non-empty `api_type`"):
            register_protocol_adapter(_BadAdapter())


# ---------------------------------------------------------------------------
# 全局 registry 隔离
# ---------------------------------------------------------------------------


class TestRegistryIsolation:
    def test_clear_all_hooks_empties_both_registries(self, hook_ctx):
        register_request_interceptor(lambda c, r: r)
        register_response_transformer(lambda c, r: r)

        assert len(get_request_interceptors().list_all()) == 1
        assert len(get_response_transformers().list_all()) == 1

        clear_all_hooks()

        assert len(get_request_interceptors().list_all()) == 0
        assert len(get_response_transformers().list_all()) == 0
