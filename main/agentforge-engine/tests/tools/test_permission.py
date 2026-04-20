"""
Tests for PermissionChecker

Tests for tool permission checking and access control.
"""


from pyagentforge.tools.permission import (
    ParameterPermissionConfig,
    ParameterPermissionRule,
    PermissionChecker,
    PermissionConfig,
    PermissionResult,
    create_permission_config_from_dict,
)


class TestPermissionResult:
    """Test cases for PermissionResult enum."""

    def test_permission_result_values(self):
        """Test permission result enum values."""
        assert PermissionResult.ALLOW.value == "allow"
        assert PermissionResult.DENY.value == "deny"
        assert PermissionResult.ASK.value == "ask"


class TestParameterPermissionRule:
    """Test cases for ParameterPermissionRule."""

    def test_check_exact_match(self):
        """Test exact match pattern."""
        rule = ParameterPermissionRule(
            parameter_name="file_path",
            patterns={
                "*.env": PermissionResult.DENY,
                "config.yaml": PermissionResult.ALLOW,
            },
            default=PermissionResult.ASK,
        )

        assert rule.check("config.yaml") == PermissionResult.ALLOW
        assert rule.check("test.env") == PermissionResult.DENY
        assert rule.check("other.txt") == PermissionResult.ASK

    def test_check_glob_pattern(self):
        """Test glob pattern matching."""
        rule = ParameterPermissionRule(
            parameter_name="file_path",
            patterns={
                "*.env": PermissionResult.DENY,
                "src/**": PermissionResult.ALLOW,
            },
            default=PermissionResult.ASK,
        )

        assert rule.check("test.env") == PermissionResult.DENY
        assert rule.check("src/main.py") == PermissionResult.ALLOW
        assert rule.check("other.txt") == PermissionResult.ASK

    def test_check_wildcard_pattern(self):
        """Test wildcard pattern matching."""
        rule = ParameterPermissionRule(
            parameter_name="command",
            patterns={
                "git*": PermissionResult.ALLOW,
                "rm*": PermissionResult.DENY,
            },
            default=PermissionResult.ASK,
        )

        assert rule.check("git status") == PermissionResult.ALLOW
        assert rule.check("git commit -m 'test'") == PermissionResult.ALLOW
        assert rule.check("rm -rf /") == PermissionResult.DENY
        assert rule.check("ls") == PermissionResult.ASK

    def test_check_non_string_value(self):
        """Test checking non-string values (converted to string)."""
        rule = ParameterPermissionRule(
            parameter_name="timeout",
            patterns={
                "100": PermissionResult.ALLOW,
            },
            default=PermissionResult.DENY,
        )

        assert rule.check(100) == PermissionResult.ALLOW
        assert rule.check(200) == PermissionResult.DENY

    def test_specificity_ordering(self):
        """Test that more specific patterns take priority."""
        rule = ParameterPermissionRule(
            parameter_name="file_path",
            patterns={
                "*.env": PermissionResult.DENY,
                "config/*.env": PermissionResult.ALLOW,
            },
            default=PermissionResult.ASK,
        )

        # More specific pattern (config/*.env) should win
        assert rule.check("config/app.env") == PermissionResult.ALLOW
        assert rule.check("other.env") == PermissionResult.DENY


class TestPermissionConfig:
    """Test cases for PermissionConfig."""

    def test_default_config(self):
        """Test default configuration allows all."""
        config = PermissionConfig()

        assert config.allowed == ["*"]
        assert config.denied == []
        assert config.ask == []

    def test_custom_config(self):
        """Test custom configuration."""
        config = PermissionConfig(
            allowed=["read", "write"],
            denied=["bash"],
            ask=["edit"],
        )

        assert config.allowed == ["read", "write"]
        assert config.denied == ["bash"]
        assert config.ask == ["edit"]


