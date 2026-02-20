# AGent + GLM 快速开始指南

## 🎯 快速启动（3 步）

### 步骤 1: 配置 GLM API Key

```bash
cd main/AGent
python setup_glm.py
```

按提示输入：
- GLM API Key（从 https://open.bigmodel.cn/ 获取）
- 选择模型（推荐 glm-4-flash）

### 步骤 2: 启动 CLI

```bash
python start.py
```

选择菜单 `1. GLM AI 模式`

或者直接运行：

```bash
python cli_glm.py
```

### 步骤 3: 开始对话

```
[novel-ideation] > 你好，我想写一个科幻小说

Agent: 你好！很高兴帮你构思科幻小说...
```

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `cli_glm.py` | ✅ **GLM 版 CLI**（推荐） |
| `setup_glm.py` | GLM 配置向导 |
| `start.py` | 启动菜单 |
| `cli_real.py` | 通用版（支持 Anthropic/Mock） |
| `cli.py` | 原始版本（不推荐） |

## 🔧 配置文件位置

GLM 配置文件：`main/glm-provider/.env`

```env
# GLM Provider 配置

GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-4-flash
```

## ✨ 功能特性

### ✅ 持续对话

```python
# 原始 cli.py（❌ 不支持）
class MockAgentEngine:
    def run(self, message: str):
        # 只记录历史，不传递给模型
        self.history.append(...)
        response = self._generate_mock_response(message)  # 独立生成

# 新版 cli_glm.py（✅ 支持）
class GLMAgentEngine:
    def run(self, message: str):
        # AgentEngine 自动管理历史
        return self.engine.run(message)  # 包含完整上下文
```

### ✅ 三个专业 Agent

1. **novel-ideation** - 构思专家
   - 世界观构建
   - 人物设定
   - 主题确定

2. **novel-outline** - 大纲专家
   - 章节规划
   - 情节设计
   - 节奏控制

3. **novel-writer** - 写手
   - 章节撰写
   - 场景描写
   - 对话创作

### ✅ 完整命令系统

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/list` | 列出所有 Agent |
| `/switch <name>` | 切换 Agent |
| `/info` | 显示当前 Agent 信息 |
| `/history` | 显示对话历史 |
| `/clear` | 清屏 |
| `/save` | 保存对话记录 |
| `/quit` | 退出 |

## 🧪 测试持续对话

### 测试 1: 基本记忆

```
[novel-ideation] > 我想写一个关于人工智能的故事

Agent: 好的！人工智能是个很有意思的主题...
       你更偏向哪种风格？硬科幻、软科幻？

[novel-ideation] > 刚才我说的是什么主题？

Agent: 你刚才提到想写一个关于人工智能的故事...
       ✅ 记住了之前的对话
```

### 测试 2: 多轮构建

```
[novel-ideation] > 主角叫李明

Agent: 好的，主角叫李明...

[novel-ideation] > 他是个科学家

Agent: 了解，李明是个科学家...

[novel-ideation] > 总结一下主角的信息

Agent: 根据我们的讨论，主角李明是一名科学家...
       ✅ 整合了多轮对话的信息
```

### 测试 3: 查看历史

```
[novel-ideation] > /history

对话历史（共 6 条）：

[1] 用户:
我想写一个关于人工智能的故事

[2] Agent:
好的！人工智能是个很有意思的主题...

[3] 用户:
主角叫李明

[4] Agent:
好的，主角叫李明...

[5] 用户:
他是个科学家

[6] Agent:
了解，李明是个科学家...
```

## 🆚 对比：原版 vs GLM 版

| 特性 | cli.py (原版) | cli_glm.py (GLM 版) |
|------|--------------|---------------------|
| 引擎 | MockAgentEngine | AgentEngine + GLMProvider |
| 对话历史 | ❌ 只记录不使用 | ✅ 自动传递给模型 |
| 上下文管理 | ❌ 无 | ✅ ContextManager |
| 真实 API | ❌ 不支持 | ✅ GLM API |
| 持续对话 | ❌ 不支持 | ✅ 完整支持 |
| 记忆能力 | ❌ 无 | ✅ 完整上下文 |
| 模型 | 无 | GLM-4 系列 |

## 🐛 常见问题

### Q1: 提示 "GLMProvider 导入失败"

**原因**：缺少依赖或路径错误

**解决**：
```bash
cd main/glm-provider
pip install -r requirements.txt
```

### Q2: 提示 "GLM API Key 未配置"

**原因**：未配置环境变量

**解决**：
```bash
cd main/AGent
python setup_glm.py
```

或手动创建 `main/glm-provider/.env`：
```env
GLM_API_KEY=your_api_key_here
GLM_MODEL=glm-4-flash
```

### Q3: 切换 Agent 后历史丢失？

**答**：不会！每个 Agent 都有独立的 ContextManager，历史会保留。

### Q4: 如何获取 GLM API Key？

**步骤**：
1. 访问 https://open.bigmodel.cn/
2. 注册/登录账号
3. 在控制台获取 API Key

### Q5: 支持哪些 GLM 模型？

- `glm-4-flash` - 快速响应（推荐，默认）
- `glm-4-plus` - 增强能力
- `glm-4-air` - 性价比高
- `glm-4-long` - 长上下文
- `glm-4.7` - 最新版本

### Q6: 如何验证正在使用 GLM？

启动时会显示：
```
✅ 已加载 GLM Provider (模型: glm-4-flash)
```

## 📊 技术架构

```
cli_glm.py
    ↓
GLMAgentEngine
    ↓
AgentEngine (pyagentforge.kernel.engine)
    ↓
ContextManager (管理对话历史)
    ↓
GLMProvider (main/glm-provider/glm_provider.py)
    ↓
OpenAI SDK (兼容 GLM API)
    ↓
GLM API (https://open.bigmodel.cn/api/paas/v4)
```

## 🎓 学习路径

1. **入门**：运行 `python start.py` 体验基本功能
2. **配置**：运行 `python setup_glm.py` 配置 API Key
3. **实践**：使用三个 Agent 创作小说
4. **深入**：阅读源码理解 AgentEngine 工作原理

## 📝 下一步改进

- [ ] 流式输出（实时显示 AI 响应）
- [ ] 工具调用（集成 read/write/bash）
- [ ] 会话持久化（保存/加载会话）
- [ ] 多 Agent 协作（Agent 间通信）

## 🔗 相关资源

- [GLM API 文档](https://open.bigmodel.cn/dev/api)
- [PyAgentForge 框架](../pyagentforge/)
- [Claude Code 学习笔记](../../Docs/learn/02-Claude-Code-学习笔记/)

---

**现在就开始：**
```bash
cd main/AGent
python setup_glm.py  # 配置 API Key
python cli_glm.py    # 启动 CLI
```

**享受与 GLM 的持续对话吧！** 🚀
