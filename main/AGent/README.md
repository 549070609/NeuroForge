# 小说创作多 Agent 系统

基于 **PyAgentForge Agent 构建层** 实现的多 Agent 协作小说创作系统。

## 🎯 系统概述

本系统使用三个专业化的 Agent 协作完成小说创作：

1. **构思专家 (Novel Ideation Agent)** - 负责创意生成、世界观构建、人物设定
2. **大纲专家 (Novel Outline Agent)** - 负责章节规划、情节设计、节奏控制
3. **写手 (Novel Writer Agent)** - 负责章节撰写、场景描写、对话创作

## 🏗️ 系统架构

```
┌─────────────────┐
│ novel-ideation  │ (构思专家)
│ - 世界观构建    │
│ - 人物设定      │
│ - 主题确定      │
└────────┬────────┘
         │ 输出: ideation/
         ↓
┌─────────────────┐
│ novel-outline   │ (大纲专家)
│ - 章节规划      │
│ - 情节设计      │
│ - 节奏控制      │
└────────┬────────┘
         │ 输出: outline/
         ↓
┌─────────────────┐
│ novel-writer    │ (写手)
│ - 章节撰写      │
│ - 场景描写      │
│ - 对话创作      │
└─────────────────┘
         │
         ↓ 输出: chapters/
┌─────────────────┐
│  完整小说作品   │
└─────────────────┘
```

## 📁 目录结构

```
AGent/
├── agents/                    # Agent 定义文件
│   ├── ideation.yaml         # 构思专家 (YAML 格式)
│   ├── outline.json          # 大纲专家 (JSON 格式)
│   └── writer.py             # 写手 (Python 格式)
│
├── novels/                    # 小说工作区
│   └── my-novel/             # 示例小说项目
│       ├── ideation/         # 构思文档
│       │   ├── world-building.md
│       │   ├── characters.md
│       │   └── themes.md
│       ├── outline/          # 大纲文档
│       │   ├── chapter-outline.md
│       │   └── plot-structure.md
│       └── chapters/         # 章节正文
│           ├── chapter-01.md
│           └── chapter-02.md
│
├── builder_demo.py           # Builder 使用示例
├── loader_demo.py            # Loader 使用示例
├── workflow_demo.py          # 完整工作流示例
├── cli.py                    # 🆕 CLI 交互界面
├── start.bat                 # 🆕 Windows 启动脚本
├── start.sh                  # 🆕 Linux/Mac 启动脚本
├── CLI使用指南.md            # 🆕 CLI 使用文档
└── README.md                 # 本文档
```

## 🚀 快速开始

### 0. 启动前检查（如果遇到问题）

**如果启动后闪退，请按顺序执行：**

1. **运行基础测试**：双击 `test_basic.bat`
2. **安装依赖**：
   ```bash
   cd ..\pyagentforge
   pip install -e .
   ```
3. **查看诊断文档**：[启动问题诊断.md](启动问题诊断.md)

### 1. 环境准备

确保已安装 PyAgentForge：

```bash
cd main/pyagentforge
pip install -e .
```

### 2. 运行示例

#### 🎮 方式 1: CLI 交互界面（推荐）

**最简单的方式测试系统！**

```bash
cd main/AGent
python cli.py
```

或双击运行 `start.bat` (Windows)

**功能**：
- ✅ 可视化 Agent 选择
- ✅ 实时对话交互
- ✅ 命令系统（/help, /list, /switch 等）
- ✅ 完整工作流执行
- ✅ 对话记录保存

📖 详细说明请查看 [CLI使用指南.md](CLI使用指南.md)

#### 方式 2: 运行演示脚本

##### Builder 使用示例

展示如何使用流畅 API 创建 Agent：

```bash
cd main/AGent
python builder_demo.py
```

**演示内容**：
- ✅ 基础创建
- ✅ 依赖配置
- ✅ 高级配置（记忆、持久化）
- ✅ 继承功能
- ✅ 模板使用

#### Loader 使用示例

展示如何从文件加载 Agent：

```bash
python loader_demo.py
```

**演示内容**：
- ✅ 从 YAML 加载
- ✅ 从 JSON 加载
- ✅ 从 Python 加载
- ✅ 自动检测格式
- ✅ 加载整个目录
- ✅ 依赖解析
- ✅ 状态查询

#### 完整工作流示例

展示三个 Agent 的协作：

```bash
python workflow_demo.py
```

**演示内容**：
- ✅ 加载所有 Agent
- ✅ 解析依赖关系
- ✅ 创建实例
- ✅ 配置概览
- ✅ 工作流执行
- ✅ 协作关系可视化
- ✅ Registry 查询

## 📋 Agent 详细说明

### 1. 构思专家 (novel-ideation)

**文件**：`agents/ideation.yaml` (YAML 格式)

**职责**：
- 发掘独特的小说创意和主题
- 构建引人入胜的世界观
- 设计深度的人物角色
- 确定故事的核心冲突

**配置特点**：
- **温度**：0.9（高创意性）
- **类别**：PLANNING
- **成本**：MODERATE
- **依赖**：无（基础层）
- **输出**：`novels/{project}/ideation/`

