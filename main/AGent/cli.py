#!/usr/bin/env python
"""
小说创作 Agent 系统 - CLI 交互界面

提供命令行交互方式来测试和使用 Agent 系统
"""

import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))

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
    os.system('color')  # 启用 Windows ANSI 支持


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印头部"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKCYAN}  📚 小说创作 Agent 系统 - CLI 交互界面{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_separator():
    """打印分隔线"""
    print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")


def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")


def print_warning(message: str):
    """打印警告消息"""
    print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")


def print_info(message: str):
    """打印信息"""
    print(f"{Colors.OKBLUE}ℹ️  {message}{Colors.ENDC}")


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
    def __init__(self, name: str, description: str, category: str):
        self.name = name
        self.description = description
        self.category = category


class MockAgentEngine:
    """模拟 Agent 引擎（用于测试）"""

    def __init__(self, agent_info: AgentInfo):
        self.info = agent_info
        self.history = []

    def run(self, message: str) -> str:
        """运行 Agent（模拟回复）"""
        self.history.append({"role": "user", "content": message})

        # 模拟智能回复
        response = self._generate_mock_response(message)
        self.history.append({"role": "assistant", "content": response})

        return response

    def _generate_mock_response(self, message: str) -> str:
        """生成模拟回复"""
        msg_lower = message.lower()

        if self.info.name == "novel-ideation":
            if any(kw in msg_lower for kw in ["构思", "创意", "世界观"]):
                return f"""好的！让我来帮你构思一个小说创意。

【世界设定】
- 时代背景：近未来 2150 年
- 核心设定：人类发现了通往平行宇宙的时间裂隙
- 世界观特点：科技发达但面临资源危机

【主要人物】
- 主角：李明轩，量子物理学家，执着于理解时间裂隙
- 配角：艾琳，来自平行世界的另一个自己

【核心冲突】
- 时间裂隙正在扩大，威胁两个宇宙的存在
- 主角必须在两个世界之间做出选择

你觉得这个构思如何？需要我调整哪些方面？"""

            elif any(kw in msg_lower for kw in ["人物", "角色"]):
                return f"""让我来设计小说的主要人物。

【主角 - 李明轩】
- 年龄：35岁
- 职业：量子物理学家
- 性格：执着、好奇、理想主义
- 目标：理解和控制时间裂隙
- 内心冲突：科学追求 vs 道德责任

【重要配角 - 艾琳】
- 身份：平行世界的李明轩（女性版本）
- 性格：务实、冷静、经验丰富
- 作用：提供另一个视角，两个自我的对话

【反派 - 张教授】
- 身份：李明轩的导师
- 动机：想要利用时间裂隙获取力量
- 秘密：曾尝试穿越但失败，留下了创伤

还需要更多人物细节吗？"""

            else:
                return f"【构思专家】收到你的消息：{message[:100]}...\n\n我准备好帮你构思小说了！你可以问我关于世界观、人物设定或主题的问题。"

        elif self.info.name == "novel-outline":
            if any(kw in msg_lower for kw in ["大纲", "章节", "结构"]):
                return f"""基于构思文档，我来创建章节大纲。

【三幕结构规划】

第一幕：发现（1-3章）
- 第1章：裂隙初现
  * 李明轩发现异常数据
  * 首次观测到时间裂隙
  * 激起强烈好奇心

- 第2章：首次穿越
  * 冒险进入裂隙
  * 来到平行世界
  * 遇见艾琳

- 第3章：两个世界
  * 对比两个世界的差异
  * 发现裂隙的危险性
  * 张教授的警告

第二幕：探索与冲突（4-7章）
- 第4章：时间悖论
- 第5章：蝴蝶效应
- 第6章：抉择
- 第7章：两个世界的碰撞

第三幕：高潮与结局（8-10章）
- 第8章：裂隙失控
- 第9章：终极选择
- 第10章：新的开始

需要我详细展开某个章节吗？"""

            else:
                return f"【大纲专家】收到你的消息：{message[:100]}...\n\n我已经准备好创建章节大纲了！告诉我你需要多少章，以及想要什么样的结构。"

        elif self.info.name == "novel-writer":
            if any(kw in msg_lower for kw in ["撰写", "写", "第"]):
                return f"""好的，让我来撰写这一章。

【第1章：裂隙初现】

深夜，量子物理研究所的实验室里，李明轩盯着屏幕上的数据，眉头紧锁。

"这不可能..."他喃喃自语，手指在键盘上飞快地敲击。

屏幕上的曲线违背了所有已知的物理定律——一个能量读数在负时间和正时间之间疯狂跳动，仿佛...仿佛有什么东西撕裂了时间的帷幕。

他拿起电话，拨通了张教授的号码。

"教授，您必须来看看这个。"

"现在？明轩，现在是凌晨三点。"

"我知道，但...我发现了一些东西。一些可能改变一切的东西。"

电话那头沉默了几秒。

"我马上到。"

李明轩放下电话，重新看向屏幕。那个异常的能量峰值正在缓慢增长，就像某种巨大存在的呼吸。

他不知道的是，这个发现将引领他走向一个跨越平行宇宙的旅程，也将迫使他面对最艰难的选择...

---

【第1章完】

这一章的基调如何？需要调整哪些描写？"""

            else:
                return f"【写手】收到你的消息：{message[:100]}...\n\n我已经准备好撰写章节了！告诉我要写第几章，以及有什么特殊要求。"

        else:
            return f"【{self.info.name}】收到消息：{message[:100]}...\n\n我准备好协助你了！"


