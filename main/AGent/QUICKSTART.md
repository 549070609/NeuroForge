# AGent CLI 快速参考卡

## 🚀 快速启动（3 步）

```bash
cd main/AGent
python start.py        # 启动菜单 → 选择 1 (GLM AI 模式)
```

## 📋 常用命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/list` | 列出 Agent |
| `/switch <name>` | 切换 Agent |
| `/info` | 当前 Agent 信息 |
| `/history` | 查看历史 |
| `/debug` | **切换调试模式** ⭐ |
| `/save` | 保存对话 |
| `/quit` | 退出 |

## 🎭 三个 Agent

| Agent | 专长 | 使用场景 |
|-------|------|---------|
| **novel-ideation** | 构思专家 | 世界观、人物、主题 |
| **novel-outline** | 大纲专家 | 章节规划、情节设计 |
| **novel-writer** | 写手 | 章节撰写、场景描写 |

## 🔧 配置文件

**GLM 版**: `main/glm-provider/.env`
```env
GLM_API_KEY=your_key_here
GLM_MODEL=glm-4-flash
```

## 🔍 调试模式 ⭐

**默认开启**，显示完整的内部过程：
- ✅ 引擎初始化和配置
- ✅ 上下文管理（消息历史）
- ✅ API 请求详情（消息数、Token 估计）
- ✅ API 响应详情（停止原因、Token 使用）
- ✅ 工具执行过程
- ✅ 引擎迭代次数

**切换调试**：
```
/debug  # 开/关调试模式
```

**查看详情**: `DEBUG_GUIDE.md`

**测试调试功能**：
```bash
python test_debug.py
```

## 📂 文件说明

| 文件 | 说明 |
|------|------|
| **cli_glm.py** | ✅ GLM 版（推荐） |
| **setup_glm.py** | 配置向导 |
| **start.py** | 启动菜单 |
| **verify.py** | 系统验证 |
| **test_debug.py** | 调试功能测试 |

## 🧪 测试持续对话

```
你: 我想写一个关于 AI 的故事
Agent: 好的！AI 是个很有意思的主题...

你: 刚才我说的是什么主题？
Agent: 你刚才提到想写一个关于 AI 的故事...
       ↑ ✅ 记住了！
```

## 🔍 调试输出示例

```
[DEBUG 14:30:25.123] [开始处理]
    用户消息长度: 10

[DEBUG 14:30:25.124] [上下文管理器]
    当前消息数: 4

[DEBUG 14:30:25.125] [API 请求]
    消息数: 6
    估计 tokens: ~180

[DEBUG 14:30:27.456] [API 响应]
    停止原因: end_turn
    Token 使用:
      输入: 156
      输出: 89
```

## ⚡ 故障排除

| 问题 | 解决 |
|------|------|
| 导入失败 | `cd main/glm-provider && pip install -r requirements.txt` |
| API Key 未配置 | `python setup_glm.py` |
| 无法持续对话 | 使用 `cli_glm.py`（不是 `cli.py`） |
| 想看内部过程 | 使用 `/debug` 开启调试模式 |

## 📞 获取帮助

- 📖 完整文档：`SOLUTION.md`
- 📖 GLM 指南：`README_GLM.md`
- 📖 调试说明：`DEBUG_GUIDE.md` ⭐
- 🔍 系统验证：`python verify.py`
- 🧪 调试测试：`python test_debug.py`

---

**记住**：
1. 使用 `cli_glm.py`，不是 `cli.py`！
2. 调试模式默认开启，随时用 `/debug` 切换
3. 查看完整内部过程，用 `DEBUG_GUIDE.md`
