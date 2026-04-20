"""
思维链系统 (Chain of Thought)

提供结构化的思考过程指导 Agent 解决问题。
"""

from .cot_manager import ChainOfThoughtManager
from .models import (
    ChainOfThought,
    ConstraintType,
    ConstraintViolation,
    CoTPhase,
)
from .PLUGIN import ChainOfThoughtPlugin

__all__ = [
    "ChainOfThoughtPlugin",
    "ChainOfThoughtManager",
    "ChainOfThought",
    "CoTPhase",
    "ConstraintType",
    "ConstraintViolation",
]
