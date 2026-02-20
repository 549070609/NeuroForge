"""
思维链系统 (Chain of Thought)

提供结构化的思考过程指导 Agent 解决问题。
"""

from .PLUGIN import ChainOfThoughtPlugin
from .cot_manager import ChainOfThoughtManager
from .models import (
    ChainOfThought,
    CoTPhase,
    ConstraintType,
    ConstraintViolation,
)

__all__ = [
    "ChainOfThoughtPlugin",
    "ChainOfThoughtManager",
    "ChainOfThought",
    "CoTPhase",
    "ConstraintType",
    "ConstraintViolation",
]
