"""
日志系统模块

提供结构化日志支持
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# NOTE: ``get_settings`` 采用函数内延迟导入，避免 ``pyagentforge.config`` 包
# 初始化路径与 ``pyagentforge.kernel.model_registry`` 形成循环：
#   config.__init__ -> config.llm_config -> kernel.model_registry -> utils.logging
# 在合并 ModelConfig 为单一来源（kernel 版）后，该链路才被激活。


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra_data") and record.extra_data:
            log_data["data"] = record.extra_data

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ExtraLogAdapter(logging.LoggerAdapter):
    """支持额外数据的日志适配器"""

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        extra_data = kwargs.pop("extra_data", {})
        if self.extra:
            extra_data.update(self.extra)
        kwargs["extra"] = {"extra_data": extra_data}
        return msg, kwargs


def setup_logging(
    level: str | None = None,
    log_format: str | None = None,
) -> None:
    """
    设置日志系统

    Args:
        level: 日志级别，默认从配置读取
        log_format: 日志格式 (json/text)，默认从配置读取
    """
    from pyagentforge.config.settings import get_settings  # lazy import, see module header

    settings = get_settings()

    log_level = level or settings.log_level
    fmt = log_format or settings.log_format

    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 创建控制台处理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level))

    # 设置格式化器
    if fmt == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # 设置第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> ExtraLogAdapter:
    """
    获取日志器

    Args:
        name: 日志器名称

    Returns:
        带有额外数据支持的日志器
    """
    logger = logging.getLogger(name)
    return ExtraLogAdapter(logger, {})
