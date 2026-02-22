"""Tests for removed pyagentforge API entrypoint."""

import pytest

from pyagentforge.api import APIRemovedError, create_app


def test_create_app_removed() -> None:
    """create_app should always fail after API migration to Service gateway."""
    with pytest.raises(APIRemovedError) as exc:
        create_app()

    assert "Service.gateway.app:create_app" in str(exc.value)