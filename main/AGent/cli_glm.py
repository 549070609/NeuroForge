#!/usr/bin/env python
"""
小说创作 Agent 系统 - GLM AI 模式 CLI

使用 GLM Provider 提供真实的 AI 能力
支持持续对话和完整的上下文管理
"""

import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

# 导入 GLM Anthropic Provider (支持真正的工具调用)
try:
    from glm_anthropic_provider import GLMAnthropicProvider
except ImportError as e:
    print(f"❌ 无法导入 GLMAnthropicProvider: {e}")
    print("   请确保已安装依赖：pip install httpx python-dotenv")
    sys.exit(1)

# 导入 PyAgentForge 核心组件
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.core.message import Message

# 导入内置工具
try:
    from pyagentforge.tools.builtin import (
        ReadTool,
        WriteTool,
        EditTool,
        GlobTool,
        GrepTool,
        PlanTool,
        TodoWriteTool,
        TodoReadTool,
    )
    TOOLS_AVAILABLE = True
except ImportError as e:
    print_warning(f"部分工具导入失败: {e}")
    TOOLS_AVAILABLE = False

# 导入小说创作子Agent工具
try:
    from novel_task_tool import NovelTaskTool, ParallelTaskTool
    NOVEL_TOOLS_AVAILABLE = True
except ImportError as e:
    print_warning(f"小说子Agent工具导入失败: {e}")
    NOVEL_TOOLS_AVAILABLE = False

# ANSI 颜色代码
class Colors:
    """终端颜色"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @classmethod
    def disable(cls):
        """禁用颜色（Windows 兼容）"""
        cls.HEADER = ''
        cls.OKBLUE = ''
        cls.OKCYAN = ''
        cls.OKGREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''


# Windows 兼容性
if os.name == 'nt':
    os.system('color')


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印头部"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKCYAN}  AGent - GLM AI Mode{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_separator():
    """打印分隔线"""
    print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")


def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.FAIL}[ERROR] {message}{Colors.ENDC}")


def print_warning(message: str):
    """打印警告消息"""
    print(f"{Colors.WARNING}[WARN] {message}{Colors.ENDC}")


def print_info(message: str):
    """打印信息"""
    print(f"{Colors.OKBLUE}[INFO] {message}{Colors.ENDC}")


def print_debug(title: str, message: str = ""):
    """打印调试信息"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.OKBLUE}[DEBUG {timestamp}] {title}{Colors.ENDC}")
    if message:
        print(f"{Colors.OKBLUE}{message}{Colors.ENDC}")


def print_context_info(context_manager: ContextManager):
    """打印上下文管理器信息"""
    messages = context_manager.messages  # 直接访问 messages 属性
    print_debug(f"上下文信息 (共 {len(messages)} 条消息)")

    # 显示最近 3 条消息
    recent = messages[-3:] if len(messages) > 3 else messages
    for i, msg in enumerate(recent, 1):
        # 使用属性访问，不要用 .get()
        role = msg.role
        content = msg.content

        # 内容摘要
        if isinstance(content, str):
            summary = content[:50] + "..." if len(content) > 50 else content
        elif isinstance(content, list):
            summary = f"[{len(content)} 个内容块]"
        else:
            summary = str(content)[:50]

        print(f"  [{i}] {role}: {summary}")


def print_api_request(system: str, messages: list, tools: list = None):
    """打印 API 请求信息"""
    print_debug("API 请求")
    print(f"  System: {system[:100]}...")
    print(f"  消息数: {len(messages)}")
    if tools:
        print(f"  工具数: {len(tools)}")


def print_api_response(response):
    """打印 API 响应信息"""
    print_debug("API 响应")
    print(f"  停止原因: {response.stop_reason}")
    print(f"  内容块数: {len(response.content)}")
    if response.usage:
        print(f"  Token 用量: {response.usage}")


