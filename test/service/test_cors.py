"""P0-7 CORS 收敛回归测试"""

from __future__ import annotations

import pytest

from Service.config.settings import ServiceSettings
from Service.gateway.app import _validate_cors_settings


class TestCorsValidation:
    """生产模式下拒绝 origins=["*"] + credentials=True。"""

    def test_production_wildcard_with_credentials_raises(self):
        s = ServiceSettings(
            debug=False,
            cors_allowed_origins=["*"],
            cors_allow_credentials=True,
        )
        with pytest.raises(ValueError, match="CORS"):
            _validate_cors_settings(s)

    def test_production_explicit_origin_ok(self):
        s = ServiceSettings(
            debug=False,
            cors_allowed_origins=["https://app.example.com"],
            cors_allow_credentials=True,
        )
        _validate_cors_settings(s)  # should not raise

    def test_production_wildcard_without_credentials_ok(self):
        s = ServiceSettings(
            debug=False,
            cors_allowed_origins=["*"],
            cors_allow_credentials=False,
        )
        _validate_cors_settings(s)  # should not raise

    def test_debug_mode_allows_wildcard_credentials(self):
        """debug 模式放行，方便本地开发。"""
        s = ServiceSettings(
            debug=True,
            cors_allowed_origins=["*"],
            cors_allow_credentials=True,
        )
        _validate_cors_settings(s)  # should not raise
