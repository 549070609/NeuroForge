#!/usr/bin/env python
"""
Service Layer 测试 CLI

用于调试 Agent 接口调用，输出详细的过程日志。

使用方法:
    python test_cli.py                    # 交互模式
    python test_cli.py --debug            # 调试模式
    python test_cli.py --batch test.json  # 批处理模式
    python test_cli.py --log-file test.log # 保存日志到文件

命令:
    /create [model] [tools]  - 创建 Agent 会话
    /exec <prompt>           - 同步执行
    /stream <prompt>         - 流式执行
    /status [session_id]     - 查看状态
    /caps [session_id]       - 查看能力
    /reset [session_id]      - 重置会话
    /destroy [session_id]    - 销毁会话
    /list                    - 列出所有会话
    /debug on/off            - 开关调试日志
    /quit                    - 退出
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parent
MAIN_DIR = SERVICE_DIR.parent

paths_to_add = [str(MAIN_DIR), str(SERVICE_DIR)]
for p in paths_to_add:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(MAIN_DIR.parent / ".env")

model_api_key = os.environ.get("TEST_LLM_API_KEY", os.environ.get("GLM_API_KEY", ""))
model_base_url = os.environ.get("TEST_LLM_BASE_URL", "https://api.example.com/v1")
if model_api_key:
    print(f"[DEBUG] TEST_LLM_API_KEY 已设置: {model_api_key[:10]}...")
else:
    print("[DEBUG] TEST_LLM_API_KEY 未设置，将使用 api_key_env 占位")

print("[DEBUG] 开始注册调试模型 (在导入 Service 模块之前)...")
try:
    from pyagentforge import ModelConfig, get_registry, register_model

    debug_model_config = ModelConfig(
        id="custom-debug-model",
        name="Custom Debug Model",
        provider="custom-debug",
        api_type="openai-completions",
        model_name="custom-debug-model",
        base_url=model_base_url,
        api_key=model_api_key or None,
        api_key_env="TEST_LLM_API_KEY",
        context_window=128000,
        max_output_tokens=4096,
        supports_tools=True,
        supports_streaming=True,
    )
    register_model(debug_model_config)
    print("[DEBUG] OK Custom Debug Model 已注册")

    registry = get_registry()
    model = registry.get_model("custom-debug-model")
    print(f"[DEBUG] 验证模型: {model}")
    if model:
        print(f"[DEBUG]   model.name: {model.name}")
        print(f"[DEBUG]   model.provider: {model.provider}")
except Exception as e:
    print(f"[DEBUG] FAIL 调试模型注册失败: {e}")
    import traceback
    traceback.print_exc()

print(f"[DEBUG] 脚本目录: {SCRIPT_DIR}")
print(f"[DEBUG] Service目录: {SERVICE_DIR}")
print(f"[DEBUG] Main目录: {MAIN_DIR}")

# === 日志配置 ===
# === 日志配置 ===

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(debug: bool = False, log_file: str | None = None):
    """配置日志系统"""
    level = logging.DEBUG if debug else logging.INFO

    # 根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = ColoredFormatter(
        '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 文件总是记录所有
        file_format = logging.Formatter(
            '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)

    return logging.getLogger('test_cli')


# === 辅助函数 ===

def print_separator(char='=', length=60):
    """打印分隔线"""
    print(f"\n{char * length}\n")


def print_json(data: Any, title: str = ""):
    """美化打印 JSON"""
    if title:
        print(f"\n{title}:")
    try:
        formatted = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        for line in formatted.split('\n'):
            print(f"  {line}")
    except Exception:
        print(f"  {data}")


def print_header(title: str):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# === 测试客户端 ===

@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    model: str
    tools: list[str]
    created_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0


class AGentTestClient:
    """Agent 测试客户端 - 输出详细调试日志"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.registry = None
        self.agent_service = None
        self.sessions: dict[str, SessionInfo] = {}
        self.current_session: str | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """初始化 Service 层"""
        print_header("初始化 Service 层")

        try:
            # 1. 导入（调试模型 已在模块顶部注册）
            self.logger.info("导入 Service 层模块...")
            print("[DEBUG] 导入 Service 层模块...")
            from Service.config import ServiceSettings
            from Service.core import AGENT_SERVICE_KEY, ServiceRegistry
            from Service.services.agent_service import AgentService
            print("[DEBUG] 导入完成")

            # 2. 创建设置
            self.logger.debug("创建 ServiceSettings...")
            settings = ServiceSettings(
                debug=True,
                log_level="DEBUG",
                default_model="custom-debug-model",  # 使用调试模型
            )
            self.logger.info(f"设置: model={settings.default_model}, debug={settings.debug}")

            # 3. 获取注册表
            self.logger.info("创建 ServiceRegistry...")
            self.registry = ServiceRegistry()
            self.registry.reset()

            # 4. 创建并注册服务
            self.logger.info("创建 AgentService...")
            self.agent_service = AgentService(self.registry)
            self.registry.register(AGENT_SERVICE_KEY, self.agent_service)
            self.logger.debug("AgentService 已注册到 registry")

            # 5. 初始化所有服务
            self.logger.info("初始化所有服务...")
            await self.registry.initialize_all()

            self._initialized = True
            self.logger.info("✓ Service 层初始化完成")
            return True

        except Exception as e:
            self.logger.error(f"✗ 初始化失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False

    async def shutdown(self):
        """关闭 Service 层"""
        print_header("关闭 Service 层")

        try:
            if self.registry:
                self.logger.info("关闭所有服务...")
                await self.registry.shutdown_all()
            self.logger.info("✓ Service 层已关闭")
        except Exception as e:
            self.logger.error(f"✗ 关闭失败: {e}")

    async def create_session(
        self,
        model: str = "claude-sonnet-4",
        tools: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> str | None:
        """创建 Agent 会话"""
        print_header("创建 Agent 会话")

        if not self._initialized:
            self.logger.error("Service 层未初始化")
            return None

        tools = tools or ["bash", "read"]

        try:
            # 导入
            from Service.schemas import CreateAgentRequest

            # 构建请求
            request = CreateAgentRequest(
                model=model,
                tools=tools,
                system_prompt=system_prompt or "You are a helpful assistant.",
            )

            self.logger.info("创建请求:")
            print_json({
                "model": request.model,
                "tools": request.tools,
                "system_prompt": request.system_prompt[:100] + "..." if request.system_prompt else None,
            }, "请求参数")

            # 调用服务
            self.logger.debug("调用 agent_service.create()...")
            start_time = datetime.now()

            response = await self.agent_service.create(request)

            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"响应耗时: {elapsed:.2f}s")

            # 记录会话
            session_id = response.session_id
            self.sessions[session_id] = SessionInfo(
                session_id=session_id,
                model=response.model,
                tools=response.tools,
            )
            self.current_session = session_id

            self.logger.info("响应:")
            print_json({
                "session_id": response.session_id,
                "model": response.model,
                "tools": response.tools,
                "plugins": response.plugins,
                "created_at": str(response.created_at),
            }, "响应数据")

            self.logger.info(f"✓ 会话创建成功: {session_id}")
            return session_id

        except Exception as e:
            self.logger.error(f"✗ 创建会话失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    async def ensure_session(self) -> bool:
        """确保有可用会话，没有则自动创建"""
        if self.current_session:
            return True

        self.logger.info("没有可用会话，自动创建...")
        session_id = await self.create_session()
        return session_id is not None

    async def execute(self, prompt: str, session_id: str | None = None) -> str | None:
        """同步执行"""
        print_header("执行同步请求")

        if not self._initialized:
            self.logger.error("Service 层未初始化")
            return None

        session_id = session_id or self.current_session
        if not session_id:
            # 自动创建会话
            if not await self.ensure_session():
                return None
            session_id = self.current_session

        try:
            from Service.schemas import ExecuteRequest

            self.logger.info(f"会话 ID: {session_id}")
            self.logger.info(f"提示词: {prompt}")

            request = ExecuteRequest(prompt=prompt)

            self.logger.debug("调用 agent_service.execute()...")
            start_time = datetime.now()

            result = await self.agent_service.execute(session_id, request)

            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"响应耗时: {elapsed:.2f}s")

            # 更新会话信息
            if session_id in self.sessions:
                self.sessions[session_id].message_count += 1

            self.logger.info("响应:")
            print_json({
                "session_id": result.get("session_id"),
                "response_length": len(result.get("response", "")),
                "duration_ms": result.get("duration_ms"),
            }, "响应元数据")

            print("\n响应内容:")
            print("-" * 40)
            print(result.get("response", ""))
            print("-" * 40)

            self.logger.info("✓ 执行完成")
            return result.get("response")

        except Exception as e:
            self.logger.error(f"✗ 执行失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None

    async def stream(self, prompt: str, session_id: str | None = None):
        """流式执行"""
        print_header("执行流式请求")

        if not self._initialized:
            self.logger.error("Service 层未初始化")
            return

        session_id = session_id or self.current_session
        if not session_id:
            # 自动创建会话
            if not await self.ensure_session():
                return
            session_id = self.current_session

        try:
            self.logger.info(f"会话 ID: {session_id}")
            self.logger.info(f"提示词: {prompt}")

            self.logger.debug("调用 agent_service.stream()...")
            start_time = datetime.now()

            event_count = 0
            full_content = []

            print("\n流式输出:")
            print("-" * 40)

            async for sse_event in self.agent_service.stream(session_id, prompt):
                event_count += 1
                self.logger.debug(f"收到事件 #{event_count}")

                # 解析 SSE 事件
                if sse_event.startswith("event:"):
                    lines = sse_event.strip().split("\n")
                    event_type = lines[0].replace("event:", "").strip()
                    data = lines[1].replace("data:", "").strip() if len(lines) > 1 else ""

                    self.logger.debug(f"事件类型: {event_type}")

                    try:
                        data_json = json.loads(data)
                    except Exception:
                        data_json = data

                    if event_type == "connected":
                        self.logger.info(f"✓ 已连接: {data_json.get('session_id', '')}")

                    elif event_type == "stream":
                        content = data_json.get("content", "")
                        full_content.append(content)
                        print(content, end="", flush=True)

                    elif event_type == "tool_start":
                        self.logger.info(f"工具开始: {data_json.get('tool_name', '')}")

                    elif event_type == "tool_result":
                        self.logger.debug(f"工具结果: {data_json}")

                    elif event_type == "complete":
                        elapsed = (datetime.now() - start_time).total_seconds()
                        self.logger.info("✓ 流式完成")
                        self.logger.info(f"事件数: {event_count}, 耗时: {elapsed:.2f}s")
                        if data_json.get("duration_ms"):
                            self.logger.info(f"服务端耗时: {data_json['duration_ms']:.0f}ms")

                    elif event_type == "error":
                        self.logger.error(f"错误: {data_json.get('error', '')}")

            print("\n" + "-" * 40)

            # 更新会话信息
            if session_id in self.sessions:
                self.sessions[session_id].message_count += 1

        except Exception as e:
            self.logger.error(f"✗ 流式执行失败: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())

    async def reset(self, session_id: str | None = None) -> bool:
        """重置会话"""
        print_header("重置会话")

        session_id = session_id or self.current_session
        if not session_id:
            self.logger.error("没有可用的会话")
            return False

        try:
            self.logger.info(f"重置会话: {session_id}")
            await self.agent_service.reset(session_id)

            if session_id in self.sessions:
                self.sessions[session_id].message_count = 0

            self.logger.info("✓ 会话已重置")
            return True

        except Exception as e:
            self.logger.error(f"✗ 重置失败: {e}")
            return False

    async def destroy(self, session_id: str | None = None) -> bool:
        """销毁会话"""
        print_header("销毁会话")

        session_id = session_id or self.current_session
        if not session_id:
            self.logger.error("没有可用的会话")
            return False

        try:
            self.logger.info(f"销毁会话: {session_id}")
            await self.agent_service.destroy(session_id)

            if session_id in self.sessions:
                del self.sessions[session_id]

            if self.current_session == session_id:
                self.current_session = None

            self.logger.info("✓ 会话已销毁")
            return True

        except Exception as e:
            self.logger.error(f"✗ 销毁失败: {e}")
            return False

    async def get_status(self, session_id: str | None = None):
        """获取会话状态"""
        print_header("获取会话状态")

        session_id = session_id or self.current_session
        if not session_id:
            self.logger.error("没有可用的会话")
            return

        try:
            self.logger.info(f"查询会话: {session_id}")
            status = await self.agent_service.status(session_id)

            print_json({
                "session_id": status.session_id,
                "model": status.model,
                "status": status.status,
                "message_count": status.message_count,
                "created_at": str(status.created_at),
                "last_activity": str(status.last_activity),
            }, "会话状态")

            self.logger.info("✓ 状态获取成功")

        except Exception as e:
            self.logger.error(f"✗ 获取状态失败: {e}")

    async def get_capabilities(self, session_id: str | None = None):
        """获取会话能力"""
        print_header("获取会话能力")

        session_id = session_id or self.current_session
        if not session_id:
            self.logger.error("没有可用的会话")
            return

        try:
            self.logger.info(f"查询会话: {session_id}")
            caps = await self.agent_service.capabilities(session_id)

            print_json({
                "model": caps.model,
                "tools": caps.tools,
                "plugins": caps.plugins,
                "max_tokens": caps.max_tokens,
                "temperature": caps.temperature,
            }, "会话能力")

            self.logger.info("✓ 能力获取成功")

        except Exception as e:
            self.logger.error(f"✗ 获取能力失败: {e}")

    def list_sessions(self):
        """列出所有会话"""
        print_header("会话列表")

        if not self.sessions:
            self.logger.info("没有活跃的会话")
            return

        for sid, info in self.sessions.items():
            current = " (当前)" if sid == self.current_session else ""
            print(f"\n  会话: {sid}{current}")
            print(f"    模型: {info.model}")
            print(f"    工具: {info.tools}")
            print(f"    消息数: {info.message_count}")
            print(f"    创建时间: {info.created_at}")

        self.logger.info(f"共 {len(self.sessions)} 个会话")


# === 命令处理器 ===

class CommandHandler:
    """命令处理器"""

    def __init__(self, client: AGentTestClient, logger: logging.Logger):
        self.client = client
        self.logger = logger
        self.running = True
        self.debug_mode = False

    def toggle_debug(self):
        """切换调试模式"""
        self.debug_mode = not self.debug_mode
        level = logging.DEBUG if self.debug_mode else logging.INFO
        logging.getLogger().setLevel(level)
        self.logger.info(f"调试模式: {'开启' if self.debug_mode else '关闭'}")

    async def process(self, command: str):
        """处理命令"""
        parts = command.strip().split(maxsplit=3)
        if not parts:
            return

        cmd = parts[0].lower()

        try:
            if cmd == "/help":
                self.show_help()

            elif cmd == "/create":
                model = parts[1] if len(parts) > 1 else "claude-sonnet-4"
                tools = parts[2].split(",") if len(parts) > 2 else None
                await self.client.create_session(model, tools)

            elif cmd == "/exec":
                if len(parts) < 2:
                    self.logger.error("用法: /exec <prompt>")
                else:
                    prompt = " ".join(parts[1:])
                    await self.client.execute(prompt)

            elif cmd == "/stream":
                if len(parts) < 2:
                    self.logger.error("用法: /stream <prompt>")
                else:
                    prompt = " ".join(parts[1:])
                    await self.client.stream(prompt)

            elif cmd == "/status":
                session_id = parts[1] if len(parts) > 1 else None
                await self.client.get_status(session_id)

            elif cmd == "/caps":
                session_id = parts[1] if len(parts) > 1 else None
                await self.client.get_capabilities(session_id)

            elif cmd == "/reset":
                session_id = parts[1] if len(parts) > 1 else None
                await self.client.reset(session_id)

            elif cmd == "/destroy":
                session_id = parts[1] if len(parts) > 1 else None
                await self.client.destroy(session_id)

            elif cmd == "/list":
                self.client.list_sessions()

            elif cmd == "/debug":
                if len(parts) > 1 and parts[1] in ["on", "off"]:
                    if (parts[1] == "on") != self.debug_mode:
                        self.toggle_debug()
                else:
                    self.toggle_debug()

            elif cmd in ["/quit", "/exit"]:
                self.running = False

            else:
                self.logger.error(f"未知命令: {cmd}")
                self.show_help()

        except Exception as e:
            self.logger.error(f"命令执行错误: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())

    def show_help(self):
        """显示帮助"""
        print("""
命令帮助:
  /create [model] [tools]  - 创建 Agent 会话
                           - model: claude-sonnet-4 (默认)
                           - tools: bash,read (默认)

  /exec <prompt>           - 同步执行
  /stream <prompt>         - 流式执行

  /status [session_id]     - 获取会话状态
  /caps [session_id]       - 获取会话能力

  /reset [session_id]      - 重置会话
  /destroy [session_id]    - 销毁会话
  /list                    - 列出所有会话

  /debug [on/off]          - 切换调试模式
  /help                    - 显示帮助
  /quit                    - 退出
""")


# === 主函数 ===

async def interactive_mode(client: AGentTestClient, logger: logging.Logger, default_model: str = "custom-debug-model"):
    """交互模式"""
    cmd_handler = CommandHandler(client, logger)

    print("""
╔════════════════════════════════════════════════════════════╗
║        Service Layer 测试 CLI - 交互模式                   ║
╠════════════════════════════════════════════════════════════╣
║  直接输入消息即可对话（自动创建会话）                       ║
║  输入 /help 查看命令                                       ║
║  输入 /quit 退出                                           ║
╚════════════════════════════════════════════════════════════╝
""")

    # 自动创建默认会话
    logger.info("正在创建默认会话...")
    session_id = await client.create_session(model=default_model)
    if session_id:
        logger.info(f"✓ 默认会话已创建: {session_id}")
    else:
        logger.warning("⚠ 默认会话创建失败，请手动使用 /create 创建")

    while cmd_handler.running:
        try:
            prompt = f"\n[{client.current_session[:8] if client.current_session else 'no-session'}] > "
            user_input = input(prompt).strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                await cmd_handler.process(user_input)
            else:
                # 默认作为执行命令
                await client.execute(user_input)

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n")
            break


async def batch_mode(client: AGentTestClient, batch_file: str, logger: logging.Logger):
    """批处理模式"""
    logger.info(f"加载批处理文件: {batch_file}")

    try:
        with open(batch_file, encoding='utf-8') as f:
            batch = json.load(f)

        for step in batch:
            action = step.get("action")
            params = step.get("params", {})

            logger.info(f"执行: {action}")

            if action == "create":
                await client.create_session(**params)
            elif action == "exec":
                await client.execute(**params)
            elif action == "stream":
                await client.stream(**params)
            elif action == "reset":
                await client.reset(**params)
            elif action == "destroy":
                await client.destroy(**params)
            elif action == "status":
                await client.get_status(**params)
            elif action == "caps":
                await client.get_capabilities(**params)
            else:
                logger.warning(f"未知操作: {action}")

        logger.info("批处理完成")

    except Exception as e:
        logger.error(f"批处理失败: {e}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Service Layer 测试 CLI")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    parser.add_argument("--log-file", type=str, help="日志文件路径")
    parser.add_argument("--batch", type=str, help="批处理文件路径")
    parser.add_argument("--model", type=str, default="custom-debug-model", help="默认模型")
    args = parser.parse_args()

    # 配置日志
    logger = setup_logging(debug=args.debug, log_file=args.log_file)

    logger.info("=" * 60)
    logger.info("Service Layer 测试 CLI 启动")
    logger.info("=" * 60)

    # 创建客户端
    client = AGentTestClient(logger)

    try:
        # 初始化
        if not await client.initialize():
            logger.error("初始化失败，退出")
            sys.exit(1)

        # 运行
        if args.batch:
            await batch_mode(client, args.batch, logger)
        else:
            await interactive_mode(client, logger, default_model=args.model)

    finally:
        await client.shutdown()

    logger.info("测试 CLI 结束")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")