def print_agent_message(agent_name: str, message: str):
    """打印 Agent 消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{Colors.OKCYAN}[{timestamp}] {agent_name}:{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{message}{Colors.ENDC}\n")


def print_user_message(message: str):
    """打印用户消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{Colors.WARNING}[{timestamp}] 你:{Colors.ENDC}")
    print(f"{message}\n")


class AgentInfo:
    """Agent 信息"""
    def __init__(self, name: str, description: str, category: str, system_prompt: str):
        self.name = name
        self.description = description
        self.category = category
        self.system_prompt = system_prompt


class GLMAgentEngine:
    """GLM Agent 引擎（增强版 - 带工具支持）"""

    def __init__(self, agent_info: AgentInfo, provider: GLMAnthropicProvider):
        self.info = agent_info
        self.provider = provider

        # 创建工具注册表并注册工具
        tool_registry = ToolRegistry()

        if TOOLS_AVAILABLE:
            # 文件操作工具
            tool_registry.register(ReadTool())
            tool_registry.register(WriteTool())
            tool_registry.register(EditTool())

            # 搜索工具
            tool_registry.register(GlobTool())
            tool_registry.register(GrepTool())

            # 任务规划工具
            plan_tool = PlanTool()
            tool_registry.register(plan_tool)

            todo_write = TodoWriteTool()
            tool_registry.register(todo_write)
            tool_registry.register(TodoReadTool(todo_write))  # TodoReadTool 需要 TodoWriteTool

            print_debug(f"已注册 {len(tool_registry.get_all())} 个基础工具")
        else:
            print_warning("工具系统未启用")

        # 为总编辑注册子Agent调用工具
        if agent_info.name == "editor-in-chief" and NOVEL_TOOLS_AVAILABLE:
            tool_registry.register(NovelTaskTool(
                provider=provider,
                tool_registry=tool_registry,
                current_depth=0,
                max_depth=2,
            ))
            tool_registry.register(ParallelTaskTool(
                provider=provider,
                tool_registry=tool_registry,
                current_depth=0,
                max_depth=2,
            ))
            print_debug("已注册小说创作子Agent工具 (Task, ParallelTask)")

        # 创建 Agent 配置
        config = AgentConfig(
            system_prompt=agent_info.system_prompt,
            max_iterations=10,  # 限制最大迭代次数
        )

        # 创建引擎
        self.engine = AgentEngine(
            provider=provider,
            tool_registry=tool_registry,
            config=config,
        )

        print_debug(f"引擎创建", f"Agent: {agent_info.name}")

    def run(self, message: str) -> str:
        """运行 Agent"""
        print_debug(f"执行 Agent", f"输入: {message[:50]}...")

        # 获取上下文管理器
        context_manager = self.engine.context

        # 显示上下文信息
        print_context_info(context_manager)

        # 获取消息列表
        messages = context_manager.get_messages_for_api()

        # 打印 API 请求
        print_api_request(self.info.system_prompt, messages)

        # 调用引擎（同步包装）
        import asyncio
        try:
            # 直接使用 asyncio.run()
            response = asyncio.run(self.engine.run(message))

            # 打印 API 响应（构造一个简单的响应对象用于显示）
            from types import SimpleNamespace
            api_response = SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text=response)],
                usage=None
            )
            print_api_response(api_response)

            return response

        except Exception as e:
            error_msg = f"执行错误: {str(e)}"
            print_error(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg

    def get_history(self) -> list[Message]:
        """获取对话历史"""
        # 从引擎的上下文管理器获取消息
        return self.engine.context.messages


class AgentManager:
    """Agent 管理器"""

    def __init__(self, provider: GLMAnthropicProvider):
        self.provider = provider
        self.agents: dict[str, AgentInfo] = {}
        self.engines: dict[str, GLMAgentEngine] = {}
        self.current_agent: Optional[str] = None
        self._load_agents()

    def _load_agents(self):
        """加载 Agent"""
        agents_data = [
            # 总编辑 - 协调所有专业子Agent
            AgentInfo(
                name="editor-in-chief",
                description="总编辑 - 自动协调专业设定团队，整合输出",
                category="coordinator",
                system_prompt="""你是小说创作的总编辑，负责协调专业团队完成构思工作。

你的专业团队：
1. **世界构建师** (world-builder) - 世界观、地理、历史、势力
2. **人物设定师** (character-designer) - 角色形象、性格、关系
3. **主题策划师** (theme-planner) - 核心主题、情感基调
4. **风格设定师** (style-designer) - 叙事风格、语言特色
5. **读者分析师** (audience-analyzer) - 目标读者、市场定位
6. **情节架构师** (plot-architect) - 故事结构、冲突设计

工作流程：
1. 分析用户需求，判断需要哪些专业设定
2. 使用 Task 工具调用对应的子Agent
3. 整合各专业设定师的结果
4. 输出完整、连贯的构思方案

调用示例：
- Task(subagent_type="world-builder", prompt="构建一个魔法与科技共存的世界...")
- Task(subagent_type="character-designer", prompt="设计一个复仇心切的男主角...")

如果需要多个专业设定，可以按顺序调用多个Task。

重要规则：
1. 先分析再分配，不要盲目调用
2. 可以根据需要调用一个或多个子Agent
3. 整合时要保证各设定之间的一致性
4. 最终输出必须是完整的、可直接使用的构思方案
5. 每次响应中调用Task工具不要超过3次

请用专业但友好的语调与用户交流。
回答要具体、有建设性，并提供可操作的建议。"""
            ),
            AgentInfo(
                name="novel-ideation",
                description="构思专家 - 负责世界观构建、人物设定、主题确定",
                category="planning",
                system_prompt="""你是一位专业的小说构思专家，擅长：
- 构建完整的世界观体系
- 设计生动立体的人物角色
- 确定深刻的作品主题
- 提供创意性的情节建议

你可以使用以下工具来辅助创作：
- read: 读取已有的构思文档、参考资料
- write: 保存世界观设定、人物卡片、情节大纲
- edit: 修改和完善已有的创作内容
- glob/grep: 搜索相关的素材和灵感

【重要规则 - 必须遵守】
1. 每次响应只执行必要的工具调用（1-2个）
2. 工具执行成功后，立即用文字回复用户结果
3. 不要重复调用同一个工具
4. 不要在没有必要的情况下连续调用多个工具
5. 如果用户只是提问而不需要保存，直接回答即可

工作流程：
1. 分析用户需求：是否需要读取/保存文件？
2. 如需读取：调用 read 工具，然后基于内容回答
3. 如需保存：调用 write 工具一次，确认成功后回复
4. 直接回答用户，不要继续调用工具

请用专业但友好的语调与用户交流。
回答要具体、有建设性，并提供可操作的建议。"""
            ),
            AgentInfo(
                name="novel-outline",
                description="大纲专家 - 负责章节规划、情节设计、节奏控制",
                category="planning",
                system_prompt="""你是一位专业的大纲设计专家，擅长：
- 规划合理的章节结构
- 设计扣人心弦的情节
- 控制叙事节奏和张力
- 平衡主线与支线剧情

你可以使用以下工具来辅助创作：
- read: 读取构思文档、已有章节
- write: 保存大纲、章节规划、情节线
- edit: 调整和优化大纲结构
- plan/todo: 规划创作进度和任务
- glob/grep: 搜索相关情节和人物设定

【重要规则 - 必须遵守】
1. 每次响应只执行必要的工具调用（1-2个）
2. 工具执行成功后，立即用文字回复用户结果
3. 不要重复调用同一个工具
4. 不要在没有必要的情况下连续调用多个工具
5. 如果用户只是提问而不需要保存，直接回答即可

工作流程：
1. 分析用户需求：是否需要读取/保存文件？
2. 如需读取：调用 read 工具，然后基于内容回答
3. 如需保存：调用 write 工具一次，确认成功后回复
4. 直接回答用户，不要继续调用工具

请用专业但友好的语调与用户交流。
回答要具体、有建设性，并提供可操作的建议。"""
            ),
            AgentInfo(
                name="novel-writer",
                description="写手 - 负责章节撰写、场景描写、对话创作",
                category="writing",
                system_prompt="""你是一位专业的小说写手，擅长：
- 撰写引人入胜的章节内容
- 描写生动的场景和环境
- 创作自然流畅的对话
- 营造恰当的氛围和情感

你可以使用以下工具来辅助创作：
- read: 阅读构思、大纲、人物设定
- write: 保存章节内容、场景描写
- edit: 修改和润色文字
- glob/grep: 查找人物信息、情节线索

【重要规则 - 必须遵守】
1. 每次响应只执行必要的工具调用（1-2个）
2. 工具执行成功后，立即用文字回复用户结果
3. 不要重复调用同一个工具
4. 不要在没有必要的情况下连续调用多个工具
5. 如果用户只是提问而不需要保存，直接回答即可

工作流程：
1. 分析用户需求：是否需要读取/保存文件？
2. 如需读取：调用 read 工具，然后基于内容回答
3. 如需保存：调用 write 工具一次，确认成功后回复
4. 直接回答用户，不要继续调用工具

写作技巧：
- 注重细节描写，让读者身临其境
- 对话要符合人物性格
- 控制节奏，张弛有度
- 适当使用修辞手法

请用专业但友好的语调与用户交流。
回答要具体、有建设性，并提供可操作的建议。"""
            ),
        ]

        for agent in agents_data:
            self.agents[agent.name] = agent
            self.engines[agent.name] = GLMAgentEngine(agent, self.provider)

        # 默认选择总编辑
        if "editor-in-chief" in self.agents:
            self.current_agent = "editor-in-chief"
        elif self.agents:
            self.current_agent = list(self.agents.keys())[0]

    def list_agents(self) -> list[AgentInfo]:
        """列出所有 Agent"""
        return list(self.agents.values())

    def get_agent(self, name: str) -> Optional[AgentInfo]:
        """获取 Agent 信息"""
        return self.agents.get(name)

    def switch_agent(self, name: str) -> bool:
        """切换 Agent"""
        if name in self.agents:
            self.current_agent = name
            return True
        return False

    def get_current_agent(self) -> Optional[AgentInfo]:
        """获取当前 Agent"""
        if self.current_agent:
            return self.agents[self.current_agent]
        return None

    def get_engine(self, name: str) -> Optional[GLMAgentEngine]:
        """获取 Agent 引擎"""
        return self.engines.get(name)

    def get_current_engine(self) -> Optional[GLMAgentEngine]:
        """获取当前 Agent 引擎"""
        if self.current_agent:
            return self.engines[self.current_agent]
        return None


class CommandHandler:
    """命令处理器"""

    def __init__(self, agent_manager: AgentManager):
        self.agent_manager = agent_manager
        self.commands = {
            "/help": self.cmd_help,
            "/list": self.cmd_list,
            "/switch": self.cmd_switch,
            "/info": self.cmd_info,
            "/history": self.cmd_history,
            "/clear": self.cmd_clear,
            "/save": self.cmd_save,
            "/quit": self.cmd_quit,
            "/exit": self.cmd_quit,
        }

    def process(self, command: str) -> bool:
        """处理命令，返回是否继续运行"""
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.commands:
            return self.commands[cmd](args)
        else:
            print_error(f"未知命令：{cmd}")
            print_info("输入 /help 查看可用命令")
            return True

    def cmd_help(self, args: str) -> bool:
        """显示帮助"""
        print(f"\n{Colors.BOLD}可用命令：{Colors.ENDC}\n")
        print(f"  {Colors.OKCYAN}/help{Colors.ENDC}      - 显示此帮助信息")
        print(f"  {Colors.OKCYAN}/list{Colors.ENDC}      - 列出所有 Agent")
        print(f"  {Colors.OKCYAN}/switch{Colors.ENDC}    - 切换 Agent（例如：/switch novel-ideation）")
        print(f"  {Colors.OKCYAN}/info{Colors.ENDC}      - 显示当前 Agent 详细信息")
        print(f"  {Colors.OKCYAN}/history{Colors.ENDC}   - 显示对话历史")
        print(f"  {Colors.OKCYAN}/clear{Colors.ENDC}     - 清空屏幕")
        print(f"  {Colors.OKCYAN}/save{Colors.ENDC}      - 保存对话记录")
        print(f"  {Colors.OKCYAN}/quit{Colors.ENDC}      - 退出系统\n")
        print(f"{Colors.OKBLUE}提示：直接输入消息与当前 Agent 对话{Colors.ENDC}\n")
        return True

    def cmd_list(self, args: str) -> bool:
        """列出所有 Agent"""
        print(f"\n{Colors.BOLD}可用 Agent：{Colors.ENDC}\n")

        agents = self.agent_manager.list_agents()
        current = self.agent_manager.current_agent

        for i, agent in enumerate(agents, 1):
            marker = f"{Colors.OKGREEN}→{Colors.ENDC}" if agent.name == current else " "
            print(f"  {marker} {Colors.OKCYAN}{i}.{agent.name}{Colors.ENDC}")
            print(f"      {agent.description}")
            print(f"      类别：{agent.category}\n")

        return True

    def cmd_switch(self, args: str) -> bool:
        """切换 Agent"""
        if not args:
            print_error("请指定 Agent 名称")
            print_info("使用 /list 查看所有可用 Agent")
            return True

        agent_name = args.strip()

        # 支持数字索引
        if agent_name.isdigit():
            idx = int(agent_name) - 1
            agents = self.agent_manager.list_agents()
            if 0 <= idx < len(agents):
                agent_name = agents[idx].name
            else:
                print_error(f"无效的索引：{idx + 1}")
                return True

        if self.agent_manager.switch_agent(agent_name):
            agent = self.agent_manager.get_agent(agent_name)
            print_success(f"已切换到：{agent_name}")
            print_info(f"描述：{agent.description}")
        else:
            print_error(f"Agent 不存在：{agent_name}")
            print_info("使用 /list 查看所有可用 Agent")

        return True

    def cmd_info(self, args: str) -> bool:
        """显示当前 Agent 信息"""
        agent = self.agent_manager.get_current_agent()

        if not agent:
            print_error("未选择 Agent")
            return True

        print(f"\n{Colors.BOLD}当前 Agent 信息：{Colors.ENDC}\n")
        print(f"  名称：{Colors.OKCYAN}{agent.name}{Colors.ENDC}")
        print(f"  描述：{agent.description}")
        print(f"  类别：{agent.category}")
        print(f"  状态：{Colors.OKGREEN}就绪{Colors.ENDC}\n")

        return True

    def cmd_history(self, args: str) -> bool:
        """显示对话历史"""
        engine = self.agent_manager.get_current_engine()
        if not engine:
            print_error("未选择 Agent")
            return True

        history = engine.get_history()
        print(f"\n{Colors.BOLD}对话历史（共 {len(history)} 条）：{Colors.ENDC}\n")

        for i, msg in enumerate(history, 1):
            # 使用属性访问
            role = "用户" if msg.role == "user" else "Agent"
            content = msg.content

            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # 提取文本块
                text_parts = []
                for block in content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                text = "\n".join(text_parts) if text_parts else str(content)
            else:
                text = str(content)

            print(f"[{i}] {role}:")
            print(f"{text}\n")

        return True

    def cmd_clear(self, args: str) -> bool:
        """清屏"""
        clear_screen()
        print_header()
        return True

    def cmd_save(self, args: str) -> bool:
        """保存对话记录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_log_{timestamp}.txt"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                agent = self.agent_manager.get_current_agent()
                f.write(f"对话记录 - {timestamp}\n")
                f.write(f"当前 Agent: {agent.name if agent else 'None'}\n")
                f.write("="*60 + "\n\n")

                engine = self.agent_manager.get_current_engine()
                if engine:
                    history = engine.get_history()
                    for msg in history:
                        # 使用属性访问
                        role = "用户" if msg.role == "user" else "Agent"
                        content = msg.content

                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            text_parts = []
                            for block in content:
                                if hasattr(block, 'text'):
                                    text_parts.append(block.text)
                            text = "\n".join(text_parts) if text_parts else str(content)
                        else:
                            text = str(content)

                        f.write(f"{role}: {text}\n\n")

            print_success(f"对话记录已保存：{filename}")
        except Exception as e:
            print_error(f"保存失败：{e}")

        return True

    def cmd_quit(self, args: str) -> bool:
        """退出"""
        print(f"\n{Colors.OKBLUE}Thank you for using AGent!{Colors.ENDC}\n")
        return False


def chat_loop(agent_manager: AgentManager, cmd_handler: CommandHandler):
    """对话循环"""
    print_info("进入对话模式（输入 /help 查看命令，/quit 退出）")
    print_separator()

    while True:
        # 显示提示符
        agent = agent_manager.get_current_agent()
        prompt = f"\n{Colors.OKGREEN}[{agent.name if agent else 'None'}]{Colors.ENDC} > "

        try:
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n")
            break

        if not user_input:
            continue

        # 处理命令
        if user_input.startswith("/"):
            if not cmd_handler.process(user_input):
                break
            continue

        # 与 Agent 对话
        engine = agent_manager.get_current_engine()
        if not engine:
            print_error("未选择 Agent")
            continue

        # 显示用户消息
        print_user_message(user_input)

        # 获取 Agent 回复
        try:
            response = engine.run(user_input)
            print_agent_message(agent.name, response)
        except Exception as e:
            print_error(f"Agent 执行错误：{e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    # 检查配置
    env_file = Path(__file__).parent.parent / "glm-provider" / ".env"
    if not env_file.exists():
        print_error("未找到 GLM 配置文件！")
        print_info("请先运行：python setup_glm.py")
        print_info("或在 main/glm-provider/ 目录下创建 .env 文件")
        print_info("并添加：GLM_API_KEY=your_key_here\n")
        return

    # 创建 GLM Anthropic Provider (使用 Anthropic 兼容端点，支持真正的工具调用)
    try:
        provider = GLMAnthropicProvider(model="claude-sonnet-4-6")  # GLM Anthropic 端点使用 Claude 模型名
        print_success(f"已加载 GLM Anthropic Provider")
        print_info(f"端点: {provider.GLM_ANTHROPIC_URL}")
    except Exception as e:
        print_error(f"GLM Provider 初始化失败：{e}")
        return

    # 初始化 Agent 管理器
    agent_manager = AgentManager(provider)
    cmd_handler = CommandHandler(agent_manager)

    # 显示欢迎界面
    clear_screen()
    print_header()

    print(f"{Colors.BOLD}欢迎使用 AGent GLM AI 模式！{Colors.ENDC}\n")
    print("本系统包含四个专业 Agent：")
    print("  1. 总编辑 - 协调专业团队（默认）")
    print("  2. 构思专家 - 世界观、人物、主题")
    print("  3. 大纲专家 - 章节规划、情节设计")
    print("  4. 写手 - 章节撰写、场景描写\n")
    print("总编辑可调度的专业子Agent：")
    print("  - world-builder (世界构建师)")
    print("  - character-designer (人物设定师)")
    print("  - theme-planner (主题策划师)")
    print("  - style-designer (风格设定师)")
    print("  - audience-analyzer (读者分析师)")
    print("  - plot-architect (情节架构师)\n")

    print_info(f"当前 Agent: {agent_manager.current_agent}")
    print_separator()

    # 进入对话循环
    try:
        chat_loop(agent_manager, cmd_handler)
    except Exception as e:
        print_error(f"系统错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
