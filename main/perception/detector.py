"""
日志格式检测

根据内容启发式判断 ATON 或 TOON 格式
"""

import re

# TOON 命名表格头：word[N]{fields}:  例 events[2]{id,level,message}:
_TOON_NAMED_RE = re.compile(r"^\w[\w.]*\[\d+\]\{[\w,\s]+\}:")
# TOON 匿名表格头：[N]{fields}:      例 [3]{id,level}:
_TOON_ANON_RE = re.compile(r"^\[\d+\]\{[\w,\s]+\}:")


def detect_format(raw: str) -> str:
    """
    检测日志格式

    Args:
        raw: 原始日志文本

    Returns:
        "aton" | "toon" | "unknown"

    Notes:
        TOON 检测仅扫描前 5 个非空行中是否出现标准表格头模式，
        避免含 ``{``、``[``、``}:`` 的普通文本被误判。
    """
    if not raw or not raw.strip():
        return "unknown"

    stripped = raw.strip()

    # ATON: 以 @schema 或 @defaults 开头
    if stripped.startswith("@schema") or stripped.startswith("@defaults"):
        return "aton"

    # TOON: 扫描前 5 个非空行，匹配标准表格头
    head_lines = [line.strip() for line in stripped.splitlines() if line.strip()][:5]
    for line in head_lines:
        if _TOON_NAMED_RE.match(line) or _TOON_ANON_RE.match(line):
            return "toon"

    return "unknown"
