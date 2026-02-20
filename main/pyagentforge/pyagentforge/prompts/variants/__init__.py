"""
提示词变体模块
"""

from pyagentforge.prompts.variants.anthropic import register_anthropic_variants
from pyagentforge.prompts.variants.google import register_google_variants
from pyagentforge.prompts.variants.openai import register_openai_variants
from pyagentforge.prompts.variants.default import register_default_variant

__all__ = [
    "register_anthropic_variants",
    "register_google_variants",
    "register_openai_variants",
    "register_default_variant",
]
