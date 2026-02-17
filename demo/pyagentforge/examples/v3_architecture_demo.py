"""
PyAgentForge v3.0 架构功能示例

展示 v3.0 新架构的核心功能：
- Session Key 体系
- Channel 通道系统 (WebChat, Webhook)
- Automation 自动化
- Telemetry 遥测
- Middleware Pipeline

运行方式:
    python examples/v3_architecture_demo.py
"""

import asyncio
from datetime import datetime

# v3.0 新模块
from pyagentforge.foundation.session import SessionKey
from pyagentforge.foundation.config import resolve_env_vars
from pyagentforge.capabilities.channels.webchat import WebChatChannel
from pyagentforge.capabilities.channels.webhook import WebhookChannel
from pyagentforge.automation import AutomationManager, TriggerType
from pyagentforge.middleware.telemetry import TelemetryCollector


async def example_session_key():
    """示例 1: Session Key 体系"""
    print("\n" + "="*60)
    print("示例 1: Session Key 统一会话标识")
    print("="*60)

    # 1. 解析不同格式的 Session Key
    keys = [
        "telegram:-100123456",
        "discord:789012345",
        "webchat:session-abc123",
        "agent:main:subagent:task-456",
    ]

    print("\n解析 Session Keys:")
    for key_str in keys:
        key = SessionKey.parse(key_str)
        print(f"  {key_str}")
        print(f"    → channel: {key.channel}, conversation_id: {key.conversation_id}")
        if key.sub_key:
            print(f"    → sub_key: {key.sub_key}")
        print(f"    → is_subagent: {key.is_subagent}")

    # 2. 创建 Session Key
    print("\n创建 Session Key:")
    parent = SessionKey("telegram", "-100123456")
    child = parent.with_sub_key("task-789")

    print(f"  Parent: {parent}")
    print(f"  Child: {child}")
    print(f"  Child's parent: {child.parent_key}")

    # 3. 用作字典键
    print("\n用作字典键:")
    data = {}
    data[SessionKey("webchat", "session-1")] = "Session 1 data"
    data[SessionKey("webchat", "session-2")] = "Session 2 data"

    for key, value in data.items():
        print(f"  {key}: {value}")


