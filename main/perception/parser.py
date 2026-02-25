"""
ATON/TOON 日志解析

将原始日志统一解析为 Python 原生结构 (dict | list)
"""

try:
    from .detector import detect_format
except ImportError:
    from detector import detect_format


def parse_log(raw: str, fmt: str | None = None) -> dict | list:
    """
    解析 ATON 或 TOON 格式日志为 Python 原生结构

    Args:
        raw: 原始日志文本
        fmt: 显式指定格式 ("aton" | "toon")，None 时自动检测

    Returns:
        解析后的 dict 或 list

    Raises:
        ValueError: 格式不支持或解析失败
    """
    detected = fmt or detect_format(raw)

    if detected == "aton":
        return _parse_aton(raw)
    if detected == "toon":
        return _parse_toon(raw)

    raise ValueError(f"Unsupported or unknown format: {detected}")


def _parse_aton(raw: str) -> dict | list:
    """解析 ATON 格式"""
    try:
        from aton_format import ATONDecoder
    except ImportError as e:
        raise ImportError("aton-format not installed. Run: pip install aton-format") from e

    try:
        decoder = ATONDecoder()
        return decoder.decode(raw)
    except Exception as e:
        raise ValueError(f"ATON parse failed: {e}") from e


def _parse_toon(raw: str) -> dict | list:
    """解析 TOON 格式"""
    try:
        from toon import ToonDecoder
    except ImportError as e:
        raise ImportError(
            "toon-formatter not installed. Run: pip install toon-formatter"
        ) from e

    try:
        decoder = ToonDecoder(strict=False)  # PoC 使用宽松模式
        return decoder.decode(raw)
    except Exception as e:
        raise ValueError(f"TOON parse failed: {e}") from e
