"""
消息类型定义

定义 Agent 通信所需的消息格式
"""

from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """文本内容块"""

    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """工具调用块"""

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(..., description="工具调用唯一标识")
    name: str = Field(..., description="工具名称")
    input: dict[str, Any] = Field(default_factory=dict, description="工具输入参数")


class ToolResultBlock(BaseModel):
    """工具结果块"""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = Field(..., description="对应的工具调用 ID")
    content: str = Field(..., description="工具返回内容")
    is_error: bool = Field(default=False, description="是否为错误结果")


# 消息内容可以是文本或内容块列表
MessageContent = Union[str, list[Union[TextBlock, ToolUseBlock, ToolResultBlock]]]


class Message(BaseModel):
    """对话消息"""

    role: Literal["user", "assistant"]
    content: MessageContent

    def to_api_format(self) -> dict[str, Any]:
        """转换为 API 调用格式"""
        if isinstance(self.content, str):
            return {"role": self.role, "content": self.content}

        # 转换内容块
        blocks = []
        for block in self.content:
            if isinstance(block, TextBlock):
                blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif isinstance(block, ToolResultBlock):
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                })

        return {"role": self.role, "content": blocks}

    @classmethod
    def user_message(cls, content: str) -> "Message":
        """创建用户消息"""
        return cls(role="user", content=content)

    @classmethod
    def assistant_text(cls, text: str) -> "Message":
        """创建助手文本消息"""
        return cls(role="assistant", content=[TextBlock(text=text)])

    @classmethod
    def assistant_tool_calls(
        cls,
        tool_calls: list[ToolUseBlock],
    ) -> "Message":
        """创建助手工具调用消息"""
        return cls(role="assistant", content=tool_calls)

    @classmethod
    def tool_result(
        cls,
        tool_use_id: str,
        content: str,
        is_error: bool = False,
    ) -> "Message":
        """创建工具结果消息"""
        return cls(
            role="user",
            content=[
                ToolResultBlock(
                    tool_use_id=tool_use_id,
                    content=content,
                    is_error=is_error,
                )
            ],
        )


class ProviderResponse(BaseModel):
    """LLM 提供商响应"""

    content: list[Union[TextBlock, ToolUseBlock]]
    stop_reason: str  # end_turn, tool_use, max_tokens
    usage: dict[str, int] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """提取文本内容"""
        texts = [b.text for b in self.content if isinstance(b, TextBlock)]
        return "\n".join(texts)

    @property
    def tool_calls(self) -> list[ToolUseBlock]:
        """提取工具调用"""
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    @property
    def has_tool_calls(self) -> bool:
        """是否有工具调用"""
        return len(self.tool_calls) > 0
