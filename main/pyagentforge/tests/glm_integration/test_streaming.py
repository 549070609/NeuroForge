"""
流式响应测试

测试 WebSocket 和流式通信功能
"""

import pytest
import asyncio
import websockets
import json
from pathlib import Path

from conftest import check_api_key


# ============ 流式文本测试 ============

@pytest.mark.streaming
@pytest.mark.asyncio
class TestStreamingText:
    """流式文本测试"""

    async def test_stream_basic_response(self, agent_engine):
        """测试流式基础响应"""
        check_api_key()

        chunks = []
        async for event in agent_engine.run_stream("请讲一个简短的故事"):
            chunks.append(event)

        assert len(chunks) > 0

        # 检查是否有最终响应
        final_events = [e for e in chunks if isinstance(e, dict) and e.get("type") == "final"]
        if final_events:
            assert final_events[0].get("content") is not None

    async def test_stream_with_tool_use(self, agent_engine, temp_dir):
        """测试流式工具调用"""
        check_api_key()

        test_file = temp_dir / "stream_test.txt"

        events = []
        async for event in agent_engine.run_stream(
            f"请将 'Streaming Test' 写入文件 {test_file}"
        ):
            events.append(event)

        assert len(events) > 0

        # 验证文件已创建
        assert test_file.exists()


# ============ WebSocket 测试 (需要服务器) ============

@pytest.mark.streaming
@pytest.mark.asyncio
@pytest.mark.skip(reason="需要启动后端服务器")
class TestWebSocket:
    """WebSocket 测试"""

    async def test_websocket_connection(self):
        """测试 WebSocket 连接"""
        pytest.skip("需要后端服务器")
        uri = "ws://localhost:8100/ws/test-session-1"

        try:
            async with websockets.connect(uri) as websocket:
                # 发送消息
                await websocket.send(json.dumps({
                    "message": "你好"
                }))

                # 接收响应
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=30
                )

                data = json.loads(response)
                assert data is not None

        except Exception as e:
            pytest.skip(f"WebSocket connection failed: {e}")

    async def test_websocket_multi_turn(self):
        """测试 WebSocket 多轮对话"""
        uri = "ws://localhost:8100/ws/test-session-2"

        try:
            async with websockets.connect(uri) as websocket:
                messages = [
                    "请记住数字 123",
                    "我刚才让你记住的数字是什么？"
                ]

                for msg in messages:
                    await websocket.send(json.dumps({"message": msg}))

                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30
                    )

                    data = json.loads(response)
                    assert data is not None

        except Exception as e:
            pytest.skip(f"WebSocket connection failed: {e}")


# ============ HTTP API 测试 (需要服务器) ============

@pytest.mark.streaming
@pytest.mark.asyncio
@pytest.mark.skip(reason="需要启动后端服务器")
class TestHTTPAPI:
    """HTTP API 测试"""

    async def test_create_session(self):
        """测试创建会话"""
        pytest.skip("需要后端服务器")
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8100/api/sessions",
                    json={
                        "system_prompt": "你是一个测试助手"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert "session_id" in data

        except Exception as e:
            pytest.skip(f"HTTP request failed: {e}")

    async def test_send_message(self):
        """测试发送消息"""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                # 创建会话
                create_resp = await client.post(
                    "http://localhost:8100/api/sessions",
                    json={}
                )
                session_id = create_resp.json()["session_id"]

                # 发送消息
                msg_resp = await client.post(
                    f"http://localhost:8100/api/sessions/{session_id}/messages",
                    json={"message": "你好"}
                )

                assert msg_resp.status_code == 200
                data = msg_resp.json()
                assert "content" in data

        except Exception as e:
            pytest.skip(f"HTTP request failed: {e}")


# ============ pytest 配置 ============

def pytest_addoption(parser):
    parser.addoption(
        "--run-server-tests",
        action="store_true",
        default=False,
        help="运行需要后端服务器的测试"
    )


# ============ 导入 ============

from pathlib import Path
