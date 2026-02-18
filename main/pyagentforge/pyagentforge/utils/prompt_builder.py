"""
动态 Prompt 构建器

支持模块化的 Prompt 组装，按优先级排序各部分内容。

Usage:
    builder = PromptBuilder()
    builder.add_section("System Instructions", priority=100)
    builder.add_section("Tool Usage Guide", priority=50)
    builder.add_section("Task Details", priority=0)

    prompt = builder.build()
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class PromptSection:
    """Prompt 片段"""

    content: str
    priority: int = 0
    name: str = ""
    condition: Callable[[], bool] | None = None  # 条件函数，决定是否包含

    def __lt__(self, other: "PromptSection") -> bool:
        """用于排序，优先级高的排前面"""
        return self.priority > other.priority


class PromptBuilder:
    """
    动态 Prompt 构建器

    Features:
    - 模块化 Prompt 管理
    - 优先级排序
    - 条件性包含
    - 链式调用
    - 变量替换

    Example:
        builder = PromptBuilder()
        builder.add_section(
            "You are a helpful assistant.",
            name="role",
            priority=100,
        ).add_section(
            "Tools available: {tools}",
            name="tools",
            priority=50,
        ).add_section(
            "User request: {request}",
            name="request",
            priority=0,
        )

        prompt = builder.build(
            tools="read, write, edit",
            request="Help me fix a bug",
        )
    """

    def __init__(self, separator: str = "\n\n"):
        """
        初始化 Prompt 构建器

        Args:
            separator: 片段之间的分隔符
        """
        self.sections: list[PromptSection] = []
        self.separator = separator
        self._variables: dict[str, Any] = {}

    def add_section(
        self,
        content: str,
        name: str = "",
        priority: int = 0,
        condition: Callable[[], bool] | None = None,
    ) -> "PromptBuilder":
        """
        添加 Prompt 片段

        Args:
            content: 片段内容（支持 {variable} 占位符）
            name: 片段名称（用于调试）
            priority: 优先级（越高越靠前）
            condition: 条件函数，返回 True 时才包含此片段

        Returns:
            self（支持链式调用）
        """
        section = PromptSection(
            content=content,
            priority=priority,
            name=name,
            condition=condition,
        )
        self.sections.append(section)
        return self

    def add_section_if(
        self,
        condition: bool,
        content: str,
        name: str = "",
        priority: int = 0,
    ) -> "PromptBuilder":
        """
        条件性添加 Prompt 片段

        Args:
            condition: 是否添加
            content: 片段内容
            name: 片段名称
            priority: 优先级

        Returns:
            self
        """
        if condition:
            self.add_section(content, name, priority)
        return self

    def add_header(self, content: str) -> "PromptBuilder":
        """
        添加头部片段（高优先级）

        Args:
            content: 头部内容

        Returns:
            self
        """
        return self.add_section(content, name="header", priority=1000)

    def add_footer(self, content: str) -> "PromptBuilder":
        """
        添加尾部片段（低优先级）

        Args:
            content: 尾部内容

        Returns:
            self
        """
        return self.add_section(content, name="footer", priority=-1000)

    def set_variable(self, key: str, value: Any) -> "PromptBuilder":
        """
        设置变量值

        Args:
            key: 变量名
            value: 变量值

        Returns:
            self
        """
        self._variables[key] = value
        return self

    def set_variables(self, **kwargs: Any) -> "PromptBuilder":
        """
        批量设置变量值

        Returns:
            self
        """
        self._variables.update(kwargs)
        return self

    def clear_variables(self) -> "PromptBuilder":
        """
        清除所有变量

        Returns:
            self
        """
        self._variables.clear()
        return self

    def clear_sections(self) -> "PromptBuilder":
        """
        清除所有片段

        Returns:
            self
        """
        self.sections.clear()
        return self

    def clear(self) -> "PromptBuilder":
        """
        清除所有内容（片段和变量）

        Returns:
            self
        """
        self.sections.clear()
        self._variables.clear()
        return self

    def build(self, **variables: Any) -> str:
        """
        构建 Prompt

        Args:
            **variables: 运行时变量（覆盖已设置的变量）

        Returns:
            构建后的 Prompt 字符串
        """
        # 合并变量
        all_vars = {**self._variables, **variables}

        # 过滤和排序片段
        valid_sections = [
            section
            for section in self.sections
            if section.condition is None or section.condition()
        ]
        sorted_sections = sorted(valid_sections)

        # 替换变量并拼接
        parts = []
        for section in sorted_sections:
            content = self._replace_variables(section.content, all_vars)
            parts.append(content)

        return self.separator.join(parts)

    def _replace_variables(
        self,
        content: str,
        variables: dict[str, Any],
    ) -> str:
        """
        替换内容中的变量

        Args:
            content: 包含 {variable} 占位符的内容
            variables: 变量字典

        Returns:
            替换后的内容
        """
        result = content

        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))

        return result

    def get_section_names(self) -> list[str]:
        """
        获取所有片段名称

        Returns:
            片段名称列表
        """
        return [s.name for s in self.sections]

    def get_section_count(self) -> int:
        """
        获取片段数量

        Returns:
            片段数量
        """
        return len(self.sections)

    def remove_section(self, name: str) -> "PromptBuilder":
        """
        移除指定名称的片段

        Args:
            name: 片段名称

        Returns:
            self
        """
        self.sections = [s for s in self.sections if s.name != name]
        return self

    def update_section(
        self,
        name: str,
        content: str | None = None,
        priority: int | None = None,
    ) -> "PromptBuilder":
        """
        更新指定名称的片段

        Args:
            name: 片段名称
            content: 新内容（None 表示不变）
            priority: 新优先级（None 表示不变）

        Returns:
            self
        """
        for section in self.sections:
            if section.name == name:
                if content is not None:
                    section.content = content
                if priority is not None:
                    section.priority = priority
                break
        return self

    def preview(self, **variables: Any) -> str:
        """
        预览构建结果（带片段标记）

        Args:
            **variables: 变量

        Returns:
            带标记的预览内容
        """
        all_vars = {**self._variables, **variables}

        valid_sections = [
            section
            for section in self.sections
            if section.condition is None or section.condition()
        ]
        sorted_sections = sorted(valid_sections)

        parts = []
        for section in sorted_sections:
            content = self._replace_variables(section.content, all_vars)
            name = section.name or "unnamed"
            parts.append(f"[{name} | priority={section.priority}]\n{content}")

        return self.separator.join(parts)

    def __str__(self) -> str:
        return self.build()

    def __repr__(self) -> str:
        return f"PromptBuilder(sections={len(self.sections)})"


class PromptTemplate:
    """
    Prompt 模板

    用于创建可重用的 Prompt 模板。

    Example:
        template = PromptTemplate(
            name="code_review",
            sections=[
                ("role", "You are a code reviewer.", 100),
                ("context", "Review this code: {code}", 50),
                ("rules", "Focus on: {focus}", 25),
            ],
        )

        prompt = template.render(code="def foo(): pass", focus="security, performance")
    """

    def __init__(
        self,
        name: str,
        sections: list[tuple[str, str, int]],  # (name, content, priority)
        separator: str = "\n\n",
    ):
        """
        初始化 Prompt 模板

        Args:
            name: 模板名称
            sections: 片段列表 [(name, content, priority), ...]
            separator: 分隔符
        """
        self.name = name
        self.sections = sections
        self.separator = separator

    def render(self, **variables: Any) -> str:
        """
        渲染模板

        Args:
            **variables: 变量

        Returns:
            渲染后的 Prompt
        """
        builder = PromptBuilder(separator=self.separator)

        for name, content, priority in self.sections:
            builder.add_section(content, name=name, priority=priority)

        return builder.build(**variables)

    def create_builder(self) -> PromptBuilder:
        """
        基于此模板创建构建器

        Returns:
            PromptBuilder 实例
        """
        builder = PromptBuilder(separator=self.separator)

        for name, content, priority in self.sections:
            builder.add_section(content, name=name, priority=priority)

        return builder


# 预定义模板
SYSTEM_PROMPT_TEMPLATE = PromptTemplate(
    name="system_prompt",
    sections=[
        ("role", "You are a helpful AI assistant.", 100),
        ("capabilities", "You have access to the following tools:\n{tools}", 75),
        ("instructions", "Instructions:\n{instructions}", 50),
        ("context", "Context:\n{context}", 25),
        ("task", "Task: {task}", 0),
    ],
)

CODE_REVIEW_TEMPLATE = PromptTemplate(
    name="code_review",
    sections=[
        ("role", "You are an expert code reviewer.", 100),
        ("focus", "Focus areas: {focus}", 75),
        ("code", "Code to review:\n```\n{code}\n```", 50),
        ("output", "Provide your review in the following format:\n{format}", 25),
    ],
)
