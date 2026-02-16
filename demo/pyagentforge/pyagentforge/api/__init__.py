"""
API 接口模块

包含 FastAPI 应用、路由、认证等组件
"""

from pyagentforge.api.app import create_app

__all__ = [
    "create_app",
]
