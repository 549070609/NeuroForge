"""
Tests for Error Recovery
"""


import pytest

from pyagentforge.plugins.middleware.error_recovery.error_recovery import (
    ErrorClassifier,
    ErrorType,
    RecoveryStrategy,
    RetryDecision,
    RetryManager,
    RetryPolicy,
    RetryResult,
)


class TestErrorClassifier:
    """Tests for ErrorClassifier"""

    def test_classify_rate_limit(self):
        """Test rate limit error classification"""
        classifier = ErrorClassifier()

        errors = [
            Exception("rate limit exceeded"),
            Exception("429 Too Many Requests"),
            Exception("API rate_limit hit"),
        ]

        for error in errors:
            assert classifier.classify(error) == ErrorType.RATE_LIMIT

    def test_classify_timeout(self):
        """Test timeout error classification"""
        classifier = ErrorClassifier()

        errors = [
            Exception("Request timeout"),
            Exception("Operation timed out"),
            TimeoutError("Connection timed out"),
        ]

        for error in errors:
            assert classifier.classify(error) == ErrorType.TIMEOUT

    def test_classify_token_limit(self):
        """Test token limit error classification"""
        classifier = ErrorClassifier()

        errors = [
            Exception("context_length_exceeded"),
            Exception("prompt is too long: 200000 tokens"),
            Exception("this request would exceed the token limit"),
        ]

        for error in errors:
            assert classifier.classify(error) == ErrorType.TOKEN_LIMIT

    def test_classify_auth_error(self):
        """Test auth error classification"""
        classifier = ErrorClassifier()

        errors = [
            Exception("Unauthorized: 401"),
            Exception("Invalid API key"),
        ]

        for error in errors:
            assert classifier.classify(error) == ErrorType.AUTH_ERROR

    def test_classify_unknown(self):
        """Test unknown error classification"""
        classifier = ErrorClassifier()

        error = Exception("Something weird happened")
        assert classifier.classify(error) == ErrorType.UNKNOWN


class TestRetryPolicy:
    """Tests for RetryPolicy"""

    def test_default_policy(self):
        """Test default policy values"""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.initial_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.backoff_factor == 2.0
        assert policy.jitter is True

    def test_custom_policy(self):
        """Test custom policy values"""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_factor=1.5,
            jitter=False,
        )

        assert policy.max_retries == 5
        assert policy.initial_delay == 0.5
        assert policy.max_delay == 30.0
        assert policy.backoff_factor == 1.5
        assert policy.jitter is False


class TestRetryManager:
    """Tests for RetryManager"""

    def test_calculate_delay(self):
        """Test delay calculation"""
        policy = RetryPolicy(
            initial_delay=1.0,
            max_delay=10.0,
            backoff_factor=2.0,
            jitter=False,
        )
        manager = RetryManager(policy=policy)

        # First attempt
        delay1 = manager.calculate_delay(1)
        assert delay1 == 1.0

        # Second attempt
        delay2 = manager.calculate_delay(2)
        assert delay2 == 2.0

        # Third attempt
        delay3 = manager.calculate_delay(3)
        assert delay3 == 4.0

        # Should cap at max_delay
        delay4 = manager.calculate_delay(10)
        assert delay4 == 10.0

    def test_should_retry_rate_limit(self):
        """Test retry decision for rate limits"""
        manager = RetryManager()
        error = Exception("rate limit exceeded")

        decision, delay = manager.should_retry(error, attempt=1)

        assert decision == RetryDecision.RETRY_WITH_BACKOFF
        assert delay > 0

    def test_should_retry_auth_error(self):
        """Test retry decision for auth errors"""
        manager = RetryManager()
        error = Exception("Unauthorized: 401")

        decision, delay = manager.should_retry(error, attempt=1)

        assert decision == RetryDecision.FAIL

    def test_should_retry_max_attempts(self):
        """Test max attempts limit"""
        policy = RetryPolicy(max_retries=2)
        manager = RetryManager(policy=policy)
        error = Exception("rate limit exceeded")

        decision, _ = manager.should_retry(error, attempt=2)

        assert decision == RetryDecision.FAIL

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test successful execution"""
        manager = RetryManager()

        async def succeed_immediately():
            return "success"

        result = await manager.execute_with_retry(succeed_immediately)

        assert result.success
        assert result.attempts == 1
        assert result.result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_eventual_success(self):
        """Test eventual success after retries"""
        policy = RetryPolicy(max_retries=3, jitter=False)
        manager = RetryManager(policy=policy)

        call_count = 0

        async def succeed_on_third_try():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("rate limit exceeded")
            return "success"

        result = await manager.execute_with_retry(succeed_on_third_try)

        assert result.success
        assert result.attempts == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self):
        """Test failure after max retries"""
        policy = RetryPolicy(max_retries=2)
        manager = RetryManager(policy=policy)

        async def always_fail():
            raise Exception("rate limit exceeded")

        result = await manager.execute_with_retry(always_fail)

        assert not result.success
        assert result.attempts == 2
        assert result.last_error is not None


class TestRetryResult:
    """Tests for RetryResult"""

    def test_success_result(self):
        """Test successful result"""
        result = RetryResult(
            success=True,
            attempts=1,
            total_delay=0.0,
            result="done",
        )

        assert result.success
        assert result.attempts == 1
        assert result.result == "done"
        assert result.last_error is None

    def test_failure_result(self):
        """Test failed result"""
        error = Exception("Failed")
        result = RetryResult(
            success=False,
            attempts=3,
            total_delay=5.0,
            last_error=error,
        )

        assert not result.success
        assert result.attempts == 3
        assert result.total_delay == 5.0
        assert result.last_error == error


class TestRecoveryStrategy:
    """Tests for RecoveryStrategy enum"""

    def test_strategy_values(self):
        """Test strategy enum values"""
        assert RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS.value == "remove_old_tool_results"
        assert RecoveryStrategy.TRUNCATE_MESSAGES.value == "truncate_messages"
        assert RecoveryStrategy.EMERGENCY_COMPACT.value == "emergency_compact"
