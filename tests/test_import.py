"""Test detect-shadowed-modules."""

import json
import sys
from pathlib import Path
from unittest.mock import patch


import detect_shadowed_modules


def test_import() -> None:
    """Test that the module can be imported."""
    assert isinstance(detect_shadowed_modules.__name__, str)


def test_get_subdirectories(tmp_path: Path) -> None:
    """Test getting subdirectories from a path."""
    # Create test directory structure
    (tmp_path / "package1").mkdir()
    (tmp_path / "package2").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "package.dist-info").mkdir()
    (tmp_path / "package.egg-info").mkdir()
    (tmp_path / "regular_file.txt").touch()

    subdirs = detect_shadowed_modules.get_subdirectories(tmp_path)

    # Should only include package1 and package2
    assert sorted(subdirs) == ["package1", "package2"]


def test_get_subdirectories_nonexistent(tmp_path: Path) -> None:
    """Test getting subdirectories from nonexistent path."""
    nonexistent = tmp_path / "nonexistent"
    subdirs = detect_shadowed_modules.get_subdirectories(nonexistent)
    assert subdirs == []


def test_find_conflicts_no_conflicts(tmp_path: Path) -> None:
    """Test that no conflicts are found when directories are unique."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path1.mkdir()
    path2.mkdir()
    (path1 / "package1").mkdir()
    (path2 / "package2").mkdir()

    conflicts = detect_shadowed_modules.find_conflicts([str(path1), str(path2)])
    assert conflicts == {}


def test_find_conflicts_with_conflicts(tmp_path: Path) -> None:
    """Test that conflicts are detected when same directory exists in multiple paths."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path1.mkdir()
    path2.mkdir()
    (path1 / "shared_package").mkdir()
    (path2 / "shared_package").mkdir()
    (path1 / "unique1").mkdir()
    (path2 / "unique2").mkdir()

    conflicts = detect_shadowed_modules.find_conflicts([str(path1), str(path2)])

    assert "shared_package" in conflicts
    assert len(conflicts["shared_package"]) == 2
    assert "unique1" not in conflicts
    assert "unique2" not in conflicts


def test_find_conflicts_multiple_duplicates(tmp_path: Path) -> None:
    """Test that conflicts are detected for multiple duplicate directories."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path3 = tmp_path / "path3"
    for p in [path1, path2, path3]:
        p.mkdir()
        (p / "common").mkdir()

    conflicts = detect_shadowed_modules.find_conflicts(
        [str(path1), str(path2), str(path3)]
    )

    assert "common" in conflicts
    assert len(conflicts["common"]) == 3


def test_format_report_no_conflicts() -> None:
    """Test formatting report when no conflicts exist."""
    report = detect_shadowed_modules.format_report({})
    assert "No conflicting directory names found" in report


def test_format_report_with_conflicts(tmp_path: Path) -> None:
    """Test formatting report with conflicts."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    conflicts = {"testpkg": [path1, path2]}

    report = detect_shadowed_modules.format_report(conflicts)

    assert "Conflicting directory names detected" in report
    assert "testpkg/" in report
    assert str(path1 / "testpkg") in report
    assert str(path2 / "testpkg") in report
    assert "shadows others" in report
    assert "shadowed" in report


def test_format_json_no_conflicts() -> None:
    """Test JSON formatting when no conflicts exist."""
    json_output = detect_shadowed_modules.format_json({})
    data = json.loads(json_output)
    assert data["shadowed"] == []


def test_format_json_with_conflicts(tmp_path: Path) -> None:
    """Test JSON formatting with conflicts."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path3 = tmp_path / "path3"
    conflicts = {"testpkg": [path1, path2, path3]}

    json_output = detect_shadowed_modules.format_json(conflicts)
    data = json.loads(json_output)

    assert "shadowed" in data
    assert len(data["shadowed"]) == 2  # path2 and path3 are shadowed by path1
    assert all("path" in item for item in data["shadowed"])
    assert all("shadowed_by" in item for item in data["shadowed"])


def test_main_no_conflicts(tmp_path: Path, capsys, monkeypatch) -> None:
    """Test main function with no conflicts."""
    path1 = tmp_path / "path1"
    path1.mkdir()
    (path1 / "package1").mkdir()

    with patch.object(sys, "argv", ["detect-shadowed-modules"]):
        with patch.object(sys, "path", [str(path1)]):
            exit_code = detect_shadowed_modules.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No conflicting directory names found" in captured.out


def test_main_with_conflicts(tmp_path: Path, capsys) -> None:
    """Test main function with conflicts."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path1.mkdir()
    path2.mkdir()
    (path1 / "shared").mkdir()
    (path2 / "shared").mkdir()

    with patch.object(sys, "argv", ["detect-shadowed-modules"]):
        with patch.object(sys, "path", [str(path1), str(path2)]):
            exit_code = detect_shadowed_modules.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Conflicting directory names detected" in captured.out
    assert "shared/" in captured.out


def test_main_quiet_mode(tmp_path: Path, capsys) -> None:
    """Test main function in quiet mode."""
    path1 = tmp_path / "path1"
    path1.mkdir()
    (path1 / "package1").mkdir()

    with patch.object(sys, "argv", ["detect-shadowed-modules", "-q"]):
        with patch.object(sys, "path", [str(path1)]):
            exit_code = detect_shadowed_modules.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    # In quiet mode, stderr should not contain "Scanning" message
    assert "Scanning" not in captured.err


def test_main_json_output(tmp_path: Path, capsys) -> None:
    """Test main function with JSON output."""
    path1 = tmp_path / "path1"
    path2 = tmp_path / "path2"
    path1.mkdir()
    path2.mkdir()
    (path1 / "shared").mkdir()
    (path2 / "shared").mkdir()

    with patch.object(sys, "argv", ["detect-shadowed-modules", "--json"]):
        with patch.object(sys, "path", [str(path1), str(path2)]):
            exit_code = detect_shadowed_modules.main()

    captured = capsys.readouterr()
    assert exit_code == 1

    # Should be valid JSON
    data = json.loads(captured.out)
    assert "shadowed" in data
    assert len(data["shadowed"]) >= 1
