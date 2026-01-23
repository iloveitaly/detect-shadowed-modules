"""Test detect-shadowed-modules."""

import detect_shadowed_modules


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(detect_shadowed_modules.__name__, str)