"""
测试 Todo Continuation Enforcer 合并后的功能
"""

import asyncio
import tempfile
import pytest
from pathlib import Path

from pyagentforge.tools.builtin.todo import (
    TodoWriteTool,
    TodoReadTool,
    TodoStateManager,
    TodoEnforcerConfig,
    TodoItem,
    TodoStatus,
)


class TestTodoStateManager:
    """测试 TodoStateManager 类"""

    def test_default_config(self):
        """测试默认配置"""
        sm = TodoStateManager()
        assert sm.config.enabled is True
        assert sm.config.countdown_seconds == 5
        assert sm.config.max_recovery_attempts == 3
        assert sm.config.auto_continue is True

    def test_custom_config(self):
        """测试自定义配置"""
        config = TodoEnforcerConfig(
            enabled=False,
            countdown_seconds=10,
            max_recovery_attempts=5,
        )
        sm = TodoStateManager(config=config)
        assert sm.config.enabled is False
        assert sm.config.countdown_seconds == 10
        assert sm.config.max_recovery_attempts == 5

    def test_should_skip_agent(self):
        """测试跳过特定 Agent"""
        sm = TodoStateManager()

        # 默认跳过列表
        assert sm.should_skip_agent("explore") is True
        assert sm.should_skip_agent("librarian") is True
        assert sm.should_skip_agent("oracle") is True

        # 不在跳过列表
        assert sm.should_skip_agent("test_agent") is False

    def test_has_pending_todos(self):
        """测试检测未完成 Todo"""
        sm = TodoStateManager()

        # 空 Todo
        assert sm.has_pending_todos({}) is False

        # 有 pending 状态
        todos = {
            1: TodoItem(id=1, content="Task 1", status="pending"),
        }
        assert sm.has_pending_todos(todos) is True

        # 有 in_progress 状态
        todos = {
            1: TodoItem(id=1, content="Task 1", status="in_progress"),
        }
        assert sm.has_pending_todos(todos) is True

        # 只有 completed 状态
        todos = {
            1: TodoItem(id=1, content="Task 1", status="completed"),
        }
        assert sm.has_pending_todos(todos) is False

    def test_get_pending_todos(self):
        """测试获取未完成 Todo 列表"""
        sm = TodoStateManager()

        todos = {
            1: TodoItem(id=1, content="Task 1", status="pending"),
            2: TodoItem(id=2, content="Task 2", status="in_progress"),
            3: TodoItem(id=3, content="Task 3", status="completed"),
        }

        pending = sm.get_pending_todos(todos)
        assert len(pending) == 2
        assert all(t.status in ["pending", "in_progress"] for t in pending)

    def test_get_status_summary(self):
        """测试获取状态摘要"""
        sm = TodoStateManager()

        todos = {
            1: TodoItem(id=1, content="Task 1", status="pending"),
            2: TodoItem(id=2, content="Task 2", status="in_progress"),
            3: TodoItem(id=3, content="Task 3", status="completed"),
        }

        summary = sm.get_status_summary(todos)
        assert summary["total"] == 3
        assert summary["pending"] == 2
        assert summary["completed"] == 1
        assert summary["is_recovering"] is False
        assert summary["recovery_count"] == 0

    def test_generate_continuation_prompt(self):
        """测试生成续接消息"""
        sm = TodoStateManager()

        pending_todos = [
            TodoItem(id=1, content="Task 1", status="pending"),
            TodoItem(id=2, content="Task 2", status="in_progress"),
        ]

        prompt = sm.generate_continuation_prompt(pending_todos)
        assert "[Task Continuation]" in prompt
        assert "2 incomplete task(s)" in prompt
        assert "Task 1" in prompt
        assert "Task 2" in prompt

    def test_can_recover(self):
        """测试是否可以恢复"""
        config = TodoEnforcerConfig(max_recovery_attempts=2)
        sm = TodoStateManager(config=config)

        assert sm.can_recover() is True

        sm.mark_recovering()
        sm.mark_recovery_complete()
        assert sm.can_recover() is True

        sm.mark_recovering()
        sm.mark_recovery_complete()
        assert sm.can_recover() is False  # 达到最大次数


