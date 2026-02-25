"""
日志格式检测

根据内容启发式判断 ATON 或 TOON 格式
"""


def detect_format(raw: str) -> str:
    """
    检测日志格式

    Args:
        raw: 原始日志文本

    Returns:
        "aton" | "toon" | "unknown"
    """
    if not raw or not raw.strip():
        return "unknown"

    stripped = raw.strip()

    # ATON: 以 @schema 或 @defaults 开头
    if stripped.startswith("@schema") or stripped.startswith("@defaults"):
        return "aton"

    # TOON: 表格式 key[N]{fields}: 模式
    # 示例: users[2]{id,name,role}:
    if "{" in stripped and "}:" in stripped and "[" in stripped:
        return "toon"

    # TOON: 简化表格式 [N]{fields}:
    if stripped.startswith("[") and "{" in stripped and "}:" in stripped:
        return "toon"

    return "unknown"
