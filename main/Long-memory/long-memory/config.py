"""
长记忆插件配置

管理 ChromaDB 存储路径、集合名称等配置
"""

from dataclasses import dataclass, field
import os


@dataclass
class LongMemoryConfig:
    """长记忆插件配置"""

    # ChromaDB 配置
    persist_directory: str = "./data/chroma"
    collection_name: str = "long_memory"

    # 搜索配置
    default_search_limit: int = 5
    max_search_limit: int = 50

    # 搜索模式配置
    # exact: 精准模式 - 关键词/文本精确匹配
    # fuzzy: 模糊模式 - 语义相似度搜索（默认）
    default_search_mode: str = "fuzzy"
    exact_match_threshold: float = 0.95  # 精准模式的相似度阈值

    # 自动记忆配置（中间件使用）
    auto_memory_enabled: bool = False
    auto_memory_min_importance: float = 0.6  # 最低重要性阈值
    auto_memory_keywords: list = field(default_factory=lambda: [
        "记住", "记忆", "重要", "偏好", "设置",
        "记住这个", "别忘了", "记录", "保存",
        "remember", "important", "note", "save"
    ])

    # 嵌入配置
    embedding_batch_size: int = 4

    @classmethod
    def from_dict(cls, data: dict) -> "LongMemoryConfig":
        """从字典创建配置"""
        return cls(
            persist_directory=data.get("persist_directory", "./data/chroma"),
            collection_name=data.get("collection_name", "long_memory"),
            default_search_limit=data.get("default_search_limit", 5),
            max_search_limit=data.get("max_search_limit", 50),
            default_search_mode=data.get("default_search_mode", "fuzzy"),
            exact_match_threshold=data.get("exact_match_threshold", 0.95),
            auto_memory_enabled=data.get("auto_memory_enabled", False),
            auto_memory_min_importance=data.get("auto_memory_min_importance", 0.6),
            auto_memory_keywords=data.get("auto_memory_keywords", [
                "记住", "记忆", "重要", "偏好", "设置",
                "记住这个", "别忘了", "记录", "保存",
                "remember", "important", "note", "save"
            ]),
            embedding_batch_size=data.get("embedding_batch_size", 4),
        )

    def ensure_directory(self) -> None:
        """确保持久化目录存在"""
        if not os.path.exists(self.persist_directory):
            os.makedirs(self.persist_directory, exist_ok=True)

    def validate(self) -> list:
        """
        验证配置

        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []

        if self.default_search_limit < 1:
            errors.append("default_search_limit must be at least 1")
        if self.default_search_limit > self.max_search_limit:
            errors.append("default_search_limit cannot exceed max_search_limit")
        if self.auto_memory_min_importance < 0 or self.auto_memory_min_importance > 1:
            errors.append("auto_memory_min_importance must be between 0 and 1")
        if self.embedding_batch_size < 1:
            errors.append("embedding_batch_size must be at least 1")
        if self.default_search_mode not in ("exact", "fuzzy"):
            errors.append("default_search_mode must be 'exact' or 'fuzzy'")
        if self.exact_match_threshold < 0 or self.exact_match_threshold > 1:
            errors.append("exact_match_threshold must be between 0 and 1")

        return errors
