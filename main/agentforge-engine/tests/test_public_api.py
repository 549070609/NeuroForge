"""Public API regression tests for P0 breaking changes."""

import pyagentforge


def test_factory_functions_removed_from_top_level_exports():
    assert not hasattr(pyagentforge, "create_engine")
    assert not hasattr(pyagentforge, "create_minimal_engine")
