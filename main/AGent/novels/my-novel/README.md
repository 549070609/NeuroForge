# 示例小说项目：时空裂隙

这是一个示例小说项目，用于测试多 Agent 协作系统。

## 项目信息

- **项目名**：my-sci-fi-novel
- **类型**：科幻小说
- **主题**：时间旅行、平行宇宙
- **章节数**：10章（规划）

## 工作流程

### 阶段 1: 构思（Ideation）

**负责 Agent**：novel-ideation
**输出目录**：`ideation/`

待生成文件：
- [ ] `world-building.md` - 世界观设定
- [ ] `characters.md` - 主要人物设定
- [ ] `themes.md` - 核心主题阐述
- [ ] `ideas.md` - 创意笔记

### 阶段 2: 大纲（Outline）

**负责 Agent**：novel-outline
**输出目录**：`outline/`

待生成文件：
- [ ] `chapter-outline.md` - 章节大纲
- [ ] `plot-structure.md` - 情节结构
- [ ] `timeline.md` - 时间线
- [ ] `key-events.md` - 关键事件

### 阶段 3: 写作（Chapters）

**负责 Agent**：novel-writer
**输出目录**：`chapters/`

待生成文件：
- [ ] `chapter-01.md` - 第1章：裂隙初现
- [ ] `chapter-02.md` - 第2章：时间漩涡
- [ ] ...更多章节

## 使用方法

### 1. 运行构思专家

```python
from pyagentforge.building import AgentLoader, AgentFactory

factory = AgentFactory(...)
loader = AgentLoader(factory)
loader.load_directory("agents/")

ideation = factory.create_from_name("novel-ideation")

# 执行任务
result = ideation.run(
    "为科幻小说《时空裂隙》创建构思，"
    "主题是时间旅行和平行宇宙，"
    "需要详细的世界观设定和主要人物设定"
)
```

### 2. 运行大纲专家

```python
outline = factory.create_from_name("novel-outline")

result = outline.run(
    "基于已完成的构思，创建10章的大纲，"
    "使用三幕结构，确保情节紧凑有张力"
)
```

### 3. 运行写手

```python
writer = factory.create_from_name("novel-writer")

# 逐章写作
for chapter_num in range(1, 11):
    result = writer.run(
        f"根据大纲撰写第{chapter_num}章，"
        f"注重场景描写和对话，"
        f"保持与前文的一致性"
    )
```

## 预期成果

### 世界观设定（示例）

```
时间：近未来 2150年
地点：地球 + 平行宇宙
核心设定：
- 科学家发现了时间裂隙现象
- 时间裂隙连接不同平行宇宙
- 通过裂隙可以穿越到平行世界
- 但存在蝴蝶效应和因果悖论
```

### 主要人物（示例）

```
1. 李明轩（主角）
   - 身份：量子物理学家
   - 性格：执着、好奇、理想主义
   - 目标：理解和控制时间裂隙

2. 艾琳（平行世界的自己）
   - 身份：另一个宇宙的李明轩（女性）
   - 性格：务实、冷静、经验丰富
   - 冲突：两个自我的对话与碰撞

3. 张教授（导师）
   - 身份：资深科学家
   - 作用：指引和警告
   - 秘密：曾试图穿越但失败
```

### 章节大纲（示例）

```
第一幕（1-3章）：发现
- 第1章：裂隙初现
- 第2章：第一次穿越
- 第3章：平行世界的自己

第二幕（4-7章）：探索与冲突
- 第4章：时间悖论
- 第5章：蝴蝶效应
- 第6章：抉择
- 第7章：两个世界的碰撞

第三幕（8-10章）：高潮与结局
- 第8章：裂隙失控
- 第9章：终极选择
- 第10章：新的开始
```

## 注意事项

1. **一致性**：写手会记住前文，确保人物和情节一致
2. **依赖关系**：必须按顺序执行（构思→大纲→写作）
3. **创造性**：每个 Agent 有不同的温度设置以匹配其职责
4. **持久化**：写手使用持久化会话，可以跨章节记忆

## 文件命名规范

```
ideation/
  - world-building.md     # 世界观
  - characters.md         # 人物
  - themes.md            # 主题
  - ideas.md             # 创意笔记

outline/
  - chapter-outline.md    # 章节大纲
  - plot-structure.md     # 情节结构
  - timeline.md          # 时间线
  - key-events.md        # 关键事件

chapters/
  - chapter-01.md        # 第1章
  - chapter-02.md        # 第2章
  - ...
```

---

**状态**：示例项目
**创建日期**：2026-02-20