**使用场景**：
```
"为科幻小说创建世界观和人物设定"
"头脑风暴一个奇幻小说的创意"
"确定小说的主题和核心冲突"
```

### 2. 大纲专家 (novel-outline)

**文件**：`agents/outline.json` (JSON 格式)

**职责**：
- 基于构思创建详细章节大纲
- 设计情节起承转合
- 规划故事节奏和高潮
- 确保逻辑一致性

**配置特点**：
- **温度**：0.7（结构化思维）
- **类别**：PLANNING
- **成本**：MODERATE
- **依赖**：`novel-ideation`
- **输出**：`novels/{project}/outline/`

**使用场景**：
```
"基于构思创建10章大纲"
"设计三幕结构的情节"
"规划故事的时间线"
```

### 3. 写手 (novel-writer)

**文件**：`agents/writer.py` (Python 格式)

**职责**：
- 根据大纲撰写章节正文
- 创作生动的场景描写
- 编写自然的对话
- 营造氛围和情感

**配置特点**：
- **温度**：0.85（创意写作）
- **最大 Token**：8192（长篇内容）
- **类别**：CODING
- **成本**：EXPENSIVE
- **依赖**：`novel-outline`
- **记忆**：150 条消息，持久化会话
- **输出**：`novels/{project}/chapters/`

**使用场景**：
```
"撰写第1章：裂隙初现"
"创作一个紧张的场景"
"编写两个角色的对话"
```

## 🔧 核心功能展示

### 1. 多格式支持

本系统使用三种格式定义 Agent，展示 AgentLoader 的多格式能力：

| Agent | 格式 | 文件 | 优势 |
|-------|------|------|------|
| 构思专家 | YAML | `ideation.yaml` | 可读性好，适合手写 |
| 大纲专家 | JSON | `outline.json` | 易于程序生成 |
| 写手 | Python | `writer.py` | 最灵活，可包含复杂逻辑 |

### 2. 依赖管理

展示 Agent 之间的依赖关系：

```python
# 依赖链
novel-ideation (无依赖)
    ↓
novel-outline (requires: ["novel-ideation"])
    ↓
novel-writer (requires: ["novel-outline"])

# 自动解析加载顺序
load_order = loader.resolve_dependencies([
    "novel-writer",
    "novel-ideation",
    "novel-outline"
])
# 返回: ["novel-ideation", "novel-outline", "novel-writer"]
```

### 3. 智能发现

使用 Registry 的增强查询功能：

```python
# 按标签查询
novel_agents = registry.find_by_tags(["novel"])

# 按能力查询
write_agents = registry.find_by_capability("write")

# 智能匹配
best_agent = registry.find_best_for_task("我需要构思一个科幻小说")
# 返回: novel-ideation
```

### 4. 流畅 API

使用 AgentBuilder 快速创建：

```python
schema = (AgentBuilder()
    .with_name("custom-writer")
    .with_description("自定义写手")
    .with_model("claude-sonnet-4-20250514")
    .with_temperature(0.85)
    .add_tools(["read", "write"])
    .with_prompt("你是一位专业写手...")
    .requires(["novel-outline"])
    .build_and_register())
```

## 📊 配置对比

| Agent | 温度 | 最大Token | 成本 | 依赖 | 持久化 |
|-------|------|----------|------|------|--------|
| 构思专家 | 0.9 | 4096 | MODERATE | 无 | ❌ |
| 大纲专家 | 0.7 | 4096 | MODERATE | ideation | ❌ |
| 写手 | 0.85 | 8192 | EXPENSIVE | outline | ✅ |

## 💡 使用建议

### 1. 创作流程

```
1. 运行构思专家
   → 输出：世界设定、人物卡、主题阐述

2. 运行大纲专家
   → 输出：章节大纲、情节图、时间线

3. 逐章运行写手
   → 输出：章节正文
```

### 2. 温度调优

- **构思阶段**：使用高温度 (0.9) 激发创意
- **大纲阶段**：使用中等温度 (0.7) 保持结构
- **写作阶段**：使用中高温度 (0.85) 平衡创意和连贯

### 3. 持久化

写手使用持久化会话，可以：
- 记住前文内容
- 保持人物一致性
- 维持情节连贯性

## 🎯 测试目标

本系统用于测试 Agent 构建层的以下功能：

- [x] AgentBuilder 流畅 API 易用性
- [x] AgentSchema 声明式定义清晰性
- [x] AgentFactory 实例创建正确性
- [x] AgentLoader 多格式加载可靠性
- [x] 依赖解析功能准确性
- [x] Registry 查询功能有效性
- [x] 多 Agent 协作可行性

## 📖 相关文档

- [Agent 构建层实现完成报告](../../Docs/plan/AGent构建层/Agent构建层-实现完成报告.md)
- [Agent 构建层产品设计](../../Docs/plan/AGent构建层/Agent构建层-产品设计文档.md)
- [PyAgentForge API 文档](../../Docs/Apis/README.md)

## 🤝 贡献

欢迎提出改进建议或添加更多 Agent 类型！

---

**创建日期**：2026-02-20
**基于**：PyAgentForge Agent 构建层
**版本**：1.0.0
