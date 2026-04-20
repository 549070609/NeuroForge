"""
主动感知器 - 基于 ATON/TOON 日志的主动感知与决策

模块：
- detector: 格式检测
- parser: ATON/TOON 解析
- perception: 感知与决策逻辑
- tools: BaseTool 实现
- PLUGIN: 插件入口
"""

from .detector import detect_format
from .parser import parse_log
from .perception import DecisionType, PerceptionResult, perceive
from .PLUGIN import PerceptionPlugin

__all__ = [
    "detect_format",
    "parse_log",
    "perceive",
    "PerceptionResult",
    "DecisionType",
    "PerceptionPlugin",
]
