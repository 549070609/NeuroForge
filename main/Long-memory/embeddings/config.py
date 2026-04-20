"""
配置管理
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EmbeddingsConfig:
    """嵌入配置"""

    model_path: Optional[str] = None
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"  # cpu, cuda, mps
    max_batch_size: int = 4
    embedding_dimension: int = 384

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingsConfig":
        """从字典创建配置"""
        return cls(
            model_path=data.get("model_path"),
            model_name=data.get("model_name", "all-MiniLM-L6-v2"),
            device=data.get("device", "cpu"),
            max_batch_size=data.get("max_batch_size", 4),
            embedding_dimension=data.get("embedding_dimension", 384),
        )

    @classmethod
    def default(cls) -> "EmbeddingsConfig":
        """获取默认配置"""
        return cls()
