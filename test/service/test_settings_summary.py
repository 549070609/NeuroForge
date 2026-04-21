"""P1-8 配置脱敏摘要 + P1-9 path 字段回归测试。"""

from __future__ import annotations

import logging

import pytest

from Service.config.settings import ServiceSettings


class TestMaskedSummary:
    def test_mask_hides_middle(self, caplog):
        s = ServiceSettings(api_key="sk-1234567890abcdef")
        with caplog.at_level(logging.INFO):
            s.print_masked_summary()
        assert "sk-***def" in caplog.text

    def test_mask_short_key(self, caplog):
        s = ServiceSettings(api_key="abc")
        with caplog.at_level(logging.INFO):
            s.print_masked_summary()
        assert "***" in caplog.text
        assert "abc" not in caplog.text

    def test_mask_none(self, caplog):
        s = ServiceSettings(api_key=None)
        with caplog.at_level(logging.INFO):
            s.print_masked_summary()
        assert "<not set>" in caplog.text


class TestPathSettings:
    def test_agent_dir_default(self):
        s = ServiceSettings()
        assert s.agent_dir == ""

    def test_data_dir_default(self):
        s = ServiceSettings()
        assert s.data_dir == "data"

    def test_override_via_constructor(self):
        s = ServiceSettings(agent_dir="/custom/agents", data_dir="/custom/data")
        assert s.agent_dir == "/custom/agents"
        assert s.data_dir == "/custom/data"
