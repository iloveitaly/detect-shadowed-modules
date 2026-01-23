"""Test editable package path detection."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import detect_shadowed_modules
from detect_shadowed_modules.editable import get_editable_paths


def test_get_editable_paths_success() -> None:
    """Test parsing valid uv JSON output."""
    mock_output = json.dumps(
        [
            {
                "name": "my-package",
                "version": "0.1.0",
                "editable_project_location": "/path/to/my-package",
            },
            {
                "name": "another-package",
                "version": "1.2.3",
                "editable_project_location": "/path/to/another-package",
            },
        ]
    )

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = mock_output

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        paths = get_editable_paths()

    assert len(paths) == 2
    assert Path("/path/to/my-package") in paths
    assert Path("/path/to/another-package") in paths


def test_get_editable_paths_empty_list() -> None:
    """Test parsing empty JSON array when no editable packages exist."""
    mock_output = "[]"

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = mock_output

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_missing_field() -> None:
    """Test handling packages without editable_project_location field."""
    mock_output = json.dumps(
        [
            {
                "name": "regular-package",
                "version": "1.0.0",
                # No editable_project_location field
            },
            {
                "name": "editable-package",
                "version": "0.1.0",
                "editable_project_location": "/path/to/editable",
            },
        ]
    )

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = mock_output

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        paths = get_editable_paths()

    assert len(paths) == 1
    assert Path("/path/to/editable") in paths


def test_get_editable_paths_uv_not_found() -> None:
    """Test handling when uv is not installed."""
    with patch(
        "detect_shadowed_modules.editable.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_uv_error() -> None:
    """Test handling when uv returns non-zero exit code."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_invalid_json() -> None:
    """Test handling malformed JSON output."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "not valid json"

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_timeout() -> None:
    """Test handling when uv command times out."""
    import subprocess

    with patch(
        "detect_shadowed_modules.editable.subprocess.run",
        side_effect=subprocess.TimeoutExpired("uv", 10),
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_unexpected_exception() -> None:
    """Test handling unexpected exceptions gracefully."""
    with patch(
        "detect_shadowed_modules.editable.subprocess.run",
        side_effect=RuntimeError("Unexpected error"),
    ):
        paths = get_editable_paths()

    assert paths == []


def test_get_editable_paths_command_args() -> None:
    """Test that the correct uv command is called."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "[]"

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ) as mock_run:
        get_editable_paths()

    # Verify the command called
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args[0][0] == ["uv", "pip", "list", "-e", "--format", "json"]
    assert call_args[1]["capture_output"] is True
    assert call_args[1]["text"] is True
    assert call_args[1]["timeout"] == 10


def test_integration_with_find_conflicts(tmp_path: Path) -> None:
    """Test that editable paths are integrated with find_conflicts correctly."""
    # Create editable package location
    editable_path = tmp_path / "editable_pkg"
    editable_path.mkdir()
    (editable_path / "mymodule").mkdir()

    # Create regular sys.path location with same module
    syspath_location = tmp_path / "site_packages"
    syspath_location.mkdir()
    (syspath_location / "mymodule").mkdir()

    # Mock uv to return the editable path
    mock_output = json.dumps(
        [
            {
                "name": "mypackage",
                "version": "0.1.0",
                "editable_project_location": str(editable_path),
            }
        ]
    )
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = mock_output

    with patch(
        "detect_shadowed_modules.editable.subprocess.run", return_value=mock_result
    ):
        editable_paths = get_editable_paths()

    # Combine paths as main() does
    combined_paths = [str(p) for p in editable_paths] + [str(syspath_location)]

    # Find conflicts
    conflicts = detect_shadowed_modules.find_conflicts(combined_paths)

    # Should detect mymodule conflict
    assert "mymodule" in conflicts
    assert len(conflicts["mymodule"]) == 2
    # Editable path should come first (takes precedence)
    assert conflicts["mymodule"][0] == editable_path
    assert conflicts["mymodule"][1] == syspath_location