class TestTodoWriteTool:
    """测试 TodoWriteTool 类"""

    def test_create_tool(self):
        """测试创建工具"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            tool = TodoWriteTool(storage_path=storage_path)
            assert tool is not None

    def test_get_state_manager(self):
        """测试获取状态管理器"""
        tool = TodoWriteTool()
        sm = tool.get_state_manager()
        assert isinstance(sm, TodoStateManager)

    @pytest.mark.asyncio
    async def test_execute_with_todos(self):
        """测试执行添加 Todo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            tool = TodoWriteTool(storage_path=storage_path)

            result = await tool.execute([
                {"id": 1, "content": "Task 1", "status": "pending"},
                {"id": 2, "content": "Task 2", "status": "in_progress", "priority": "high"},
            ])

            assert "Task 1" in result
            assert "Task 2" in result
            assert tool.has_pending_todos() is True

    def test_on_agent_stop(self):
        """测试 Agent 停止时的处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            config = TodoEnforcerConfig(enabled=True, auto_continue=False)
            tool = TodoWriteTool(storage_path=storage_path, enforcer_config=config)

            # 无 Todo
            assert tool.on_agent_stop("test_agent") is None

    @pytest.mark.asyncio
    async def test_on_agent_stop_with_pending(self):
        """测试 Agent 停止时有未完成任务"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            config = TodoEnforcerConfig(enabled=True, auto_continue=False)
            tool = TodoWriteTool(storage_path=storage_path, enforcer_config=config)

            # 添加未完成的 Todo
            await tool.execute([
                {"id": 1, "content": "Task 1", "status": "pending"},
            ])

            # 检查是否生成续接消息
            continuation = tool.on_agent_stop("test_agent")
            assert continuation is not None
            assert "[Task Continuation]" in continuation

    @pytest.mark.asyncio
    async def test_skip_agent(self):
        """测试跳过特定 Agent"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            config = TodoEnforcerConfig(enabled=True)
            tool = TodoWriteTool(storage_path=storage_path, enforcer_config=config)

            # 添加未完成的 Todo
            await tool.execute([
                {"id": 1, "content": "Task 1", "status": "pending"},
            ])

            # 跳过的 Agent
            assert tool.on_agent_stop("explore") is None
            assert tool.on_agent_stop("librarian") is None


class TestTodoReadTool:
    """测试 TodoReadTool 类"""

    @pytest.mark.asyncio
    async def test_read_todos(self):
        """测试读取 Todo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            write_tool = TodoWriteTool(storage_path=storage_path)
            read_tool = TodoReadTool(todo_write_tool=write_tool)

            # 添加 Todo
            await write_tool.execute([
                {"id": 1, "content": "Task 1", "status": "pending"},
            ])

            # 读取 Todo
            result = await read_tool.execute()
            assert "Task 1" in result


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "todos.json"
            config = TodoEnforcerConfig(
                enabled=True,
                auto_continue=False,
                max_recovery_attempts=2,
            )
            tool = TodoWriteTool(storage_path=storage_path, enforcer_config=config)

            # 1. 添加 Todo
            await tool.execute([
                {"id": 1, "content": "Plan", "status": "completed"},
                {"id": 2, "content": "Develop", "status": "in_progress"},
                {"id": 3, "content": "Test", "status": "pending"},
            ])

            # 2. 检查状态
            assert tool.has_pending_todos() is True
            pending = tool.get_pending_todos()
            assert len(pending) == 2

            summary = tool.get_status_summary()
            assert summary["total"] == 3
            assert summary["pending"] == 2
            assert summary["completed"] == 1

            # 3. 模拟 Agent 停止
            continuation = tool.on_agent_stop("developer")
            assert continuation is not None
            assert "Develop" in continuation
            assert "Test" in continuation

            # 4. 标记恢复完成
            tool.mark_recovery_complete()
            assert tool.is_recovering() is False

            # 5. 完成所有任务
            await tool.execute([
                {"id": 2, "content": "Develop", "status": "completed"},
                {"id": 3, "content": "Test", "status": "completed"},
            ])

            # 6. 检查无未完成
            assert tool.has_pending_todos() is False
            continuation = tool.on_agent_stop("developer")
            assert continuation is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
