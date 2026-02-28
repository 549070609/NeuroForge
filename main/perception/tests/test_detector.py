"""
单元测试 — detector.detect_format
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector import detect_format


class TestDetectFormat:
    def test_aton_schema_prefix(self):
        assert detect_format("@schema[id:int, level:str]") == "aton"

    def test_aton_defaults_prefix(self):
        assert detect_format("@defaults\nkey: value") == "aton"

    def test_aton_schema_with_leading_whitespace(self):
        assert detect_format("  @schema[id:int]") == "aton"

    def test_toon_named_table(self):
        raw = "events[2]{id,level,message}:\n  1,error,msg\n  2,info,msg"
        assert detect_format(raw) == "toon"

    def test_toon_simple_bracket_start(self):
        raw = "[3]{id,level}:\n  1,error\n  2,warn\n  3,info"
        assert detect_format(raw) == "toon"

    def test_unknown_plain_text(self):
        assert detect_format("plain log line") == "unknown"

    def test_unknown_json_object(self):
        assert detect_format('{"level": "error", "message": "fail"}') == "unknown"

    def test_unknown_empty_string(self):
        assert detect_format("") == "unknown"

    def test_unknown_whitespace_only(self):
        assert detect_format("   \n\t  ") == "unknown"

    def test_unknown_none_like_empty(self):
        assert detect_format("") == "unknown"
