"""
ATON/TOON 日志解析

将原始日志统一解析为 Python 原生结构 (dict | list)
"""

try:
    from .detector import detect_format
except ImportError:
    from detector import detect_format


def parse_log(
    raw: str,
    fmt: str | None = None,
    strict: bool = False,
) -> dict | list:
    """
    解析 ATON 或 TOON 格式日志为 Python 原生结构

    Args:
        raw:    原始日志文本
        fmt:    显式指定格式 ("aton" | "toon")，None 时自动检测
        strict: 是否启用严格解析模式（仅对 TOON 生效）。
                False（默认）= 宽松模式，容忍轻微格式偏差；
                True          = 严格模式，格式错误立即抛出异常。

    Returns:
        解析后的 dict 或 list

    Raises:
        ValueError:   格式不支持或解析失败
        ImportError:  所需解析器包未安装
    """
    detected = fmt or detect_format(raw)

    if detected == "aton":
        return _parse_aton(raw)
    if detected == "toon":
        return _parse_toon(raw, strict=strict)

    raise ValueError(f"Unsupported or unknown format: {detected!r}")


def _parse_aton(raw: str) -> dict | list:
    """解析 ATON 格式"""
    try:
        from aton_format import ATONDecoder
    except ImportError as e:
        raise ImportError(
            "aton-format not installed. See requirements.txt for installation instructions."
        ) from e

    try:
        decoder = ATONDecoder()
        return decoder.decode(raw)
    except Exception as e:
        raise ValueError(f"ATON parse failed: {e}") from e


def _parse_toon(raw: str, strict: bool = False) -> dict | list:
    """解析 TOON 格式

    Args:
        raw:    原始 TOON 文本
        strict: True 表示严格模式（拒绝格式偏差），False 表示宽松模式（容忍轻微偏差）
    """
    try:
        from toon import ToonDecoder
    except ImportError as e:
        raise ImportError(
            "toon-formatter not installed. See requirements.txt for installation instructions."
        ) from e

    try:
        decoder = ToonDecoder(strict=strict)
        return decoder.decode(raw)
    except Exception as e:
        raise ValueError(f"TOON parse failed: {e}") from e