async def example_env_parser():
    """示例 2: 环境变量解析"""
    print("\n" + "="*60)
    print("示例 2: 环境变量解析器")
    print("="*60)

    import os

    # 设置一些环境变量
    os.environ["APP_NAME"] = "PyAgentForge"
    os.environ["API_KEY"] = "secret123"

    # 1. 基本解析
    config = {
        "app_name": "${APP_NAME}",
        "api_key": "${API_KEY}",
        "debug": "${DEBUG:-false}",
        "timeout": "${TIMEOUT:-30}",
    }

    print("\n原始配置:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    print("\n解析后配置:")
    for key, value in config.items():
        resolved = resolve_env_vars(value)
        print(f"  {key}: {resolved}")

    # 2. 嵌套配置
    print("\n嵌套配置解析:")
    nested_config = {
        "database": {
            "host": "${DB_HOST:-localhost}",
            "port": "${DB_PORT:-5432}",
        },
        "features": {
            "enabled": ["${FEATURE_1:-auth}", "${FEATURE_2:-telemetry}"],
        }
    }

    print(f"  数据库主机: {resolve_env_vars(nested_config['database']['host'])}")
    print(f"  数据库端口: {resolve_env_vars(nested_config['database']['port'])}")


async def example_webchat_channel():
    """示例 3: WebChat 通道"""
    print("\n" + "="*60)
    print("示例 3: WebChat 通道")
    print("="*60)

    # 1. 创建通道
    channel = WebChatChannel({
        "max_sessions": 100,
        "session_timeout": 3600,
    })

    await channel.initialize()
    print(f"\n通道状态: {channel.status.value}")

    # 2. 创建会话
    session_id = channel.create_session()
    print(f"创建会话: {session_id}")

    # 3. 注册消息回调
    received_messages = []

    async def on_message(msg):
        received_messages.append(msg)
        print(f"\n收到消息:")
        print(f"  Session Key: {msg.session_key}")
        print(f"  Content: {msg.content}")
        print(f"  Sender: {msg.sender}")

    channel.on_message(on_message)

    # 4. 模拟接收消息
    await channel.receive_message(
        session_id=session_id,
        content="Hello from WebChat!",
        sender="user-123"
    )

    # 5. 获取通道信息
    info = await channel.get_channel_info()
    print(f"\n通道信息:")
    print(f"  活跃会话数: {info['active_sessions']}")
    print(f"  最大会话数: {info['max_sessions']}")

    await channel.stop()


async def example_webhook_channel():
    """示例 4: Webhook 通道"""
    print("\n" + "="*60)
    print("示例 4: Webhook 通道")
    print("="*60)

    # 1. 创建通道
    channel = WebhookChannel({
        "default_secret": "my_default_secret"
    })

    await channel.initialize()
    await channel.start()

    # 2. 注册 Webhook 处理器
    async def github_handler(payload, headers):
        event = headers.get("X-GitHub-Event", "unknown")
        print(f"\nGitHub 事件: {event}")
        print(f"Payload: {payload}")
        return {"status": "processed", "event": event}

    channel.register_handler(
        path="/github/webhook",
        handler=github_handler,
        secret="github_webhook_secret"
    )

    print(f"\n注册的 Webhook 路径: {list(channel._handlers.keys())}")

    # 3. 模拟处理 Webhook（带签名）
    import hmac
    import hashlib
    import json

    payload = {"action": "opened", "repo": {"name": "user/repo"}}

    # 生成签名
    signature = "sha256=" + hmac.new(
        b"github_webhook_secret",
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-GitHub-Event": "push",
        "User-Agent": "GitHub-Hookshot",
        "X-Hub-Signature-256": signature,
    }

    result = await channel.handle_webhook(
        path="/github/webhook",
        payload=payload,
        headers=headers
    )

    print(f"\n处理结果: {result}")

    # 4. 列出所有处理器
    handlers = channel.list_handlers()
    print(f"\n注册的处理器:")
    for handler_info in handlers:
        print(f"  {handler_info['path']}")
        print(f"    - 有密钥: {handler_info['has_secret']}")
        print(f"    - 自动创建会话: {handler_info['auto_create_session']}")

    await channel.stop()


async def example_automation():
    """示例 5: Automation 自动化"""
    print("\n" + "="*60)
    print("示例 5: Automation 自动化")
    print("="*60)

    # 1. 创建管理器
    manager = AutomationManager()

    # 2. 添加 Cron 任务
    task1 = manager.add_cron_task(
        task_id="daily_report",
        cron_expr="0 9 * * *",  # 每天早上9点
        action="Generate daily report",
        name="每日报告"
    )

    print(f"\n添加 Cron 任务:")
    print(f"  ID: {task1.id}")
    print(f"  名称: {task1.name}")
    print(f"  Cron: {task1.trigger_config['cron']}")
    print(f"  类型: {task1.trigger_type.value}")

    # 3. 添加 Webhook 任务（无签名验证）
    def webhook_action(payload, headers):
        print(f"Webhook 触发: {payload}")
        return {"processed": True}

    manager.add_webhook_handler(
        path="/api/trigger",
        handler=webhook_action
        # 不设置 secret，跳过签名验证
    )

    print(f"\n注册的 Webhook 路径: {list(manager._webhook_handlers.keys())}")

    # 4. 列出所有任务
    tasks = manager.list_tasks()
    print(f"\n所有任务 ({len(tasks)}):")
    for task in tasks:
        print(f"  - {task.id}: {task.name}")

    # 5. 模拟 Webhook 触发
    result = await manager.handle_webhook(
        path="/api/trigger",
        payload={"event": "test"},
        headers={}
    )
    print(f"\nWebhook 执行结果: {result}")


async def example_telemetry():
    """示例 6: Telemetry 遥测"""
    print("\n" + "="*60)
    print("示例 6: Telemetry 遥测")
    print("="*60)

    # 1. 创建收集器
    collector = TelemetryCollector()

    # 2. 追踪请求
    print("\n模拟请求追踪:")
    for i in range(10):
        latency = 100.0 + i * 10
        success = i % 5 != 0  # 20% 失败率

        collector.track_request(
            session_key=f"session_{i % 3}",
            latency_ms=latency,
            success=success
        )

        if success:
            collector.track_tokens(
                session_key=f"session_{i % 3}",
                input_tokens=100 + i * 5,
                output_tokens=50 + i * 3
            )

    # 3. 同步外部数据
    mock_event_bus_stats = {
        "events_emitted": 150,
        "handlers_called": 300,
    }
    collector.sync_from_event_bus(mock_event_bus_stats)

    mock_provider_health = {
        "openai": {
            "healthy": True,
            "average_latency_ms": 120.5,
        }
    }
    collector.sync_from_provider_pool(mock_provider_health)

    # 4. 获取指标
    metrics = collector.get_all_metrics()

    print(f"\n请求统计:")
    print(f"  总请求: {metrics['requests']['total']}")
    print(f"  错误数: {metrics['requests']['errors']}")
    print(f"  错误率: {metrics['requests']['error_rate']:.2%}")

    print(f"\n延迟统计:")
    print(f"  平均延迟: {metrics['latency']['average_ms']:.1f}ms")
    print(f"  P50: {metrics['latency']['p50_ms']:.1f}ms")
    print(f"  P95: {metrics['latency']['p95_ms']:.1f}ms")
    print(f"  P99: {metrics['latency']['p99_ms']:.1f}ms")

    print(f"\nToken 统计:")
    print(f"  输入: {metrics['tokens']['total_input']}")
    print(f"  输出: {metrics['tokens']['total_output']}")
    print(f"  总计: {metrics['tokens']['total']}")

    print(f"\n会话统计:")
    print(f"  活跃会话: {metrics['sessions']['active_count']}")

    # 5. 导出格式
    print(f"\n摘要: {collector.get_summary()}")

    # 6. JSON 导出
    json_export = collector.export_json()
    print(f"\nJSON 导出长度: {len(json_export)} 字符")

    # 7. Prometheus 导出
    prometheus_export = collector.export_prometheus()
    prometheus_lines = prometheus_export.split('\n')
    print(f"Prometheus 导出: {len(prometheus_lines)} 行")
    print(f"示例:")
    for line in prometheus_lines[:5]:
        if line and not line.startswith('#'):
            print(f"  {line}")


async def example_integration():
    """示例 7: 完整集成场景"""
    print("\n" + "="*60)
    print("示例 7: 完整集成场景")
    print("="*60)

    # 1. 创建组件
    telemetry = TelemetryCollector()
    automation = AutomationManager()
    webchat = WebChatChannel({"max_sessions": 10})

    await webchat.initialize()
    await automation.start()

    # 2. 连接组件
    async def on_webchat_message(msg):
        """处理 WebChat 消息"""
        print(f"\n收到消息: {msg.content[:50]}...")

        # 追踪请求
        telemetry.track_request(
            session_key=msg.session_key,
            latency_ms=50.0,
            success=True
        )

        # 追踪 token
        telemetry.track_tokens(
            session_key=msg.session_key,
            input_tokens=100,
            output_tokens=50
        )

    webchat.on_message(on_webchat_message)

    # 3. 模拟场景
    session_id = webchat.create_session()

    # 用户发送多条消息
    for i in range(5):
        await webchat.receive_message(
            session_id=session_id,
            content=f"用户消息 {i+1}",
            sender="user"
        )

    # 4. 查看统计
    metrics = telemetry.get_all_metrics()
    print(f"\n集成统计:")
    print(f"  处理消息数: {metrics['requests']['total']}")
    print(f"  总 Token: {metrics['tokens']['total']}")

    # 5. 清理
    await automation.stop()
    await webchat.stop()

    print("\n集成场景完成")


async def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("PyAgentForge v3.0 架构功能演示")
    print("="*60)

    await example_session_key()
    await example_env_parser()
    await example_webchat_channel()
    await example_webhook_channel()
    await example_automation()
    await example_telemetry()
    await example_integration()

    print("\n" + "="*60)
    print("所有示例完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
