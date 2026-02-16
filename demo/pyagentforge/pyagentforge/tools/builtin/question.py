"""
Question 工具

向用户提问并等待回答
"""

from typing import Any, Callable

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class QuestionTool(BaseTool):
    """Question 工具 - 向用户提问"""

    name = "question"
    description = """向用户提问并等待回答。

使用场景:
- 需要用户确认操作
- 请求用户提供信息
- 让用户做出选择

问题会显示给用户，用户回答后继续执行。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要问用户的问题",
            },
            "options": {
                "type": "array",
                "description": "可选的答案选项",
                "items": {"type": "string"},
            },
            "default": {
                "type": "string",
                "description": "默认答案",
            },
            "allow_other": {
                "type": "boolean",
                "description": "是否允许用户输入其他答案",
                "default": True,
            },
        },
        "required": ["question"],
    }
    timeout = 300  # 5分钟等待用户回答
    risk_level = "low"

    def __init__(
        self,
        ask_callback: Callable[[str, list[str] | None, str | None, bool], str] | None = None,
    ) -> None:
        """
        初始化

        Args:
            ask_callback: 用户提问回调函数
                - 参数: (question, options, default, allow_other)
                - 返回: 用户回答
        """
        self.ask_callback = ask_callback

    async def execute(
        self,
        question: str,
        options: list[str] | None = None,
        default: str | None = None,
        allow_other: bool = True,
    ) -> str:
        """向用户提问"""
        logger.info(
            "Asking user question",
            extra_data={"question": question[:100], "options": options},
        )

        if self.ask_callback:
            # 使用回调获取答案
            answer = self.ask_callback(question, options, default, allow_other)
            return f"User answered: {answer}"

        # 如果没有回调，返回提示让 Agent 自行处理
        result_parts = [f"[QUESTION]: {question}"]

        if options:
            result_parts.append("\nOptions:")
            for i, opt in enumerate(options, 1):
                marker = " (default)" if opt == default else ""
                result_parts.append(f"  {i}. {opt}{marker}")

        if allow_other:
            result_parts.append("\n(User can provide a custom answer)")

        if default:
            result_parts.append(f"\nDefault: {default}")

        result_parts.append("\n[Waiting for user response...]")

        return "\n".join(result_parts)


class AskUserQuestion:
    """用户提问助手类"""

    def __init__(self) -> None:
        self._pending_questions: list[dict[str, Any]] = []
        self._answers: dict[str, str] = {}

    def ask(
        self,
        question: str,
        options: list[str] | None = None,
        default: str | None = None,
    ) -> str:
        """
        同步提问

        Args:
            question: 问题
            options: 选项
            default: 默认值

        Returns:
            问题 ID
        """
        import uuid

        question_id = str(uuid.uuid4())[:8]
        self._pending_questions.append({
            "id": question_id,
            "question": question,
            "options": options,
            "default": default,
            "status": "pending",
        })
        return question_id

    def answer(self, question_id: str, answer: str) -> None:
        """回答问题"""
        self._answers[question_id] = answer
        for q in self._pending_questions:
            if q["id"] == question_id:
                q["status"] = "answered"
                q["answer"] = answer
                break

    def get_answer(self, question_id: str) -> str | None:
        """获取答案"""
        return self._answers.get(question_id)

    def get_pending(self) -> list[dict[str, Any]]:
        """获取待回答问题"""
        return [q for q in self._pending_questions if q["status"] == "pending"]


class ConfirmTool(BaseTool):
    """Confirm 工具 - 简单的确认"""

    name = "confirm"
    description = """请求用户确认是/否。

返回用户的选择。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "确认消息",
            },
            "default": {
                "type": "boolean",
                "description": "默认值",
                "default": False,
            },
        },
        "required": ["message"],
    }
    timeout = 120
    risk_level = "low"

    def __init__(
        self,
        confirm_callback: Callable[[str, bool], bool] | None = None,
    ) -> None:
        self.confirm_callback = confirm_callback

    async def execute(
        self,
        message: str,
        default: bool = False,
    ) -> str:
        """请求确认"""
        logger.info(
            "Requesting confirmation",
            extra_data={"message": message[:100]},
        )

        if self.confirm_callback:
            result = self.confirm_callback(message, default)
            return f"User confirmed: {result}"

        default_str = "Y/n" if default else "y/N"
        return f"[CONFIRM]: {message}\n[{default_str}]?\n[Waiting for user confirmation...]"
