"""Long memory package exports."""

try:
    from .PLUGIN import LongMemoryPlugin, create_plugin
    from .config import LongMemoryConfig
    from .models import MemoryEntry, MemorySearchResult, MemoryStats
    from .vector_store import ChromaVectorStore
except ImportError:
    # Support direct-file imports during standalone plugin loading/tests.
    from PLUGIN import LongMemoryPlugin, create_plugin
    from config import LongMemoryConfig
    from models import MemoryEntry, MemorySearchResult, MemoryStats
    from vector_store import ChromaVectorStore

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
