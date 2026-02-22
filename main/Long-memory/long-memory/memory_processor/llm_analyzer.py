"""
LLM 分析器

使用 LLM 分析记忆内容，生成标签、主题和摘要
支持 LLM 和规则两种模式，自动回退
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果"""

    tags: List[str] = field(default_factory=list)
    topic: str = ""
    summary: str = ""
    confidence: float = 0.0  # 置信度 0.0-1.0
    method: str = "unknown"  # 分析方法: llm, rule, none

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tags": self.tags,
            "topic": self.topic,
            "summary": self.summary,
            "confidence": self.confidence,
            "method": self.method,
        }

    @classmethod
    def empty(cls) -> "AnalysisResult":
        """创建空结果"""
        return cls(tags=[], topic="", summary="", confidence=0.0, method="none")


class LLMAnalyzer:
    """LLM 记忆分析器"""

    SYSTEM_PROMPT = """你是一个记忆分析助手。分析用户提供的记忆内容，生成结构化的元数据。

任务要求：
1. 标签 (tags): 从提供的标签池中选择 1-3 个最相关的标签
2. 主题 (topic): 用 3-5 个字概括这段记忆的核心内容
3. 摘要 (summary): 用 1-2 句话概括记忆的关键信息

输出格式要求（仅输出 JSON，不要有其他内容）：
```json
{
  "tags": ["标签1", "标签2"],
  "topic": "简短主题",
  "summary": "一句话摘要"
}
```

注意：
- 标签必须从标签池中选择
- 主题要简洁明确
- 摘要要抓住核心要点"""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        tag_pool: List[str] = None,
        max_summary_length: int = 200,
        max_topic_length: int = 50,
        max_tags: int = 5,
        timeout: int = 30,
        fallback_to_rules: bool = True,
    ):
        """
        初始化分析器

        Args:
            llm_client: LLM 客户端（可选）
            tag_pool: 可用标签池
            max_summary_length: 摘要最大长度
            max_topic_length: 主题最大长度
            max_tags: 最多标签数
            timeout: LLM 调用超时
            fallback_to_rules: LLM 失败时是否回退到规则
        """
        self._llm_client = llm_client
        self._tag_pool = tag_pool or []
        self._max_summary_length = max_summary_length
        self._max_topic_length = max_topic_length
        self._max_tags = max_tags
        self._timeout = timeout
        self._fallback_to_rules = fallback_to_rules

        # 规则匹配关键词
        self._rule_keywords = {
            "工作": ["工作", "项目", "任务", "计划", "会议", "进度", "报告", "团队", "合作"],
            "项目": ["项目", "工程", "开发", "版本", "里程碑", "迭代"],
            "代码": ["代码", "函数", "类", "模块", "API", "接口", "实现", "重构"],
            "技术": ["技术", "框架", "库", "依赖", "架构", "性能", "优化"],
            "Bug": ["Bug", "错误", "问题", "修复", "调试", "异常", "崩溃"],
            "功能": ["功能", "特性", "需求", "实现", "支持", "新增"],
            "学习": ["学习", "教程", "课程", "笔记", "文档", "知识", "理解"],
            "笔记": ["笔记", "记录", "备忘", "摘录", "总结"],
            "偏好": ["偏好", "喜欢", "习惯", "风格", "设置", "配置"],
            "设置": ["设置", "配置", "参数", "选项", "环境", "变量"],
            "想法": ["想法", "创意", "灵感", "点子", "思路", "构思"],
            "待办": ["待办", "TODO", "任务", "计划", "要做", "完成"],
            "重要": ["重要", "关键", "核心", "必要", "紧急", "优先"],
            "资料": ["资料", "链接", "参考", "文档", "资源", "手册"],
            "链接": ["链接", "URL", "网址", "网站", "页面", "地址"],
        }

    async def analyze(self, content: str) -> AnalysisResult:
        """
        分析记忆内容

        优先使用 LLM，失败时回退到规则

        Args:
            content: 记忆内容

        Returns:
            分析结果
        """
        if not content or not content.strip():
            return AnalysisResult.empty()

        # 尝试 LLM 分析
        if self._llm_client:
            try:
                result = await self._llm_analyze(content)
                if result.confidence > 0.5:
                    return result
                logger.debug("LLM analysis confidence low, falling back to rules")
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")

        # 回退到规则分析
        if self._fallback_to_rules:
            return self._rule_based_analyze(content)

        return AnalysisResult.empty()

    async def _llm_analyze(self, content: str) -> AnalysisResult:
        """
        使用 LLM 分析

        Args:
            content: 记忆内容

        Returns:
            分析结果
        """
        if not self._llm_client:
            raise RuntimeError("LLM client not available")

        # 构建提示
        tag_pool_str = ", ".join(self._tag_pool) if self._tag_pool else "无预设标签池"

        user_prompt = f"""请分析以下记忆内容：

标签池: {tag_pool_str}

记忆内容:
{content}

请输出 JSON 格式的分析结果。"""

        # 调用 LLM
        try:
            # 兼容不同的 LLM 客户端接口
            if hasattr(self._llm_client, "chat"):
                # OpenAI 风格接口
                response = await self._llm_client.chat(
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self._get_model_name(),
                    temperature=0.3,
                    max_tokens=500,
                    timeout=self._timeout,
                )
                response_text = response.choices[0].message.content
            elif hasattr(self._llm_client, "complete"):
                # Anthropic 风格接口
                response = await self._llm_client.complete(
                    messages=[
                        {"role": "user", "content": f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"},
                    ],
                    max_tokens=500,
                    timeout=self._timeout,
                )
                response_text = response.content[0].text
            elif callable(self._llm_client):
                # 直接调用
                response = await self._llm_client(
                    prompt=f"{self.SYSTEM_PROMPT}\n\n{user_prompt}",
                    max_tokens=500,
                    temperature=0.3,
                )
                if hasattr(response, "text"):
                    response_text = response.text
                elif isinstance(response, str):
                    response_text = response
                else:
                    response_text = str(response)
            else:
                raise RuntimeError(f"Unsupported LLM client type: {type(self._llm_client)}")

            # 解析 JSON 响应
            return self._parse_llm_response(response_text)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _parse_llm_response(self, response_text: str) -> AnalysisResult:
        """
        解析 LLM 响应

        Args:
            response_text: LLM 返回的文本

        Returns:
            分析结果
        """
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
            else:
                data = json.loads(response_text)

            # 提取字段
            tags = data.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]

            # 过滤和验证标签
            if self._tag_pool:
                tags = [t for t in tags if t in self._tag_pool]
            tags = tags[:self._max_tags]

            # 验证和截断主题
            topic = data.get("topic", "")[:self._max_topic_length]

            # 验证和截断摘要
            summary = data.get("summary", "")[:self._max_summary_length]

            # 计算置信度
            confidence = self._calculate_confidence(tags, topic, summary)

            return AnalysisResult(
                tags=tags,
                topic=topic,
                summary=summary,
                confidence=confidence,
                method="llm",
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return AnalysisResult(confidence=0.0, method="llm")

    def _calculate_confidence(
        self,
        tags: List[str],
        topic: str,
        summary: str,
    ) -> float:
        """
        计算置信度

        Args:
            tags: 标签列表
            topic: 主题
            summary: 摘要

        Returns:
            置信度 0.0-1.0
        """
        score = 0.0

        # 有标签加分
        if tags:
            score += 0.3
            if len(tags) >= 2:
                score += 0.1

        # 有主题加分
        if topic:
            score += 0.25
            if len(topic) >= 3:
                score += 0.1

        # 有摘要加分
        if summary:
            score += 0.25
            if len(summary) >= 10:
                score += 0.1

        return min(1.0, score)

    def _rule_based_analyze(self, content: str) -> AnalysisResult:
        """
        基于规则的分析

        Args:
            content: 记忆内容

        Returns:
            分析结果
        """
        tags = []
        content_lower = content.lower()

        # 匹配标签
        tag_scores: Dict[str, int] = {}
        for tag, keywords in self._rule_keywords.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    tag_scores[tag] = tag_scores.get(tag, 0) + 1

        # 选择得分最高的标签
        if tag_scores:
            sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
            tags = [t for t, _ in sorted_tags[:self._max_tags]]

        # 如果有预定义标签池，过滤
        if self._tag_pool:
            tags = [t for t in tags if t in self._tag_pool]

        # 生成主题（取内容的前几个字或关键词）
        topic = self._extract_topic(content)

        # 生成摘要（取内容的前几句）
        summary = self._extract_summary(content)

        # 规则分析的置信度较低
        confidence = 0.5 if tags else 0.3

        return AnalysisResult(
            tags=tags,
            topic=topic,
            summary=summary,
            confidence=confidence,
            method="rule",
        )

    def _extract_topic(self, content: str) -> str:
        """
        提取主题

        Args:
            content: 内容

        Returns:
            主题
        """
        # 尝试提取关键词作为主题
        # 首先检查是否有明显的主题标记
        patterns = [
            r"主题[是为：:]\s*(.+?)(?:\n|$)",
            r"关于\s*(.+?)\s*(?:的|记录|笔记)",
            r"#\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()[:self._max_topic_length]

        # 否则取内容的前几个字
        # 去除空白字符
        clean_content = re.sub(r'\s+', '', content)
        if len(clean_content) <= self._max_topic_length:
            return clean_content

        return clean_content[:self._max_topic_length]

    def _extract_summary(self, content: str) -> str:
        """
        提取摘要

        Args:
            content: 内容

        Returns:
            摘要
        """
        # 按句号分割，取前几句
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return content[:self._max_summary_length]

        # 组合句子直到达到长度限制
        summary_parts = []
        current_length = 0

        for sentence in sentences[:3]:  # 最多取前3句
            if current_length + len(sentence) <= self._max_summary_length:
                summary_parts.append(sentence)
                current_length += len(sentence)
            else:
                break

        summary = "。".join(summary_parts)
        if summary and not summary.endswith(("。", "！", "？")):
            summary += "。"

        return summary[:self._max_summary_length]

    def _get_model_name(self) -> str:
        """获取模型名称"""
        return getattr(self._llm_client, "model", "default") if self._llm_client else "default"

    def update_tag_pool(self, tag_pool: List[str]) -> None:
        """更新标签池"""
        self._tag_pool = tag_pool

    def update_llm_client(self, llm_client: Any) -> None:
        """更新 LLM 客户端"""
        self._llm_client = llm_client
