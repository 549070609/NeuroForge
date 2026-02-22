"""
AST-Grep 结果格式化

负责将搜索/替换结果格式化为用户友好的文本
"""

from typing import Optional

from pyagentforge.plugins.tools.ast_grep.types import SgResult, SgMatch


def format_search_result(result: SgResult) -> str:
    """
    格式化搜索结果

    Args:
        result: 搜索结果

    Returns:
        str: 格式化后的文本
    """
    if result.error:
        return f"Error: {result.error}"

    if not result.matches:
        return "No matches found."

    lines = []

    # 按文件分组
    current_file = None
    for match in result.matches:
        # 文件变化时添加分隔
        if match.file != current_file:
            if current_file is not None:
                lines.append("")  # 文件间空行
            current_file = match.file
            lines.append(f"[File] {match.file}")

        # 格式: line:column: matched_text
        lines.append(f"  {match.line}:{match.column}: {match.text}")

    output = "\n".join(lines)

    # 统计信息
    output += f"\n\n[Total] {result.total_matches} match(es)"

    if result.truncated:
        output += f" (truncated: {result.truncated_reason})"

    return output


def format_replace_result(result: SgResult, dry_run: bool) -> str:
    """
    格式化替换结果

    Args:
        result: 替换结果
        dry_run: 是否为预览模式

    Returns:
        str: 格式化后的文本
    """
    if result.error:
        return f"Error: {result.error}"

    mode = "[Preview]" if dry_run else "[Applied]"

    if not result.matches:
        return f"{mode}: No matches found for replacement."

    lines = [f"{mode} - {result.total_matches} replacement(s):\n"]

    # 按文件分组
    current_file = None
    for match in result.matches:
        if match.file != current_file:
            if current_file is not None:
                lines.append("")
            current_file = match.file
            lines.append(f"[File] {match.file}")

        # 显示原始和替换后的文本
        lines.append(f"  Line {match.line}:")
        lines.append(f"    - {match.text}")
        if match.replacement:
            lines.append(f"    + {match.replacement}")

    if dry_run:
        lines.append("\n[Hint] Set dry_run=False to apply changes.")

    return "\n".join(lines)


def get_empty_result_hint(pattern: str, lang: str) -> Optional[str]:
    """
    提供空结果时的提示

    Args:
        pattern: AST 模式
        lang: 语言

    Returns:
        str or None: 提示信息
    """
    src = pattern.strip()

    # Python 特定提示
    if lang == "python":
        if src.startswith("class ") and src.endswith(":"):
            without_colon = src[:-1]
            return f"Hint: Remove trailing colon. Try: '{without_colon}'"

        if (src.startswith("def ") or src.startswith("async def ")) and src.endswith(":"):
            without_colon = src[:-1]
            return f"Hint: Remove trailing colon. Try: '{without_colon}'"

        if src.startswith("if ") and src.endswith(":"):
            without_colon = src[:-1]
            return f"Hint: Remove trailing colon. Try: '{without_colon}'"

    # JavaScript/TypeScript 提示
    if lang in ["javascript", "typescript", "tsx"]:
        # 函数模式不完整
        if "function" in src and "{" not in src:
            return "Hint: Function patterns need params and body. Try: 'function $NAME($$$) { $$$ }'"

        # 箭头函数不完整
        if "=>" in src and "{" not in src and "(" not in src.split("=>")[0]:
            return "Hint: Arrow function patterns need complete syntax. Try: 'const $NAME = ($$$) => { $$$ }'"

    # 通用提示
    if src.endswith(";") and lang not in ["c", "cpp", "java", "javascript", "typescript"]:
        return f"Hint: '{lang}' does not use semicolons. Try removing the trailing semicolon."

    return None
