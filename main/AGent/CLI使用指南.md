# CLI 使用指南

## 🚀 快速开始

### Windows 用户

双击运行 `start.bat` 或在命令行中执行：

```bash
python cli.py
```

### Linux/Mac 用户

```bash
chmod +x start.sh
./start.sh
```

或直接运行：

```bash
python3 cli.py
```

## 📖 使用说明

### 界面说明

```
============================================================
  📚 小说创作 Agent 系统 - CLI 交互界面
============================================================

当前 Agent: novel-ideation
状态: 就绪
──────────────────────────────────────────────────────────

[novel-ideation] > 输入消息...
```

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/list` | 列出所有 Agent | `/list` |
| `/switch` | 切换 Agent | `/switch novel-writer` |
| `/info` | 显示当前 Agent 信息 | `/info` |
| `/workflow` | 运行完整工作流 | `/workflow` |
| `/clear` | 清空屏幕 | `/clear` |
| `/save` | 保存对话记录 | `/save` |
| `/quit` | 退出系统 | `/quit` |

### 使用流程

#### 1. 查看 Agent 列表

```
[novel-ideation] > /list

可用 Agent：

→ 1.novel-ideation
    构思专家 - 负责世界观构建、人物设定、主题确定
    类别：planning

  2.novel-outline
    大纲专家 - 负责章节规划、情节设计、节奏控制
    类别：planning

  3.novel-writer
    写手 - 负责章节撰写、场景描写、对话创作
    类别：coding
```

#### 2. 切换 Agent

```
[novel-ideation] > /switch novel-outline
✅ 已切换到：novel-outline
ℹ️  描述：大纲专家 - 负责章节规划、情节设计、节奏控制

[novel-outline] > /switch 3
✅ 已切换到：novel-writer
ℹ️  描述：写手 - 负责章节撰写、场景描写、对话创作
```

#### 3. 与 Agent 对话

**示例 1：构思小说**

```
[novel-ideation] > 构思一个科幻小说，主题是时间旅行

[14:30:25] 你:
构思一个科幻小说，主题是时间旅行

[14:30:26] novel-ideation:
好的！让我来帮你构思一个小说创意。

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

你觉得这个构思如何？需要我调整哪些方面？
```

**示例 2：创建大纲**

```
[novel-outline] > 基于构思创建5章的大纲

[14:31:10] novel-outline:
基于构思文档，我来创建章节大纲。

【三幕结构规划】

第一幕：发现（1-2章）
- 第1章：裂隙初现
  * 李明轩发现异常数据
  * 首次观测到时间裂隙

- 第2章：首次穿越
  * 冒险进入裂隙
  * 来到平行世界

...
```

**示例 3：撰写章节**

```
[novel-writer] > 撰写第1章：裂隙初现

[14:32:00] novel-writer:
好的，让我来撰写这一章。

【第1章：裂隙初现】

深夜，量子物理研究所的实验室里，李明轩盯着屏幕上的数据...

【第1章完】

这一章的基调如何？需要调整哪些描写？
```

#### 4. 运行完整工作流

```
[novel-ideation] > /workflow

开始执行小说创作工作流...
──────────────────────────────────────────────────────────
ℹ️  阶段 1/3: 构思专家生成创意...
[14:35:01] novel-ideation:
好的！让我来帮你构思...

ℹ️  阶段 2/3: 大纲专家创建大纲...
[14:35:02] novel-outline:
基于构思文档，我来创建章节大纲...

ℹ️  阶段 3/3: 写手撰写第一章...
[14:35:03] novel-writer:
好的，让我来撰写这一章...

──────────────────────────────────────────────────────────
✅ 工作流执行完成！
ℹ️  这是模拟执行。实际使用需要配置 AI Provider。
```

#### 5. 保存对话

```
[novel-writer] > /save
✅ 对话记录已保存：chat_log_20260220_143500.txt
```

#### 6. 退出系统

```
[novel-writer] > /quit

👋 感谢使用小说创作 Agent 系统！
```

## 💡 使用技巧

### 1. 快速切换 Agent

支持两种方式：

- **名称切换**：`/switch novel-ideation`
- **数字切换**：`/switch 1`（按列表顺序）

### 2. 查看当前状态

随时输入 `/info` 查看当前 Agent 信息

### 3. 清屏重置

输入 `/clear` 清空屏幕，重新开始

### 4. 对话历史

Agent 会记住之前的对话内容（在当前会话中）

### 5. 多步工作流

推荐顺序：
1. 先用 **构思专家** 完成世界观和人物设定
2. 再用 **大纲专家** 创建章节大纲
3. 最后用 **写手** 逐章撰写

## 🎯 测试场景

### 场景 1：测试构思专家

```
/switch novel-ideation
构思一个悬疑小说
设计主要人物
确定核心冲突
```

### 场景 2：测试大纲专家

```
/switch novel-outline
创建10章的大纲
设计高潮部分
规划伏笔
```

### 场景 3：测试写手

```
/switch novel-writer
撰写第1章
创作一段对话
描写一个场景
```

### 场景 4：测试完整流程

```
/workflow
```

## ⚙️ 配置说明

### 模拟模式

当前 CLI 使用**模拟模式**，Agent 会返回预设的回复，无需配置真实的 AI Provider。

### 真实模式（需要配置）

如果要使用真实的 AI，需要：

1. 在 `cli.py` 中导入真实的 AgentFactory
2. 配置 API 密钥
3. 替换 MockAgentEngine

```python
# 示例：使用真实 Agent
from pyagentforge.building import AgentLoader, AgentFactory
from pyagentforge.tools.registry import ToolRegistry

# 创建真实的 Factory
tool_registry = ToolRegistry()
provider_factory = create_anthropic_provider  # 需要实现

factory = AgentFactory(
    provider_factory=provider_factory,
    tool_registry=tool_registry,
)

# 加载真实 Agent
loader = AgentLoader(factory)
loader.load_directory("agents/")

# 获取真实引擎
engine = factory.create_from_name("novel-ideation")
```

## 🐛 常见问题

### Q1: 颜色显示不正常？

**A:** Windows 用户确保终端支持 ANSI 颜色。如果颜色乱码，可以在 `cli.py` 中禁用颜色：

```python
Colors.disable()  # 在文件开头添加
```

### Q2: 无法切换 Agent？

**A:** 使用 `/list` 查看正确的 Agent 名称，或使用数字索引

### Q3: 对话记录保存在哪里？

**A:** 保存在当前目录，文件名格式：`chat_log_YYYYMMDD_HHMMSS.txt`

### Q4: 如何使用真实的 AI？

**A:** 需要配置 API 密钥和真实的 AgentFactory，参考上面的"真实模式"说明

## 📊 系统状态

- ✅ 三个 Agent 可用
- ✅ 命令系统完整
- ✅ 对话功能正常
- ✅ 工作流可执行
- ✅ 日志保存功能

## 📝 更新日志

- 2026-02-20: 初始版本发布
  - 实现基础 CLI 界面
  - 支持三个 Agent 切换
  - 支持命令系统
  - 支持工作流执行

## 📞 获取帮助

- 查看系统文档：`README.md`
- 查看实现总结：`实现总结.md`
- 查看增强方案：`增强方案.md`

---

**版本**: 1.0.0
**更新日期**: 2026-02-20