class TestPermissionChecker:
    """Test cases for PermissionChecker."""

    def test_allow_all(self):
        """Test allowing all tools by default."""
        config = PermissionConfig(allowed=["*"])
        checker = PermissionChecker(config)

        assert checker.check("read", {}) == PermissionResult.ALLOW
        assert checker.check("write", {}) == PermissionResult.ALLOW
        assert checker.check("bash", {"command": "ls"}) == PermissionResult.ALLOW

    def test_deny_specific(self):
        """Test denying specific tools."""
        config = PermissionConfig(
            allowed=["*"],
            denied=["bash"],
        )
        checker = PermissionChecker(config)

        assert checker.check("read", {}) == PermissionResult.ALLOW
        assert checker.check("bash", {"command": "ls"}) == PermissionResult.DENY

    def test_ask_permission(self):
        """Test tools that require permission."""
        config = PermissionConfig(
            allowed=["*"],
            ask=["write"],
        )
        checker = PermissionChecker(config)

        assert checker.check("read", {}) == PermissionResult.ALLOW
        assert checker.check("write", {"file_path": "/tmp/test.txt"}) == PermissionResult.ASK

    def test_priority_rules(self):
        """Test priority: deny > ask > allow."""
        config = PermissionConfig(
            allowed=["*"],
            denied=["bash"],
            ask=["read"],
        )
        checker = PermissionChecker(config)

        # Denied takes priority
        assert checker.check("bash", {}) == PermissionResult.DENY

        # Ask for read
        assert checker.check("read", {}) == PermissionResult.ASK

        # Write is allowed
        assert checker.check("write", {}) == PermissionResult.ALLOW

    def test_specific_allowed(self):
        """Test allowing only specific tools."""
        config = PermissionConfig(
            allowed=["read", "write"],
            denied=[],
            ask=[],
        )
        checker = PermissionChecker(config)

        assert checker.check("read", {}) == PermissionResult.ALLOW
        assert checker.check("write", {}) == PermissionResult.ALLOW
        # Not in allowed list, so denied by default
        assert checker.check("bash", {}) == PermissionResult.DENY

    def test_check_command_blacklist(self):
        """Test command blacklist."""
        config = PermissionConfig(
            allowed=["*"],
            command_blacklist=["rm", "chmod"],
        )
        checker = PermissionChecker(config)

        assert checker.check_command("rm -rf /") == PermissionResult.DENY
        assert checker.check_command("chmod 777 file") == PermissionResult.DENY
        assert checker.check_command("ls") == PermissionResult.ALLOW

    def test_check_command_whitelist(self):
        """Test command whitelist."""
        config = PermissionConfig(
            allowed=["*"],
            command_whitelist=["git", "ls", "cat"],
        )
        checker = PermissionChecker(config)

        assert checker.check_command("git status") == PermissionResult.ALLOW
        assert checker.check_command("ls -la") == PermissionResult.ALLOW
        # npm is not in whitelist
        assert checker.check_command("npm install") == PermissionResult.DENY

    def test_check_path_allowed(self):
        """Test path permission - allowed paths."""
        config = PermissionConfig(
            allowed_paths=["/workspace", "/tmp"],
        )
        checker = PermissionChecker(config)

        assert checker.check_path("/workspace/test.txt") == PermissionResult.ALLOW
        assert checker.check_path("/tmp/file.txt") == PermissionResult.ALLOW
        assert checker.check_path("/etc/passwd") == PermissionResult.DENY

    def test_check_path_denied(self):
        """Test path permission - denied paths."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=["/etc", "/root"],
        )
        checker = PermissionChecker(config)

        assert checker.check_path("/etc/passwd") == PermissionResult.DENY
        assert checker.check_path("/root/.ssh") == PermissionResult.DENY
        assert checker.check_path("/home/user/file.txt") == PermissionResult.ALLOW

    def test_check_host_permission(self):
        """Test host permission."""
        config = PermissionConfig(
            allowed=["*"],
            denied_hosts=["*.internal.com", "localhost"],
        )
        checker = PermissionChecker(config)

        assert checker.check_host("api.internal.com") == PermissionResult.DENY
        assert checker.check_host("localhost") == PermissionResult.DENY
        assert checker.check_host("example.com") == PermissionResult.ALLOW

    def test_parameter_level_permission(self):
        """Test parameter-level permission checking."""
        param_config = ParameterPermissionConfig()
        param_config.tools["write"] = {
            "file_path": ParameterPermissionRule(
                parameter_name="file_path",
                patterns={
                    "*.env": PermissionResult.DENY,
                    "*.md": PermissionResult.ALLOW,
                },
                default=PermissionResult.ASK,
            )
        }

        config = PermissionConfig(
            allowed=["*"],
            parameter_rules=param_config,
        )
        checker = PermissionChecker(config)

        # Parameter pattern matching
        result = checker.check("write", {"file_path": "/tmp/test.env"})
        assert result == PermissionResult.DENY

        result = checker.check("write", {"file_path": "/tmp/README.md"})
        assert result == PermissionResult.ALLOW

        result = checker.check("write", {"file_path": "/tmp/other.txt"})
        assert result == PermissionResult.ASK

    def test_parameter_permission_overrides_tool(self):
        """Test that parameter deny overrides tool allow."""
        param_config = ParameterPermissionConfig()
        param_config.tools["bash"] = {
            "command": ParameterPermissionRule(
                parameter_name="command",
                patterns={
                    "rm*": PermissionResult.DENY,
                },
                default=PermissionResult.ALLOW,
            )
        }

        config = PermissionConfig(
            allowed=["*"],  # All tools allowed at tool level
            parameter_rules=param_config,
        )
        checker = PermissionChecker(config)

        # rm command denied at parameter level
        assert checker.check("bash", {"command": "rm -rf /"}) == PermissionResult.DENY
        # ls command allowed
        assert checker.check("bash", {"command": "ls"}) == PermissionResult.ALLOW

    def test_pattern_matching_prefix(self):
        """Test pattern matching with prefix wildcard."""
        config = PermissionConfig()
        checker = PermissionChecker(config)

        # Test internal _matches_pattern method
        assert checker._matches_pattern("git-status", ["git*"]) is True
        assert checker._matches_pattern("npm-install", ["git*"]) is False

    def test_pattern_matching_suffix(self):
        """Test pattern matching with suffix wildcard."""
        config = PermissionConfig()
        checker = PermissionChecker(config)

        assert checker._matches_pattern("config.env", ["*.env"]) is True
        assert checker._matches_pattern("config.yaml", ["*.env"]) is False

    def test_pattern_matching_exact(self):
        """Test exact pattern matching."""
        config = PermissionConfig()
        checker = PermissionChecker(config)

        assert checker._matches_pattern("read", ["read", "write"]) is True
        assert checker._matches_pattern("bash", ["read", "write"]) is False

    def test_pattern_matching_wildcard(self):
        """Test wildcard pattern matching."""
        config = PermissionConfig()
        checker = PermissionChecker(config)

        assert checker._matches_pattern("anything", ["*"]) is True


class TestCreatePermissionConfigFromDict:
    """Test cases for create_permission_config_from_dict function."""

    def test_create_from_simple_dict(self):
        """Test creating config from simple dictionary."""
        config_dict = {
            "allowed": ["read", "write"],
            "denied": ["bash"],
        }

        config = create_permission_config_from_dict(config_dict)

        assert config.allowed == ["read", "write"]
        assert config.denied == ["bash"]

    def test_create_from_dict_with_parameter_rules(self):
        """Test creating config with parameter rules."""
        config_dict = {
            "allowed": ["*"],
            "parameter_rules": {
                "write": {
                    "file_path": {
                        "patterns": {
                            "*.env": "deny",
                            "*.md": "allow",
                        },
                        "default": "ask",
                    }
                }
            }
        }

        config = create_permission_config_from_dict(config_dict)

        assert "write" in config.parameter_rules.tools
        assert "file_path" in config.parameter_rules.tools["write"]

        rule = config.parameter_rules.tools["write"]["file_path"]
        assert rule.default == PermissionResult.ASK

    def test_create_from_dict_with_all_options(self):
        """Test creating config with all options."""
        config_dict = {
            "allowed": ["*"],
            "denied": ["bash"],
            "ask": ["write"],
            "command_whitelist": ["git", "ls"],
            "command_blacklist": ["rm"],
            "allowed_paths": ["/workspace"],
            "denied_paths": ["/etc"],
            "allowed_hosts": ["example.com"],
            "denied_hosts": ["localhost"],
        }

        config = create_permission_config_from_dict(config_dict)

        assert config.allowed == ["*"]
        assert config.denied == ["bash"]
        assert config.ask == ["write"]
        assert config.command_whitelist == ["git", "ls"]
        assert config.command_blacklist == ["rm"]
        assert config.allowed_paths == ["/workspace"]
        assert config.denied_paths == ["/etc"]
        assert config.allowed_hosts == ["example.com"]
        assert config.denied_hosts == ["localhost"]
