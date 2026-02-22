"""
记忆加工配置

定义标签池、分析参数等配置项
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json


# 默认标签池（分类 -> 标签列表）
DEFAULT_TAG_POOL: Dict[str, List[str]] = {
    "work": ["工作", "项目", "任务", "计划", "会议", "进度"],
    "technical": ["代码", "技术", "Bug", "功能", "架构", "API", "框架"],
    "learning": ["学习", "笔记", "教程", "文档", "课程", "研究"],
    "personal": ["偏好", "设置", "个人信息", "习惯", "风格"],
    "ideas": ["想法", "创意", "待办", "目标", "规划", "灵感"],
    "reference": ["资料", "链接", "命令", "配置", "参数", "环境"],
    "communication": ["沟通", "反馈", "问题", "决策", "讨论"],
    "important": ["重要", "紧急", "关键", "核心", "必要"],
}


def _flatten_tag_pool(tag_pool: Dict[str, List[str]]) -> List[str]:
    """展平标签池为简单列表"""
    tags = []
    for category_tags in tag_pool.values():
        tags.extend(category_tags)
    return list(set(tags))  # 去重


@dataclass
class ProcessorConfig:
    """记忆加工配置"""

    # 基本配置
    enabled: bool = True
    auto_trigger: bool = True  # 存入后自动触发加工

    # 模型配置
    model: str = "default"  # LLM 模型标识

    # 输出限制
    max_summary_length: int = 200  # 摘要最大长度（字符）
    max_topic_length: int = 50     # 主题最大长度（字符）
    max_tags: int = 5              # 最多标签数

    # 标签池
    tag_pool: Dict[str, List[str]] = field(default_factory=lambda: DEFAULT_TAG_POOL)

    # 性能配置
    timeout: int = 30  # LLM 调用超时（秒）

    # 回退策略
    fallback_to_rules: bool = True  # LLM 失败时回退到规则分析

    # 调试
    debug: bool = False

    @property
    def flat_tag_pool(self) -> List[str]:
        """获取展平后的标签池"""
        return _flatten_tag_pool(self.tag_pool)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ProcessorConfig":
        """从字典创建配置"""
        if data is None:
            return cls()

        # 处理标签池
        tag_pool = data.get("tag_pool")
        if tag_pool is None:
            tag_pool = DEFAULT_TAG_POOL
        elif isinstance(tag_pool, list):
            # 如果是列表格式，转换为分类格式
            tag_pool = {"general": tag_pool}

        return cls(
            enabled=data.get("enabled", True),
            auto_trigger=data.get("auto_trigger", True),
            model=data.get("model", "default"),
            max_summary_length=data.get("max_summary_length", 200),
            max_topic_length=data.get("max_topic_length", 50),
            max_tags=data.get("max_tags", 5),
            tag_pool=tag_pool,
            timeout=data.get("timeout", 30),
            fallback_to_rules=data.get("fallback_to_rules", True),
            debug=data.get("debug", False),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "auto_trigger": self.auto_trigger,
            "model": self.model,
            "max_summary_length": self.max_summary_length,
            "max_topic_length": self.max_topic_length,
            "max_tags": self.max_tags,
            "tag_pool": self.tag_pool,
            "timeout": self.timeout,
            "fallback_to_rules": self.fallback_to_rules,
            "debug": self.debug,
        }

    def validate(self) -> List[str]:
        """
        验证配置

        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []

        if self.max_summary_length < 10:
            errors.append("max_summary_length must be at least 10")
        if self.max_topic_length < 2:
            errors.append("max_topic_length must be at least 2")
        if self.max_tags < 1:
            errors.append("max_tags must be at least 1")
        if self.timeout < 5:
            errors.append("timeout must be at least 5 seconds")

        return errors

    def get_tags_for_category(self, category: str) -> List[str]:
        """获取指定分类的标签"""
        return self.tag_pool.get(category, [])

    def find_category_for_tag(self, tag: str) -> Optional[str]:
        """查找标签所属分类"""
        for category, tags in self.tag_pool.items():
            if tag in tags:
                return category
        return None
