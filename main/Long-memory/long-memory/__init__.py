"""Long Memory 插件"""

from .PLUGIN import LongMemoryPlugin, create_plugin
from .config import LongMemoryConfig
from .models import MemoryEntry, MemorySearchResult, MemoryStats
from .vector_store import ChromaVectorStore

__version__ = "1.0.0"
__all__ = [
    "LongMemoryPlugin",
    "create_plugin",
    "LongMemoryConfig",
    "MemoryEntry",
    "MemorySearchResult",
    "MemoryStats",
    "ChromaVectorStore",
]
