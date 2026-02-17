"""
API 限流模块

使用 slowapi 实现限流
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def get_client_identifier(request: Any) -> str:
    """
    获取客户端标识符

    优先使用认证用户 ID，否则使用 IP 地址

    Args:
        request: 请求对象

    Returns:
        客户端标识符
    """
    # 尝试从认证信息获取用户 ID
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user.user_id

    # 回退到 IP 地址
    return get_remote_address(request)