class AgentManager:
    """Agent 管理器"""

    def __init__(self):
        self.agents: dict[str, AgentInfo] = {}
        self.engines: dict[str, MockAgentEngine] = {}
        self.current_agent: Optional[str] = None
        self._load_agents()

    def _load_agents(self):
        """加载 Agent"""
        # 预定义的 Agent
        agents_data = [
            AgentInfo(
                name="novel-ideation",
                description="构思专家 - 负责世界观构建、人物设定、主题确定",
                category="planning"
            ),
            AgentInfo(
                name="novel-outline",
                description="大纲专家 - 负责章节规划、情节设计、节奏控制",
                category="planning"
            ),
            AgentInfo(
                name="novel-writer",
                description="写手 - 负责章节撰写、场景描写、对话创作",
                category="coding"
            ),
        ]

        for agent in agents_data:
            self.agents[agent.name] = agent
            self.engines[agent.name] = MockAgentEngine(agent)

        # 默认选择第一个
        if self.agents:
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

    def get_engine(self, name: str) -> Optional[MockAgentEngine]:
        """获取 Agent 引擎"""
        return self.engines.get(name)

    def get_current_engine(self) -> Optional[MockAgentEngine]:
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
            "/workflow": self.cmd_workflow,
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
        print(f"  {Colors.OKCYAN}/workflow{Colors.ENDC}  - 运行完整工作流")
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

    def cmd_workflow(self, args: str) -> bool:
        """运行完整工作流"""
        print(f"\n{Colors.BOLD}开始执行小说创作工作流...{Colors.ENDC}\n")
        print_separator()

        # 阶段 1: 构思
        print_info("阶段 1/3: 构思专家生成创意...")
        ideation_engine = self.agent_manager.get_engine("novel-ideation")
        if ideation_engine:
            result1 = ideation_engine.run("构思一个科幻小说，主题是时间旅行")
            print_agent_message("构思专家", result1[:200] + "...\n")

        # 阶段 2: 大纲
        print_info("阶段 2/3: 大纲专家创建大纲...")
        outline_engine = self.agent_manager.get_engine("novel-outline")
        if outline_engine:
            result2 = outline_engine.run("基于构思创建5章的大纲")
            print_agent_message("大纲专家", result2[:200] + "...\n")

        # 阶段 3: 写作
        print_info("阶段 3/3: 写手撰写第一章...")
        writer_engine = self.agent_manager.get_engine("novel-writer")
        if writer_engine:
            result3 = writer_engine.run("撰写第1章：裂隙初现")
            print_agent_message("写手", result3[:200] + "...\n")

        print_separator()
        print_success("工作流执行完成！")
        print_info("这是模拟执行。实际使用需要配置 AI Provider。\n")

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
                if engine and engine.history:
                    for msg in engine.history:
                        role = "用户" if msg["role"] == "user" else "Agent"
                        f.write(f"{role}: {msg['content']}\n\n")

            print_success(f"对话记录已保存：{filename}")
        except Exception as e:
            print_error(f"保存失败：{e}")

        return True

    def cmd_quit(self, args: str) -> bool:
        """退出"""
        print(f"\n{Colors.OKBLUE}👋 感谢使用小说创作 Agent 系统！{Colors.ENDC}\n")
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


def main():
    """主函数"""
    # 初始化
    agent_manager = AgentManager()
    cmd_handler = CommandHandler(agent_manager)

    # 显示欢迎界面
    clear_screen()
    print_header()

    print(f"{Colors.BOLD}欢迎使用小说创作 Agent 系统！{Colors.ENDC}\n")
    print("本系统包含三个专业 Agent：")
    print("  1. 构思专家 - 世界观、人物、主题")
    print("  2. 大纲专家 - 章节规划、情节设计")
    print("  3. 写手 - 章节撰写、场景描写\n")

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
