"""
Passive Agent Handler

Simulates a reactive assistant agent that responds to user requests with
tool-augmented capabilities: code generation, code review, text writing,
text summarization, and format conversion.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any

TOOL_DEFINITIONS = {
    "code_generate": {
        "name": "code_generate",
        "description": "根据自然语言描述生成代码",
        "parameters": {"language": "string", "description": "string"},
    },
    "code_review": {
        "name": "code_review",
        "description": "分析代码质量并给出改进建议",
        "parameters": {"code": "string", "language": "string"},
    },
    "text_write": {
        "name": "text_write",
        "description": "撰写技术文档或文章",
        "parameters": {"topic": "string", "style": "string"},
    },
    "text_summarize": {
        "name": "text_summarize",
        "description": "对长文本进行精炼摘要",
        "parameters": {"text": "string", "max_length": "integer"},
    },
    "format_convert": {
        "name": "format_convert",
        "description": "在不同格式间转换内容",
        "parameters": {"content": "string", "from_format": "string", "to_format": "string"},
    },
}


def _detect_tool(message: str) -> str | None:
    """Detect which tool should be invoked based on message content."""
    msg = message.lower()
    if any(k in msg for k in ["写代码", "生成代码", "code", "编写", "实现", "函数", "class", "function"]):
        return "code_generate"
    if any(k in msg for k in ["审查", "review", "检查代码", "分析代码", "优化"]):
        return "code_review"
    if any(k in msg for k in ["写文档", "文档", "readme", "文章", "撰写", "write"]):
        return "text_write"
    if any(k in msg for k in ["摘要", "总结", "summary", "summarize", "概括"]):
        return "text_summarize"
    if any(k in msg for k in ["转换", "convert", "格式", "json", "yaml", "markdown"]):
        return "format_convert"
    return None


def _simulate_code_generate(message: str) -> dict[str, Any]:
    lang = "python"
    for l in ["javascript", "typescript", "go", "rust", "java", "c++"]:
        if l in message.lower():
            lang = l
            break

    code_samples = {
        "python": '''class TaskManager:
    """异步任务管理器，支持优先级队列和超时控制"""

    def __init__(self, max_workers: int = 4):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task] = []
        self._max_workers = max_workers
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self._max_workers)
        ]

    async def submit(self, priority: int, coro, timeout: float = 30.0):
        await self._queue.put((priority, timeout, coro))

    async def _worker(self, worker_id: int):
        while self._running:
            try:
                priority, timeout, coro = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

    async def shutdown(self) -> None:
        self._running = False
        await asyncio.gather(*self._workers, return_exceptions=True)''',
        "javascript": '''class EventEmitter {
  #listeners = new Map();
  #maxListeners = 10;

  on(event, handler) {
    if (!this.#listeners.has(event)) {
      this.#listeners.set(event, []);
    }
    const handlers = this.#listeners.get(event);
    if (handlers.length >= this.#maxListeners) {
      console.warn(`Max listeners (${this.#maxListeners}) reached for "${event}"`);
    }
    handlers.push(handler);
    return () => this.off(event, handler);
  }

  off(event, handler) {
    const handlers = this.#listeners.get(event) || [];
    const idx = handlers.indexOf(handler);
    if (idx !== -1) handlers.splice(idx, 1);
  }

  emit(event, ...args) {
    const handlers = this.#listeners.get(event) || [];
    handlers.forEach(h => h(...args));
  }

  once(event, handler) {
    const wrapper = (...args) => {
      this.off(event, wrapper);
      handler(...args);
    };
    return this.on(event, wrapper);
  }
}''',
    }

    code = code_samples.get(lang, code_samples["python"])

    return {
        "tool": "code_generate",
        "input": {"language": lang, "description": message},
        "output": {
            "language": lang,
            "code": code,
            "explanation": f"已生成 {lang} 代码，包含完整的类定义、错误处理和文档字符串。",
        },
    }


def _simulate_code_review(message: str) -> dict[str, Any]:
    return {
        "tool": "code_review",
        "input": {"code": message[:200], "language": "auto-detect"},
        "output": {
            "overall_score": "B+ (良好)",
            "issues": [
                {"severity": "WARNING", "line": 12, "message": "建议使用类型注解提高可读性"},
                {"severity": "INFO", "line": 25, "message": "可以使用列表推导式简化循环"},
                {"severity": "WARNING", "line": 38, "message": "异常处理过于宽泛，建议捕获具体异常"},
            ],
            "suggestions": [
                "添加 docstring 文档字符串",
                "考虑使用 dataclass 简化数据类",
                "添加单元测试覆盖核心逻辑",
            ],
            "security": "未发现安全漏洞",
        },
    }


def _simulate_text_write(message: str) -> dict[str, Any]:
    return {
        "tool": "text_write",
        "input": {"topic": message, "style": "technical"},
        "output": {
            "format": "markdown",
            "content": f"""# 技术文档

## 概述

本文档描述了基于 {message[:30]} 的系统设计方案。

## 架构设计

### 核心组件

