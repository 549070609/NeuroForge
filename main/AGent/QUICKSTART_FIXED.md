# 快速启动指南 - AGent GLM

## ✅ 修复完成！

所有问题已修复，系统已通过验证。

## 🚀 立即启动

### 方式 1：直接启动（最快）
```bash
双击 start_glm.bat
```

### 方式 2：命令行启动
```bash
py cli_glm.py
```

### 方式 3：菜单启动
```bash
py start.py
# 选择 1. GLM AI 模式
```

## 📋 首次运行

如果是首次运行，需要先配置 GLM API Key：

```bash
py setup_glm.py
```

按提示输入：
- GLM API Key（从 https://open.bigmodel.cn/ 获取）
- 选择模型（推荐 `glm-4-flash`）

## 🎮 使用方法

启动后，你会看到提示符：

```
[novel-ideation] >
```

### 基本对话
直接输入消息与 Agent 对话：
```
[novel-ideation] > 你好，我想写一个科幻小说
```

### 可用命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/list` | 列出所有 Agent |
| `/switch novel-outline` | 切换到大纲专家 |
| `/info` | 显示当前 Agent 信息 |
| `/history` | 显示对话历史 |
| `/save` | 保存对话记录 |
| `/clear` | 清屏 |
| `/quit` | 退出 |

### 三个专业 Agent

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

## 🔧 故障排除

### 问题 1：提示 "未找到 GLM 配置文件"
**解决**：运行 `py setup_glm.py` 配置 API Key

### 问题 2：导入错误
**解决**：安装依赖
```bash
pip install openai python-dotenv pydantic
```

### 问题 3：API 调用失败
**解决**：检查 API Key 是否正确，网络是否通畅

## 📚 更多信息

- 详细修复说明：`GLM_FIX_SUMMARY.md`
- 使用指南：`README_GLM.md`
- 完整文档：`README.md`

## ✨ 享受创作！

---

**提示**：Agent 会记住对话历史，你可以持续深入讨论你的小说构思！
