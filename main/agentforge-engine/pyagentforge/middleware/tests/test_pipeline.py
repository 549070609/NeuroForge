"""
Middleware Pipeline 单元测试
"""

import pytest

from pyagentforge.middleware.base import BaseMiddleware, MiddlewareContext, NextMiddleware
from pyagentforge.middleware.pipeline import MiddlewarePipeline


class TestMiddlewareContext:
    """测试 MiddlewareContext"""

    def test_create_context(self):
        """创建上下文"""
        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[{"role": "user", "content": "Hello"}],
            tools=[{"name": "test_tool"}],
            config={"timeout": 30}
        )
        assert ctx.session_key == "test:123"
        assert len(ctx.messages) == 1
        assert len(ctx.tools) == 1
        assert ctx.config["timeout"] == 30

    def test_default_values(self):
        """默认值"""
        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )
        assert ctx.config == {}
        assert ctx.metadata == {}

    def test_with_metadata(self):
        """添加元数据"""
        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[],
            metadata={"existing": "value"}
        )
        new_ctx = ctx.with_metadata(new_key="new_value")
        assert new_ctx.metadata["existing"] == "value"
        assert new_ctx.metadata["new_key"] == "new_value"
        # 原始上下文不变
        assert "new_key" not in ctx.metadata


class FirstMiddleware(BaseMiddleware):
    """测试中间件 - 最先执行"""
    name = "first"
    priority = 10

    def __init__(self):
        self.called = False
        self.call_order = []

    async def process(self, ctx: MiddlewareContext, next_middleware: NextMiddleware):
        self.called = True
        ctx.metadata["first_called"] = True
        result = await next_middleware(ctx)
        ctx.metadata["first_after"] = True
        return result


class SecondMiddleware(BaseMiddleware):
    """测试中间件 - 第二执行"""
    name = "second"
    priority = 20

    def __init__(self):
        self.called = False

    async def process(self, ctx: MiddlewareContext, next_middleware: NextMiddleware):
        self.called = True
        ctx.metadata["second_called"] = True
        return await next_middleware(ctx)


class ThirdMiddleware(BaseMiddleware):
    """测试中间件 - 最后执行"""
    name = "third"
    priority = 30

    def __init__(self):
        self.called = False

    async def process(self, ctx: MiddlewareContext, next_middleware: NextMiddleware):
        self.called = True
        ctx.metadata["third_called"] = True
        return await next_middleware(ctx)


class TestBaseMiddleware:
    """测试 BaseMiddleware"""

    def test_middleware_repr(self):
        """中间件字符串表示"""
        m = FirstMiddleware()
        assert "FirstMiddleware" in repr(m)
        assert "first" in repr(m)
        assert "10" in repr(m)

    def test_cannot_instantiate_abc(self):
        """不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseMiddleware()  # type: ignore


class TestMiddlewarePipeline:
    """测试 MiddlewarePipeline"""

    def test_empty_pipeline(self):
        """空管道"""
        pipeline = MiddlewarePipeline()
        assert len(pipeline) == 0

    @pytest.mark.asyncio
    async def test_empty_pipeline_executes_handler(self):
        """空管道直接执行处理器"""
        pipeline = MiddlewarePipeline()
        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c: MiddlewareContext):
            return "result"

        result = await pipeline.execute(ctx, handler)
        assert result == "result"

    def test_add_middleware(self):
        """添加中间件"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware()).add(SecondMiddleware())
        assert len(pipeline) == 2

    def test_add_sorts_by_priority(self):
        """按优先级排序"""
        pipeline = MiddlewarePipeline()
        # 添加顺序: third, first, second
        pipeline.add(ThirdMiddleware()).add(FirstMiddleware()).add(SecondMiddleware())

        middlewares = pipeline.get_middlewares()
        assert middlewares[0].name == "first"
        assert middlewares[1].name == "second"
        assert middlewares[2].name == "third"

    def test_remove_middleware(self):
        """移除中间件"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware()).add(SecondMiddleware())
        assert len(pipeline) == 2

        removed = pipeline.remove("second")
        assert removed is True
        assert len(pipeline) == 1

        removed = pipeline.remove("nonexistent")
        assert removed is False

    def test_clear_middlewares(self):
        """清除所有中间件"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware()).add(SecondMiddleware())
        pipeline.clear()
        assert len(pipeline) == 0

    @pytest.mark.asyncio
    async def test_execution_order(self):
        """执行顺序"""
        pipeline = MiddlewarePipeline()
        first = FirstMiddleware()
        second = SecondMiddleware()
        third = ThirdMiddleware()
        pipeline.add(third).add(first).add(second)  # 添加顺序不同

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c: MiddlewareContext):
            return "done"

        await pipeline.execute(ctx, handler)

        # 所有中间件都被调用
        assert first.called
        assert second.called
        assert third.called

    @pytest.mark.asyncio
    async def test_middleware_can_modify_context(self):
        """中间件可以修改上下文"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c: MiddlewareContext):
            return "done"

        await pipeline.execute(ctx, handler)

        assert ctx.metadata.get("first_called") is True
        assert ctx.metadata.get("first_after") is True

    @pytest.mark.asyncio
    async def test_middleware_can_short_circuit(self):
        """中间件可以短路"""
        class ShortCircuitMiddleware(BaseMiddleware):
            name = "short_circuit"
            priority = 5

            async def process(self, ctx: MiddlewareContext, next_middleware: NextMiddleware):
                # 不调用 next_middleware，直接返回
                return "short_circuited"

        pipeline = MiddlewarePipeline()
        pipeline.add(ShortCircuitMiddleware()).add(FirstMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c: MiddlewareContext):
            return "handler_result"

        result = await pipeline.execute(ctx, handler)
        assert result == "short_circuited"

    @pytest.mark.asyncio
    async def test_final_handler_receives_modified_context(self):
        """最终处理器接收修改后的上下文"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        received_metadata = {}

        async def handler(c: MiddlewareContext):
            received_metadata.update(c.metadata)
            return "done"

        await pipeline.execute(ctx, handler)

        assert received_metadata.get("first_called") is True

    def test_pipeline_repr(self):
        """管道字符串表示"""
        pipeline = MiddlewarePipeline()
        pipeline.add(FirstMiddleware()).add(SecondMiddleware())
        repr_str = repr(pipeline)
        assert "MiddlewarePipeline" in repr_str
        assert "first" in repr_str
        assert "second" in repr_str