| 组件 | 职责 | 技术栈 |
|------|------|--------|
| API Gateway | 请求路由和认证 | FastAPI |
| Agent Engine | 核心执行引擎 | Python 3.11+ |
| Tool Registry | 工具管理和调度 | Plugin Architecture |

### 数据流

1. 用户请求通过 API Gateway 进入系统
2. Agent Engine 解析意图并选择合适的工具
3. Tool Registry 调度工具执行
4. 结果经过后处理返回用户

## API 参考

```python
async def execute(task: str, context: dict = None) -> AgentResponse:
    \"\"\"执行 Agent 任务\"\"\"
    ...
```

## 部署指南

```bash
pip install -e ".[dev]"
uvicorn app:create_app --factory --reload
```
""",
            "word_count": 256,
        },
    }


def _simulate_text_summarize(message: str) -> dict[str, Any]:
    return {
        "tool": "text_summarize",
        "input": {"text": message[:100], "max_length": 100},
        "output": {
            "summary": "该文本主要讨论了系统架构设计，核心包括三个方面：(1) 模块化的插件体系，(2) 基于事件驱动的通信机制，(3) 可扩展的工具注册表。关键结论是采用分层架构可以有效降低耦合度。",
            "key_points": [
                "模块化插件体系",
                "事件驱动通信",
                "可扩展工具注册表",
                "分层架构降低耦合",
            ],
            "original_length": len(message),
            "compression_ratio": "75%",
        },
    }


def _simulate_format_convert(message: str) -> dict[str, Any]:
    return {
        "tool": "format_convert",
        "input": {"content": message[:100], "from_format": "text", "to_format": "json"},
        "output": {
            "converted": json.dumps(
                {
                    "title": "转换结果",
                    "content": message[:80],
                    "metadata": {
                        "source_format": "text",
                        "target_format": "json",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            "format": "json",
        },
    }


TOOL_SIMULATORS = {
    "code_generate": _simulate_code_generate,
    "code_review": _simulate_code_review,
    "text_write": _simulate_text_write,
    "text_summarize": _simulate_text_summarize,
    "format_convert": _simulate_format_convert,
}


async def handle_passive_message(message: str) -> list[dict[str, Any]]:
    """
    Process a user message through the passive agent pipeline.
    Returns a list of events (tool_call, tool_result, agent_reply) to stream back.
    """
    events: list[dict[str, Any]] = []
    tool_name = _detect_tool(message)

    if tool_name and tool_name in TOOL_SIMULATORS:
        events.append({
            "type": "thinking",
            "content": f"分析用户请求...检测到需要使用 {TOOL_DEFINITIONS[tool_name]['description']}",
        })

        await asyncio.sleep(0.3)

        events.append({
            "type": "tool_call",
            "tool": tool_name,
            "description": TOOL_DEFINITIONS[tool_name]["description"],
            "status": "executing",
        })

        await asyncio.sleep(0.5)

        result = TOOL_SIMULATORS[tool_name](message)

        events.append({
            "type": "tool_result",
            "tool": tool_name,
            "result": result["output"],
            "status": "completed",
        })

        reply_templates = {
            "code_generate": "已为您生成代码。代码包含完整的类定义和错误处理，您可以在右侧面板查看详细输出。如需调整，请告诉我具体的修改需求。",
            "code_review": "代码审查完成。整体评分 B+（良好），发现了几个可以改进的地方。详细的审查报告已展示在工具输出面板中。",
            "text_write": "文档已撰写完成。包含了架构设计、API 参考和部署指南等章节。您可以在右侧面板预览完整文档。",
            "text_summarize": "文本摘要已生成，压缩率 75%。提取了 4 个关键要点，详见工具输出面板。",
            "format_convert": "格式转换完成。已将内容转换为 JSON 格式，包含元数据标注。",
        }
        events.append({
            "type": "agent_reply",
            "content": reply_templates.get(tool_name, "任务已完成。"),
        })
    else:
        events.append({
            "type": "agent_reply",
            "content": _general_reply(message),
        })

    return events


def _general_reply(message: str) -> str:
    replies = [
        "你好！我是被动型通用助手。我可以帮你：\n\n"
        "- **生成代码** - 告诉我你需要什么功能\n"
        "- **审查代码** - 粘贴代码让我分析\n"
        "- **撰写文档** - 告诉我文档主题\n"
        "- **文本摘要** - 给我一段长文本\n"
        "- **格式转换** - 告诉我源格式和目标格式\n\n"
        "请输入你的需求，我会调用相应的工具来帮助你。",
    ]
    if any(k in message.lower() for k in ["你好", "hi", "hello", "帮助", "help"]):
        return replies[0]
    return (
        f"收到你的消息。如果你需要我帮忙处理具体任务，可以尝试：\n\n"
        f"- 输入「写一个 Python 排序函数」来生成代码\n"
        f"- 输入「审查这段代码」来进行代码审查\n"
        f"- 输入「写一份 API 文档」来撰写文档\n"
        f"- 输入「总结以下内容...」来生成摘要"
    )


def get_tool_list() -> list[dict[str, Any]]:
    return list(TOOL_DEFINITIONS.values())
